// franc e o unico pacote de deteccao de idioma que auditamos como seguro na
// ultima versao (franc 3.1.1-5.0.0 tem uma dependencia transitiva - trim -
// com uma vulnerabilidade de ReDoS: https://github.com/advisories/GHSA-w5p7-h5w8-2hfq).
// A versao segura (6.x) e ESM-only; o resto do projeto usa CommonJS, entao
// carregamos via import() dinamico (suportado nativamente pelo Node a
// partir de CJS) em vez de require().
let francPromise: Promise<typeof import("franc")> | null = null;
function loadFranc(): Promise<typeof import("franc")> {
  if (!francPromise) francPromise = import("franc");
  return francPromise;
}

// Idiomas que o produto sabe detectar e para os quais existem strings de UI
// traduzidas (ver src/language/strings.ts). Mapeamento entre os codigos
// ISO 639-1 usados pelo produto (pt, en, es...) e os codigos ISO 639-3 que a
// biblioteca de deteccao usa internamente.
const ISO_639_1_TO_3: Record<string, string> = {
  pt: "por",
  en: "eng",
  es: "spa",
  fr: "fra",
  de: "deu",
  it: "ita",
  nl: "nld",
};
const ISO_639_3_TO_1: Record<string, string> = Object.fromEntries(
  Object.entries(ISO_639_1_TO_3).map(([iso1, iso3]) => [iso3, iso1])
);

export const DETECTABLE_LANGUAGES = Object.keys(ISO_639_1_TO_3);

// Restringir a deteccao aos idiomas que a propria empresa suporta melhora
// MUITO a precisao em mensagens curtas (tipicas do WhatsApp) - sem isso,
// franc erra bastante em frases de poucas palavras. Retorna null quando o
// texto e curto/ambiguo demais para detectar com confianca.
export async function detectLanguage(text: string, candidateLanguages: string[]): Promise<string | null> {
  const candidates3 = candidateLanguages
    .map((lang) => ISO_639_1_TO_3[lang])
    .filter((v): v is string => Boolean(v));

  if (candidates3.length === 0 || !text.trim()) return null;

  const { franc } = await loadFranc();
  const detected = franc(text, { only: candidates3 });
  if (detected === "und") return null;
  return ISO_639_3_TO_1[detected] ?? null;
}

export interface ResolvedLanguage {
  language: string;
  detected: string | null;
}

// Resolve o idioma "efetivo" para responder a uma mensagem: tenta detectar a
// partir do texto atual (nunca fica preso a um idioma anterior se o cliente
// trocar de idioma no meio da conversa); se nao conseguir detectar com
// confianca, usa a preferencia salva do cliente; por ultimo, o idioma padrao
// da empresa.
export async function resolveLanguage(params: {
  text: string;
  supportedLanguages: string[];
  preferredLanguage: string; // "auto" ou um codigo ISO 639-1
  defaultLanguage: string;
}): Promise<ResolvedLanguage> {
  const detected = await detectLanguage(params.text, params.supportedLanguages);
  if (detected) return { language: detected, detected };
  if (params.preferredLanguage !== "auto") return { language: params.preferredLanguage, detected: null };
  return { language: params.defaultLanguage, detected: null };
}
