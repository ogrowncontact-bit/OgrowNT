import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { EmailProvider, SendEmailParams, SendResult } from "./types";

/**
 * Dev-only stand-in for local testing without a real Resend key — writes
 * the rendered email (and any attachments) to disk instead of sending it,
 * so the full report-delivery pipeline is inspectable end-to-end offline.
 */
export class LocalProvider implements EmailProvider {
  readonly name = "local";
  constructor(private outputDir: string) {}

  async send(params: SendEmailParams): Promise<SendResult> {
    await mkdir(this.outputDir, { recursive: true });
    const stamp = Date.now();
    const safeTo = params.to.replace(/[^a-z0-9@._-]/gi, "_");
    const htmlPath = path.join(this.outputDir, `${stamp}-${safeTo}.html`);
    await writeFile(htmlPath, params.html, "utf8");

    for (const attachment of params.attachments ?? []) {
      await writeFile(path.join(this.outputDir, `${stamp}-${safeTo}-${attachment.filename}`), attachment.content);
    }

    console.log(`[email:local] "${params.subject}" to ${params.to} written to ${htmlPath}`);
    return { ok: true, providerRef: htmlPath };
  }
}
