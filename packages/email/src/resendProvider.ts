import { Resend } from "resend";
import type { EmailProvider, SendEmailParams, SendResult } from "./types";

export class ResendProvider implements EmailProvider {
  readonly name = "resend";
  private client: Resend;

  constructor(
    apiKey: string,
    private fromAddress: string
  ) {
    this.client = new Resend(apiKey);
  }

  async send(params: SendEmailParams): Promise<SendResult> {
    const result = await this.client.emails.send({
      from: this.fromAddress,
      to: params.to,
      subject: params.subject,
      html: params.html,
      attachments: params.attachments?.map((a) => ({
        filename: a.filename,
        content: a.content,
      })),
    });
    if (result.error) return { ok: false };
    return { ok: true, providerRef: result.data?.id };
  }
}
