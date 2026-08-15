import path from "node:path";
import { LocalProvider, ResendProvider, type EmailProvider } from "@inner/email";

let provider: EmailProvider | undefined;

export function getEmailProvider(): EmailProvider {
  if (provider) return provider;

  const apiKey = process.env.RESEND_API_KEY;
  const fromAddress = process.env.RESEND_FROM_ADDRESS;

  if (apiKey && fromAddress) {
    provider = new ResendProvider(apiKey, fromAddress);
    return provider;
  }

  console.warn("[email] No RESEND_API_KEY configured — using LocalProvider (writes to .local-emails/, dev only).");
  provider = new LocalProvider(path.join(process.cwd(), ".local-emails"));
  return provider;
}
