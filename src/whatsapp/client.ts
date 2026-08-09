import { config } from "../config";

const GRAPH_BASE = "https://graph.facebook.com";

export interface SendContext {
  phoneNumberId: string;
  // Token de acesso ja descriptografado. Vazio = modo dry-run (loga no console
  // em vez de chamar a Graph API) - usado quando a empresa ainda nao conectou
  // um numero real de WhatsApp.
  accessToken: string;
}

async function callGraphApi(ctx: SendContext, body: unknown): Promise<unknown> {
  const url = `${GRAPH_BASE}/${config.whatsapp.apiVersion}/${ctx.phoneNumberId}/messages`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${ctx.accessToken}`,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Falha ao enviar mensagem WhatsApp (${res.status}): ${errText}`);
  }
  return res.json();
}

function dryRunLog(to: string, label: string, payload: unknown) {
  console.log(`[whatsapp:dry-run] -> ${to} ${label}`, JSON.stringify(payload));
}

export async function sendTextMessage(ctx: SendContext, to: string, text: string): Promise<unknown> {
  if (!ctx.accessToken) {
    dryRunLog(to, "texto", text);
    return { dryRun: true };
  }
  return callGraphApi(ctx, {
    messaging_product: "whatsapp",
    to,
    type: "text",
    text: { body: text },
  });
}

export interface ListRow {
  id: string;
  title: string;
  description?: string;
}

export interface ListSection {
  title: string;
  rows: ListRow[];
}

export async function sendListMessage(
  ctx: SendContext,
  to: string,
  opts: { bodyText: string; buttonText: string; sections: ListSection[] }
): Promise<unknown> {
  if (!ctx.accessToken) {
    dryRunLog(to, "lista", opts);
    return { dryRun: true };
  }
  return callGraphApi(ctx, {
    messaging_product: "whatsapp",
    to,
    type: "interactive",
    interactive: {
      type: "list",
      body: { text: opts.bodyText },
      action: { button: opts.buttonText, sections: opts.sections },
    },
  });
}

export interface ReplyButton {
  id: string;
  title: string;
}

export async function sendButtonsMessage(
  ctx: SendContext,
  to: string,
  bodyText: string,
  buttons: ReplyButton[]
): Promise<unknown> {
  if (!ctx.accessToken) {
    dryRunLog(to, "botoes", { bodyText, buttons });
    return { dryRun: true };
  }
  return callGraphApi(ctx, {
    messaging_product: "whatsapp",
    to,
    type: "interactive",
    interactive: {
      type: "button",
      body: { text: bodyText },
      action: {
        buttons: buttons.map((b) => ({ type: "reply", reply: { id: b.id, title: b.title } })),
      },
    },
  });
}

// Mensagens de template sao obrigatorias para iniciar contato fora da janela
// de 24h (ex: lembretes proativos) e precisam estar pre-aprovadas no Meta
// Business Manager da empresa.
export async function sendTemplateMessage(
  ctx: SendContext,
  to: string,
  templateName: string,
  languageCode: string,
  components?: unknown[]
): Promise<unknown> {
  if (!ctx.accessToken) {
    dryRunLog(to, `template:${templateName}`, components);
    return { dryRun: true };
  }
  return callGraphApi(ctx, {
    messaging_product: "whatsapp",
    to,
    type: "template",
    template: { name: templateName, language: { code: languageCode }, components },
  });
}
