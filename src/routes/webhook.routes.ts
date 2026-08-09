import { Router, type Request, type Response } from "express";
import { config } from "../config";
import { routeIncomingMessage } from "../conversation/router";
import { prisma } from "../db";
import { parseIncomingWebhook, verifySignature } from "../whatsapp/webhook";

export const webhookRouter = Router();

// Handshake de verificacao exigido pela Meta ao configurar o webhook no
// dashboard do app (https://developers.facebook.com).
webhookRouter.get("/whatsapp", (req: Request, res: Response) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === config.whatsapp.webhookVerifyToken) {
    res.status(200).send(String(challenge ?? ""));
    return;
  }
  res.sendStatus(403);
});

webhookRouter.post("/whatsapp", (req: Request, res: Response) => {
  const rawBody = (req as Request & { rawBody?: Buffer }).rawBody;
  const signature = req.header("x-hub-signature-256");

  if (!rawBody || !verifySignature(rawBody, signature)) {
    res.sendStatus(401);
    return;
  }

  // A Meta espera confirmacao rapida (200) - o processamento roda depois,
  // de forma assincrona, para nao segurar a resposta do webhook.
  res.sendStatus(200);
  processWebhookPayload(req.body).catch((err) => {
    console.error("[webhook] erro ao processar payload:", err);
  });
});

async function processWebhookPayload(payload: unknown): Promise<void> {
  const entries = parseIncomingWebhook(payload);

  for (const entry of entries) {
    const account = await prisma.whatsAppAccount.findUnique({
      where: { phoneNumberId: entry.phoneNumberId },
      include: { business: true },
    });
    if (!account) {
      console.warn(`[webhook] nenhuma empresa conectada ao phoneNumberId ${entry.phoneNumberId}`);
      continue;
    }

    for (const message of entry.messages) {
      await routeIncomingMessage(
        account.business,
        account,
        message.from,
        entry.contactNames[message.from],
        message
      ).catch((err) => console.error("[webhook] erro ao processar mensagem:", err));
    }
  }
}
