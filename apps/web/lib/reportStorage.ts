import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Dev-only stand-in for the R2/S3 object storage described in
 * docs/ARCHITECTURE.md §1.1 — local disk under a gitignored directory.
 * Swap this for a real signed-URL-capable client when R2 credentials
 * exist; nothing else in the app should know the difference (it only
 * ever sees a `pdfObjectKey` string).
 */
const REPORTS_DIR = path.join(process.cwd(), ".local-reports");

export async function storeReportPdf(reportId: string, pdf: Buffer): Promise<string> {
  await mkdir(REPORTS_DIR, { recursive: true });
  const objectKey = `${reportId}.pdf`;
  await writeFile(path.join(REPORTS_DIR, objectKey), pdf);
  return objectKey;
}

export async function readReportPdf(objectKey: string): Promise<Buffer> {
  return readFile(path.join(REPORTS_DIR, objectKey));
}
