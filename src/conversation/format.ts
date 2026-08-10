import type { Prisma } from "@prisma/client";
import { enUS, es, ptBR, type Locale } from "date-fns/locale";
import { formatInTimeZone } from "date-fns-tz";

const DATE_FNS_LOCALES: Record<string, Locale> = { pt: ptBR, en: enUS, es };
const INTL_LOCALE_TAGS: Record<string, string> = { pt: "pt-BR", en: "en-US", es: "es-ES" };
const LONG_DATE_PATTERNS: Record<string, string> = {
  pt: "d 'de' MMMM 'as' HH:mm",
  es: "d 'de' MMMM 'a las' HH:mm",
  en: "MMMM d 'at' h:mm a",
};

// Formato compacto e numerico (sem nomes de mes/dia) - usado nos titulos de
// linha de listas do WhatsApp, que tem limite de 24 caracteres. Nao depende
// de idioma de proposito: numeros sao universais e cabem no limite.
export function formatSlotShort(date: Date, timeZone: string): string {
  return formatInTimeZone(date, timeZone, "dd/MM HH:mm");
}

// Formato por extenso, sensivel a idioma - usado em textos de confirmacao e
// nas respostas da IA, onde nao ha limite de caracteres e uma data legivel
// melhora a experiencia.
export function formatSlotLong(date: Date, timeZone: string, language: string): string {
  const locale = DATE_FNS_LOCALES[language] ?? DATE_FNS_LOCALES.pt;
  const pattern = LONG_DATE_PATTERNS[language] ?? LONG_DATE_PATTERNS.pt;
  return formatInTimeZone(date, timeZone, pattern, { locale });
}

export function formatPrice(price: Prisma.Decimal | null, currency: string, language: string): string | null {
  if (price === null) return null;
  const localeTag = INTL_LOCALE_TAGS[language] ?? INTL_LOCALE_TAGS.pt;
  return price.toNumber().toLocaleString(localeTag, { style: "currency", currency });
}
