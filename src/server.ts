import path from "node:path";
import express, { type Request } from "express";
import { config } from "./config";
import { startReminderScheduler } from "./reminders/scheduler";
import { adminRouter } from "./routes/admin.routes";
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

app.use("/api", express.json(), adminRouter);
app.use("/widget", express.static(path.join(__dirname, "..", "public")));

app.get("/health", (_req, res) => res.json({ ok: true }));

app.listen(config.port, () => {
  console.log(`OgrowNT rodando na porta ${config.port}`);
  startReminderScheduler();
});
