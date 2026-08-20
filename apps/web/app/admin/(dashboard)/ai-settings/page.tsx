import { isAiEnabled, DEFAULT_MODEL_CONFIG } from "@inner/ai";
import { getAdminSession } from "@/lib/adminAuth";
import { getAiModelConfig } from "@/lib/aiConfig";
import { AiSettingsForm } from "@/components/admin/AiSettingsForm";

export const dynamic = "force-dynamic";

export default async function AdminAiSettingsPage() {
  const [session, config] = await Promise.all([getAdminSession(), getAiModelConfig()]);
  const readOnly = session?.role === "viewer";

  return (
    <div>
      <h1 className="font-display mb-2 text-[24px] text-[var(--inner-ink)]">AI Settings</h1>
      <p className="mb-6 max-w-lg text-[13px] text-[var(--inner-ink-soft)]">
        Controls which Claude models the interpretation engine calls, and how much room each call gets. This never
        changes what the AI is allowed to say — the guardrails, the non-diagnostic filter, and the deterministic
        scoring engine are unaffected by anything here. The API key itself is an environment variable and is never
        shown or editable from this screen.
      </p>

      <div className="mb-6 rounded-[var(--inner-radius-lg)] border border-[var(--inner-line)] bg-[var(--inner-card)] p-4 text-[13px]">
        <span className="text-[var(--inner-muted)]">AI status: </span>
        {isAiEnabled() ? (
          <span className="text-[var(--inner-ink)]">enabled (ANTHROPIC_API_KEY is set)</span>
        ) : (
          <span className="text-[var(--inner-accent)]">
            disabled — no ANTHROPIC_API_KEY in this environment. Every AI call is degrading to its deterministic
            fallback.
          </span>
        )}
      </div>

      <AiSettingsForm
        initial={{
          fastModel: config.fastModel || DEFAULT_MODEL_CONFIG.fastModel,
          qualityModel: config.qualityModel || DEFAULT_MODEL_CONFIG.qualityModel,
          temperature: config.temperature,
          maxTokens: config.maxTokens,
          timeoutMs: config.timeoutMs,
        }}
        readOnly={readOnly}
      />
    </div>
  );
}
