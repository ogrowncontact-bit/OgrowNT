/**
 * Email provider abstraction — docs/ARCHITECTURE.md: transactional and
 * marketing email share this send path, but only transactional sends
 * (report delivery) are triggered without checking marketing consent.
 */
export interface Attachment {
  filename: string;
  content: Buffer;
  contentType: string;
}

export interface SendEmailParams {
  to: string;
  subject: string;
  html: string;
  attachments?: Attachment[];
}

export interface SendResult {
  ok: boolean;
  providerRef?: string;
}

export interface EmailProvider {
  readonly name: string;
  send(params: SendEmailParams): Promise<SendResult>;
}
