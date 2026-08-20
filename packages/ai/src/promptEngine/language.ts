export const SUPPORTED_REPORT_LANGUAGES = ["en", "es", "pt"] as const;
export type ReportLanguage = (typeof SUPPORTED_REPORT_LANGUAGES)[number];
// Architecture-ready, not yet wired to real generation — see resolvedLanguage() callers.
export const PLANNED_REPORT_LANGUAGES = ["fr", "it", "de", "nl"] as const;

export const LANGUAGE_NAMES: Record<ReportLanguage, string> = { en: "English", es: "Spanish", pt: "Portuguese" };

export function resolvedLanguage(language: string): ReportLanguage {
  return (SUPPORTED_REPORT_LANGUAGES as readonly string[]).includes(language) ? (language as ReportLanguage) : "en";
}

/** Empty for English (the model's native default) — non-English always gets an explicit native-voice instruction, never a mechanical translation. */
export function languageInstruction(language: ReportLanguage): string {
  if (language === "en") return "";
  return ` Write your ENTIRE response naturally in ${LANGUAGE_NAMES[language]}, as a native speaker would write it — never a mechanical word-for-word translation from English.`;
}
