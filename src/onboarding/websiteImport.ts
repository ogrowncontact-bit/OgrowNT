import dns from "node:dns/promises";
import net from "node:net";
import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config";

const FETCH_TIMEOUT_MS = 8_000;
const MAX_RESPONSE_BYTES = 700_000;
const MAX_TEXT_CHARS = 12_000;
const MAX_REDIRECTS = 4;
const MAX_SUGGESTIONS = 20;

export interface ImportedServiceSuggestion {
  name: string;
  price: number | null;
  durationMinutes: number | null;
}

function isPrivateIp(ip: string): boolean {
  if (net.isIPv4(ip)) {
    const [a, b] = ip.split(".").map(Number);
    return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 100 && b >= 64 && b <= 127);
  }
  if (net.isIPv6(ip)) {
    const lower = ip.toLowerCase();
    if (lower === "::1" || lower.startsWith("fe80") || lower.startsWith("fc") || lower.startsWith("fd")) return true;
    if (lower.startsWith("::ffff:")) {
      const v4 = lower.split(":").pop();
      return v4 && net.isIPv4(v4) ? isPrivateIp(v4) : true;
    }
    return false;
  }
  return true;
}

// Bloqueia URLs que resolvem para redes internas (evita SSRF a partir de um
// dono de negocio mal-intencionado colando uma URL apontando pro proprio
// backend/infra). Nota: o fetch() logo em seguida resolve o DNS de novo, por
// isso isso nao elimina 100% um ataque de DNS rebinding entre a checagem e a
// conexao real - aceitavel para essa funcionalidade (endpoint autenticado,
// so acessivel por OWNER/ADMIN da propria empresa), mas nao seria suficiente
// para um proxy publico sem autenticacao.
async function assertPublicHost(hostname: string): Promise<void> {
  const records = await dns.lookup(hostname, { all: true });
  if (records.length === 0) throw new Error("Nao foi possivel resolver esse dominio.");
  if (records.some((r) => isPrivateIp(r.address))) {
    throw new Error("Essa URL aponta para um endereco de rede interno, o que nao e permitido.");
  }
}

function htmlToText(html: string): string {
  const withoutNonContent = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ");
  const withoutTags = withoutNonContent.replace(/<[^>]+>/g, " ");
  return withoutTags
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX_TEXT_CHARS);
}

export async function fetchWebsiteText(startUrl: string): Promise<string> {
  let current = startUrl;

  for (let hop = 0; hop < MAX_REDIRECTS; hop++) {
    const parsed = new URL(current);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("Apenas URLs http:// ou https:// sao permitidas.");
    }
    await assertPublicHost(parsed.hostname);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let response: Response;
    try {
      response = await fetch(parsed.toString(), {
        redirect: "manual",
        signal: controller.signal,
        headers: { "user-agent": "OgrowNT-onboarding-import/1.0" },
      });
    } catch {
      throw new Error("Nao foi possivel acessar essa URL (tempo esgotado ou site fora do ar).");
    } finally {
      clearTimeout(timeout);
    }

    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get("location");
      if (!location) throw new Error("O site redirecionou sem indicar destino.");
      current = new URL(location, parsed).toString();
      continue;
    }

    if (!response.ok) {
      throw new Error(`O site respondeu com erro (status ${response.status}).`);
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("text/html") && !contentType.includes("text/plain")) {
      throw new Error("Essa URL nao aponta para uma pagina de texto/HTML.");
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("Nao foi possivel ler o conteudo dessa pagina.");
    const chunks: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_RESPONSE_BYTES) {
        await reader.cancel();
        break;
      }
      chunks.push(value);
    }

    return htmlToText(Buffer.concat(chunks).toString("utf8"));
  }

  throw new Error("Muitos redirecionamentos ao acessar essa URL.");
}

export async function extractServicesFromText(
  pageText: string,
  businessLabel: string
): Promise<ImportedServiceSuggestion[]> {
  const anthropic = new Anthropic({ apiKey: config.anthropic.apiKey });
  const response = await anthropic.messages.create({
    model: config.anthropic.model,
    max_tokens: 1500,
    system:
      'Voce extrai servicos/produtos e precos a partir de texto de sites de negocios (ex: cardapio de restaurante, tabela de precos de escola). ' +
      'Responda APENAS com um JSON valido no formato {"services":[{"name":string,"price":number|null,"durationMinutes":number|null}]}. ' +
      "Inclua so itens que parecam servicos/produtos reservaveis ou vendaveis reais, com nomes curtos e claros, no maximo " +
      `${MAX_SUGGESTIONS} itens. Se o preco nao estiver explicito no texto use null (nunca invente um preco). Se a duracao nao estiver ` +
      "explicita use null. Nao inclua nenhum texto fora do JSON.",
    messages: [
      { role: "user", content: `Tipo de negocio: ${businessLabel}\n\nTexto extraido do site:\n${pageText}` },
    ],
  });

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();

  const jsonMatch = text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error("A IA nao retornou um resultado reconhecivel.");

  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonMatch[0]);
  } catch {
    throw new Error("A IA nao retornou um JSON valido.");
  }

  const rawServices = (parsed as { services?: unknown })?.services;
  if (!Array.isArray(rawServices)) throw new Error("Formato de resposta inesperado da IA.");

  return rawServices
    .slice(0, MAX_SUGGESTIONS)
    .filter((s): s is Record<string, unknown> => typeof s === "object" && s !== null)
    .map((s) => ({
      name: String(s.name ?? "").trim().slice(0, 120),
      price: typeof s.price === "number" && Number.isFinite(s.price) && s.price >= 0 ? s.price : null,
      durationMinutes:
        typeof s.durationMinutes === "number" && Number.isFinite(s.durationMinutes) && s.durationMinutes > 0
          ? Math.round(s.durationMinutes)
          : null,
    }))
    .filter((s) => s.name.length > 0);
}
