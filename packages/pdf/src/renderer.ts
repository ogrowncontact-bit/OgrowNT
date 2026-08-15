import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { buildReportHtml, type ReportPdfData } from "./template";

const execFileAsync = promisify(execFile);

/**
 * render-worker.mjs runs as a subprocess, resolved relative to a Next.js
 * app's cwd (always the app directory when `next dev`/`next start` runs) —
 * see the comment in render-worker.mjs for why this can't just be an
 * in-process `import("playwright")`.
 */
function workerPath(): string {
  return path.resolve(process.cwd(), "../../packages/pdf/src/render-worker.mjs");
}

/** Real HTML->PDF rendering via headless Chromium — no external API, so this needs no key/credential to run. */
export async function renderReportPdf(data: ReportPdfData): Promise<Buffer> {
  const html = buildReportHtml(data);
  const dir = await mkdtemp(path.join(tmpdir(), "inner-pdf-"));
  const inputPath = path.join(dir, "input.html");
  const outputPath = path.join(dir, "output.pdf");

  try {
    await writeFile(inputPath, html, "utf8");
    await execFileAsync("node", [workerPath(), inputPath, outputPath], { timeout: 30_000 });
    return await readFile(outputPath);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
