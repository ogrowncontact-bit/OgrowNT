// Plain JS, deliberately never imported by any TS module — it only runs as
// a spawned `node` subprocess (see renderer.ts). Next.js's webpack bundler
// chokes on playwright-core's optional chromium-bidi require when it's
// pulled into a traced route module graph; running it out-of-process
// sidesteps that entirely instead of fighting bundler config for it.
import { chromium } from "playwright";
import { readFile, writeFile } from "node:fs/promises";

const [, , inputPath, outputPath] = process.argv;

async function main() {
  const html = await readFile(inputPath, "utf8");
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined;
  const browser = await chromium.launch({ executablePath });
  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: "load" });
    const pdf = await page.pdf({ format: "A4", printBackground: true });
    await writeFile(outputPath, pdf);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
