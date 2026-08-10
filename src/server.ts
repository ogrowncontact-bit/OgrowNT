import path from "node:path";
import cors from "cors";
import express, { type NextFunction, type Request, type Response } from "express";
import { startAutomationScheduler } from "./automations/scheduler";
import { requireAuth } from "./auth/middleware";
import { config } from "./config";
import { logger } from "./logger";
import { adminRouter } from "./routes/admin.routes";
import { agentRouter } from "./routes/agent.routes";
import { authRouter } from "./routes/auth.routes";
import { automationsRouter } from "./routes/automations.routes";
import { businessRouter } from "./routes/business.routes";
import { inboxRouter } from "./routes/inbox.routes";
import { metricsRouter } from "./routes/metrics.routes";
import { onboardingRouter } from "./routes/onboarding.routes";
import { webhookRouter } from "./routes/webhook.routes";

const app = express();

// Libera o dashboard (Next.js, ver web/) a chamar /api/* a partir do
// navegador - so as origens listadas em CORS_ORIGINS (ver src/config.ts).
// Nao se aplica a /webhooks (server-to-server, Meta nunca envia Origin).
app.use(
  "/api",
  cors({
    origin: config.corsOrigins.length > 0 ? config.corsOrigins : false,
    credentials: false,
  })
);

app.use(
  "/webhooks",
  express.json({
    verify: (req, _res, buf) => {
      (req as Request & { rawBody?: Buffer }).rawBody = Buffer.from(buf);
    },
  }),
  webhookRouter
);

// /api/auth e publico (registro/login). Tudo em /api/businesses exige um
// usuario autenticado (requireAuth); o isolamento por empresa/papel acontece
// dentro de cada router (requireMembership/requireRole).
app.use("/api/auth", express.json(), authRouter);
app.use("/api/businesses", express.json(), requireAuth);
app.use("/api/businesses", businessRouter);
app.use("/api/businesses/:businessId", onboardingRouter);
app.use("/api/businesses/:businessId", agentRouter);
app.use("/api/businesses/:businessId", adminRouter);
app.use("/api/businesses/:businessId", inboxRouter);
app.use("/api/businesses/:businessId", metricsRouter);
app.use("/api/businesses/:businessId", automationsRouter);

app.use("/widget", express.static(path.join(__dirname, "..", "public")));

app.get("/health", (_req, res) => res.json({ ok: true }));

// Middleware de erro central - toda rota async e envolvida por asyncHandler
// (ver src/asyncHandler.ts), entao qualquer excecao cai aqui em vez de
// derrubar o processo. Precisa ser o ULTIMO app.use (convencao do Express:
// middleware com 4 parametros = error handler).
app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  const status = typeof (err as { status?: unknown })?.status === "number" ? (err as { status: number }).status : 500;
  logger.error("http.unhandled_error", { status, message: err instanceof Error ? err.message : String(err) });
  if (res.headersSent) return;
  res.status(status).json({ error: status === 400 ? "Requisicao invalida." : "Erro interno. Tente novamente em instantes." });
});

app.listen(config.port, () => {
  console.log(`OgrowNT rodando na porta ${config.port}`);
  startAutomationScheduler();
});
