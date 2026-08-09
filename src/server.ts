import path from "node:path";
import express, { type Request } from "express";
import { requireAuth } from "./auth/middleware";
import { config } from "./config";
import { startReminderScheduler } from "./reminders/scheduler";
import { adminRouter } from "./routes/admin.routes";
import { authRouter } from "./routes/auth.routes";
import { businessRouter } from "./routes/business.routes";
import { webhookRouter } from "./routes/webhook.routes";

const app = express();

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
app.use("/api/businesses/:businessId", adminRouter);

app.use("/widget", express.static(path.join(__dirname, "..", "public")));

app.get("/health", (_req, res) => res.json({ ok: true }));

app.listen(config.port, () => {
  console.log(`OgrowNT rodando na porta ${config.port}`);
  startReminderScheduler();
});
