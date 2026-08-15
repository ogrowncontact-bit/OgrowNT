# INNER — Architecture Proposal (v0.1)

Status: **Draft for review** — no application code has been written yet. This document is the deliverable for the "first task" gate: analyze the product, propose the architecture, and wait for approval before building module by module.

Design inspiration note: reference points below (Typeform-style single-question flow, Co-Star/wellness-app editorial tone, dating-app-grade mobile polish) are named only to communicate a *feel*. Nothing is to be visually or structurally copied from any named product — INNER gets its own design language (see §9).

---

## 0. Product restatement (so we're aligned before diving in)

INNER is not a quiz app. It's a funnel-shaped **discovery engine**:

```
AD/SEARCH/SHARE → SPECIFIC EXPERIENCE (/love, /intimacy, ...) → ADAPTIVE AI CONVERSATION
 → FREE INSIGHT → CURIOSITY GAP → PAYWALL → EMAIL → PAYMENT → AI REPORT → PDF
 → NEXT DISCOVERY (contextual) → repeat with deeper profile
```

Two things make this hard, and they drive every decision below:

1. **It must feel like one intimate conversation, not a form** — while underneath it's a deterministic, auditable scoring system (AI is not allowed to be the sole source of truth, and must never diagnose).
2. **It must scale to N experiences without code changes** — the 10 launch experiences are *data*, not 10 separate codebases.

Everything in this proposal optimizes for those two constraints.

---

## 1. Technical architecture

### 1.1 Stack decision

| Layer | Choice | Why |
|---|---|---|
| App framework | **Next.js (App Router) + React + TypeScript** | SSR for fast first paint on ad-driven mobile traffic + SEO on public `/love` etc. landing routes; one deploy target for user app + admin. |
| Styling | **Tailwind CSS + Radix UI primitives** (headless) | Full control over the "premium editorial" look — no default component aesthetic to fight against. |
| Motion | **Framer Motion** | Subtle, fast screen transitions per the mobile UX spec. |
| Database | **PostgreSQL** | Relational integrity across identity/assessment/commerce/marketing boundaries (§12 needs real separation, not convention). |
| ORM | **Prisma** | Typed schema, migrations, good fit for a schema that will grow (admin-authored assessments). |
| Cache / queue | **Redis** (rate limiting, AI response cache, job queue for report generation) | Report generation (AI + PDF render) is async work that shouldn't block the checkout response. |
| Object storage | **S3-compatible (e.g. Cloudflare R2)** | Generated PDFs, served via short-lived signed URLs — never public. |
| AI provider | **Claude (Anthropic API)** — Sonnet for generation-quality steps (Report AI, nuanced follow-ups), a smaller/faster model for cheap classification (Response AI tagging) | Structured outputs (tool-use / JSON schema) throughout — see §4. |
| Payments | **Stripe**, behind a `PaymentProvider` interface | Abstracted per spec; Stripe Checkout keeps us out of PCI scope entirely. |
| Email | **Resend + React Email**, behind an `EmailProvider` interface | Transactional + marketing use the same renderer, different sending path/consent gate. |
| PDF rendering | **Playwright/Chromium, HTML→PDF** | Full typographic control for a "premium product," reuses the same design tokens as the web report. |
| Auth (users) | None (anonymous session token, see §12) | Per spec — no accounts. |
| Auth (admin) | **Clerk** (org/session already available in this environment) | Only surface that needs real login + RBAC. |
| Hosting | **Vercel** (Next app) + managed Postgres/Redis (Neon/Upstash or Railway) | Matches the connectors already in this environment; confirm before Phase 0 if you have a different preference. |
| Analytics sink | Internal Postgres `events` table as source of truth, optional pluggable forward to PostHog/GA4/Meta CAPI | Funnel truth must never depend on a third party we don't control. |

### 1.2 Module boundaries (monorepo)

```
apps/
  web/                  Next.js app — public experiences, checkout, report viewer, /admin route group
packages/
  assessment-engine/    Pure TS domain logic: session state machine, adaptive rule evaluator,
                         scoring calculator, profile matcher. Zero framework deps, fully unit-testable.
  ai/                   QuestionAI, ResponseAI, ProfileAI, ReportAI, RecommendationAI clients.
                         Owns prompts, schemas, guardrails, retries. Nothing outside this package
                         calls the model provider directly.
  db/                   Prisma schema, migrations, generated client, repository helpers.
  payments/             PaymentProvider interface + StripeProvider.
  email/                EmailProvider interface + ResendProvider + React Email templates.
  pdf/                  ReportRenderer: report JSON → HTML → PDF, template registry.
  analytics/            EventTracker interface + Postgres writer + pluggable sinks.
  ui/                   Shared design-system components (mobile-first question renderer, etc.)
  config/                shared eslint/tsconfig/tailwind config
```

**Rule that keeps this honest:** `apps/web` never imports the AI SDK, Stripe SDK, or Prisma client directly — only the package interfaces. No assessment-specific logic (e.g. "if slug === 'love'") is allowed anywhere in `apps/web` or `packages/ui`; that logic can only live as *data* inside `assessment-engine` configs. This is the mechanism that actually enforces "don't hard-code around these 10 experiences."

### 1.3 Request-time flow (assessment taking)

```
Client (mobile) ── POST /api/sessions/start {slug, utm}
                          → creates anonymous_session + assessment_session, sets HttpOnly cookie
Client ── POST /api/sessions/:id/answer {question_id, answer}
                          → assessment-engine: record response → run adaptive rules
                          → if rule says "ask AI follow-up": ai.questionAI.generateFollowup()
                          → returns next question (core, branched, or AI-generated) + progress
... repeats until engine says "complete" (confidence + max-question safeguards, §5) ...
Client ── POST /api/sessions/:id/complete
                          → scoring engine computes dimension_scores → profile match
                          → ai.profileAI.annotate() adds semantic notes (bounded influence)
                          → returns FREE result (primary profile + 1 insight + locked-count)
Client ── paywall → POST /api/checkout {session_id, product}
                          → Stripe Checkout session → redirect
Stripe webhook ── payment_intent.succeeded
                          → order.paid → entitlement granted → enqueue report job
Worker ── ai.reportAI.generate() per section → pdf.render() → upload → email.sendReport()
Client ── polls / gets emailed link → report viewer page (web) + PDF
```

Everything before payment is synchronous and cheap (must stay inside the 4–7 min target). Report generation is the one place we go async, because premium per-section AI generation + PDF rendering can take longer than a mobile user should wait staring at a spinner — we show a tasteful "preparing your profile" state and deliver by email regardless.

---

## 2. Database schema

Modeled as separate Postgres **schemas** (not just tables) so the privacy separation in the spec (identity / assessment / purchase / marketing) is structural, not a naming convention — it lets us apply different access grants and different deletion routines per schema.

### `identity`
- `anonymous_sessions(id, created_at, last_seen_at, first_landing_slug, utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer, ip_hash, ua_hash, user_id NULL)`
- `users(id, email UNIQUE, email_verified_at, stripe_customer_id NULL, created_at)`
- `deletion_requests(id, user_id, requested_at, status, completed_at)`

`ip_hash`/`ua_hash` (salted hash, not raw) — enough for fraud/rate-limit heuristics without storing raw PII we don't need.

### `catalog` (admin-authored, versioned content — this is what makes new experiences data-only)
- `assessments(id, slug UNIQUE, name, category, description, hook, target_audience, status[draft|published|archived], current_version_id, created_at, updated_at)`
- `assessment_versions(id, assessment_id, version_number, config_snapshot JSONB, published_at, created_by)`
- `dimensions(id, key UNIQUE, label, description)` — global reusable pool (Connection, Independence, Trust, ...)
- `assessment_dimensions(assessment_version_id, dimension_id, weight_config JSONB)`
- `questions(id, assessment_version_id, key, type[single_select|multi_select|scale|open_text], is_core BOOL, prompt, order_hint, metadata JSONB)`
- `question_options(id, question_id, key, label, dimension_contributions JSONB)` — `{dimension_key: weight}`
- `adaptive_rules(id, assessment_version_id, trigger JSONB, action JSONB, priority)`
- `profiles(id, assessment_version_id, key, name, description_template, matching_rule JSONB)`
- `report_templates(id, assessment_version_id, sections JSONB)` — ordered `{key, title, prompt_ref}`
- `recommendation_rules(id, from_assessment_id, to_assessment_id, condition JSONB, weight)`
- `prices(id, assessment_id, product_type[individual|deep|bundle|couple|master], amount_cents, currency, active BOOL, effective_from)`

### `runtime` (a user's actual pass through an assessment — sensitive, access-restricted)
- `assessment_sessions(id, anonymous_session_id, assessment_id, assessment_version_id, status[in_progress|completed|abandoned], started_at, completed_at, question_count, source_slug)`
- `responses(id, assessment_session_id, question_id, selected_option_ids JSONB, answered_at, response_time_ms)`
- `open_responses(id, assessment_session_id, question_id, raw_text_encrypted, ai_tags JSONB, ai_sentiment, safety_flag BOOL, created_at)` — encrypted column, never joined into analytics
- `ai_followups(id, assessment_session_id, triggered_by_question_id, generated_text, generated_options JSONB, reason_code, created_at)`
- `dimension_scores(id, assessment_session_id, dimension_key, raw_score, normalized_score, confidence)`
- `profile_results(id, assessment_session_id, primary_profile_id, secondary_profile_ids JSONB, ai_semantic_notes JSONB, computed_at)`

### `commerce`
- `orders(id, user_id, assessment_session_id, price_id, product_type, amount_cents, currency, status[pending|paid|refunded|failed], provider, provider_ref, created_at, paid_at)`
- `entitlements(id, user_id, assessment_session_id, order_id, report_id, granted_at, expires_at NULL)`
- `reports(id, assessment_session_id, order_id, template_version, content JSONB, pdf_object_key, generated_at, delivered_at)`
- `refunds(id, order_id, amount_cents, reason, created_at)`

### `marketing`
- `marketing_consents(id, user_id, consent BOOL, consent_timestamp, consent_version, consent_source, campaign, assessment_id)`
- `email_events(id, user_id, type, template_key, sent_at, opened_at, clicked_at)`
- `unsubscribes(id, user_id, scope[all|recommendations], unsubscribed_at)`

### `analytics`
- `events(id, occurred_at, anonymous_session_id, user_id NULL, event_name, assessment_id NULL, properties JSONB, utm_source, utm_medium, utm_campaign, utm_content, utm_term)` — append-only, partitioned by month. **Never** contains `raw_text` or option-level answer content beyond dimension deltas.

### `admin`
- `admin_users(id, email, role[owner|editor|viewer], created_at)`
- `audit_log(id, admin_user_id, action, entity_type, entity_id, diff JSONB, created_at)`

GDPR deletion is then a defined operation per schema: hard-delete `identity` + `runtime` rows for a user, anonymize (not delete) `analytics.events` (strip `user_id`/`anonymous_session_id`, keep aggregate value), retain `commerce` rows as required by tax law but detach PII (keep only what invoicing legally requires).

---

## 3. Assessment data model

This is the contract every one of the 10 (and future N) experiences must satisfy — expressed as the shape stored in `assessment_versions.config_snapshot` and mirrored by admin forms:

```ts
interface AssessmentConfig {
  id: string
  slug: string                     // "/love"
  name: string                     // "How Do You Love?"
  category: string
  description: string
  hook: string                     // landing page emotional hook copy
  targetAudience: string
  dimensions: DimensionRef[]       // subset of the global dimension pool + weight config
  questionBank: {
    core: Question[]               // always-asked, ordered
    adaptivePool: Question[]       // candidates for AI/rule-triggered follow-ups
  }
  adaptiveRules: AdaptiveRule[]    // deterministic branch/stop conditions (see §5)
  openQuestions: OpenQuestionSlot[]  // where + how many open-text prompts are allowed
  scoringModel: {
    dimensionWeights: Record<DimensionKey, number>
    normalization: "min-max" | "z-score"
    aiInfluenceCap: number         // max % a semantic signal may shift a score (see §6)
  }
  profiles: ProfileDefinition[]    // possible primary/secondary archetypes + matching rule
  freeResultTemplate: FreeResultTemplate
  premiumReportStructure: ReportSection[]
  recommendedNext: { assessmentSlug: string; condition: RecommendationCondition; weight: number }[]
  pricing: { productType: string; priceRefId: string }[]
  status: "draft" | "published" | "archived"
  version: number
  minQuestions: number
  recommendedQuestions: number
  maxQuestions: number
}
```

Because `dimensions` are references into a **shared global pool**, scores are comparable across assessments from day one — this is what makes a later "INNER Master Profile" (blend of everything a user has taken) possible without a data migration.

The 10 launch experiences are 10 rows in `catalog.assessments` + JSON config, authored via seed scripts initially and via the admin builder later (§10). No code path branches on slug.

---

## 4. AI architecture

Five narrow, independently-versioned services, each with a strict input/output contract. **None of them talk to the model provider except through `packages/ai`**, and every call uses structured/tool-constrained output — free-text model output is never parsed by hand or shown to the user unfiltered.

| Module | Input | Output | Notes |
|---|---|---|---|
| **Question AI** | current session state, last answer, dimension confidence map | either "no follow-up" or a follow-up question drawn from / shaped by the assessment's `adaptivePool`, with 3–5 structured options + optional open variant | Constrained to the assessment's own pool + topic guardrails — it selects/adapts, it does not freely invent new psychological territory. |
| **Response AI** | raw open-text answer + question context | semantic tags, sentiment, 1–3 dimension "nudges" (bounded magnitude), safety_flag (crisis-language detector) | Cheapest/fastest model tier; runs on every open answer. |
| **Profile AI** | structured `dimension_scores` + all semantic tags/notes for the session | non-diagnostic annotation: which profile fits best (must agree with the deterministic matcher, can only choose among candidates it returns, not invent new profiles), 1 "meaningful insight" sentence for the free result | Structured scores are always computed first (§6); Profile AI explains/labels, it doesn't decide the number. |
| **Report AI** | full profile + scores + section spec from `premiumReportStructure` | personalized copy per section, generated one section at a time against that section's own prompt + word budget + banned-phrase list | Output runs through the **language-safety filter** (§4.1) before storage. |
| **Recommendation AI** | user's profile(s), assessment history, `recommendedNext` candidates from config | 1 sentence of contextual narrative bridging the just-completed pattern to the next experience + which candidate to lead with | Cannot recommend an assessment that isn't already a config-approved candidate — it writes the copy, not the graph. |

### 4.1 Guardrails (apply to every module, enforced in code, not just prompt instructions)

- **Non-diagnostic language filter**: a post-generation check that rejects/rewrites output containing clinical/absolute phrasing ("you are...", "you have...", "you suffer from...", any DSM-style term) and requires hedged framing ("your responses suggest...", "one pattern in your answers is..."). Implemented as a deterministic regex/lint pass over AI output before it's ever persisted — the prompt instructs this too, but we don't trust the model alone.
- **Topic containment**: system prompts + a fixed pool of assessment-approved follow-up templates keep Question AI from wandering into unrelated or higher-risk territory (e.g., a `/love` session drifting into unrelated medical topics).
- **Prompt-injection resistance**: user open-text is *data*, never concatenated into a role that has instruction-following authority. It's always passed as a clearly delimited, labeled user-content block; system prompts explicitly state that content inside that block is never to be treated as instructions.
- **Crisis-language safety net**: Response AI's `safety_flag` (self-harm, abuse, danger language) triggers a fixed, non-AI-generated support-resources message in the UI — this bypasses the AI pipeline entirely; INNER is not equipped to handle this itself, so it doesn't try.
- **Every AI output is versioned and logged** (prompt version + model version + output) so report quality/regressions are auditable — this doubles as the eval harness substrate.

### 4.2 Cost & latency strategy
- Question/Response AI use a fast, cheap model tier (sub-second target) since they sit in the critical path of the live conversation.
- Report AI runs **async**, post-payment, section-by-section (parallelizable), so we never trade report quality for chat latency.
- Redis-backed response caching for identical (question, prior-answer-pattern) pairs where safe, to cut redundant generation cost at scale.

---

## 5. Adaptive-question architecture

Core loop, evaluated after every answer by the (non-AI) **adaptive rule evaluator** in `assessment-engine`:

```
answer recorded
  → update dimension_scores + confidence per affected dimension
  → evaluate adaptive_rules in priority order:
       - CONTRADICTION/AMBIGUITY rule matched → ask specific follow-up (Question AI shapes it)
       - STRONG SIGNAL rule matched → ask deeper question on that dimension
       - none matched → advance to next core question
  → check stop conditions:
       - questions_asked >= maxQuestions → force stop
       - questions_asked >= minQuestions AND avg(confidence) >= threshold → offer stop
       - questions_asked >= recommendedQuestions AND no pending high-priority rule → stop
  → return next question OR mark session complete
```

- **Rules are deterministic and declarative** (`trigger: {dimension, condition}` → `action: {ask_followup_pool_key | increase_confidence | skip}`), stored per assessment version. AI's role is narrower than "decide what to ask next" — it *phrases/selects* within a rule-approved slot, which keeps the system debuggable and keeps runaway AI-invented interrogation off the table.
- Hard safeguards: `minQuestions`/`recommendedQuestions`/`maxQuestions` per assessment (spec target: finish in ~4–7 min, roughly translates to ~12–18 questions depending on mix of select vs. open). Open-text prompts are capped separately (e.g. max 2 per assessment) regardless of rule triggers, so personalization never becomes fatigue.
- Every follow-up shown to the user still degrades gracefully to structured options ("My independence / My emotions / My sense of control / Myself from rejection / I'm not sure / Something else") — open-ended is additive, never the only path, per the spec's structured+open requirement.

---

## 6. Scoring architecture

```
STRUCTURED LAYER (source of truth)
  each selected option → weighted contribution to 1+ dimensions (question_options.dimension_contributions)
  → summed per dimension → normalized 0–100 (min-max within the assessment's configured range)
  → confidence per dimension = f(number of contributing answers, agreement/consistency)

SEMANTIC LAYER (adjustment, capped)
  Response AI nudges ("this open answer leans toward protecting independence, magnitude 0.4")
  → applied as a bounded delta (± aiInfluenceCap%, e.g. max 15% of a dimension's score)
  → never allowed to flip a profile match on its own — it can shade a borderline case, not invent one

PROFILE MATCHING
  profiles.matching_rule: threshold/range rules over normalized dimension scores
  (e.g. Connection > 70 AND Independence > 65 → "The Independent Connector")
  → deterministic nearest-match / rule evaluation picks primary profile
  → secondary profiles = next-closest matches above a relevance floor
  → Profile AI is handed the *already-decided* primary/secondary set to narrate, not to choose
```

This ordering — structured math first, AI narrates second, AI influence numerically capped — is what satisfies "AI must not be the only source of truth" and "AI must not freely diagnose": the diagnosis-shaped decision (which profile) is arithmetic and auditable; AI's job is expressive, not decisional.

Scores are stored normalized against the shared global dimension pool (§3), so a later cross-assessment "INNER Master Profile" is a weighted blend of existing `dimension_scores` rows — no redesign needed, just a new aggregation query.

---

## 7. Report generation architecture

- `report_templates.sections` (configurable per assessment) defines the section list — spec gives the default 10 (Signature, dominant pattern, how you connect, what you may need, how you may react, strengths, friction points, what others may perceive, reflection questions, personalized conclusion), but each assessment can reorder/customize.
- Generation pipeline (async worker, triggered by `order.paid`):
  1. Load profile + scores + semantic notes + section spec.
  2. For each section, call Report AI with that section's own prompt + a word budget + the non-diagnostic phrasing rules.
  3. Run the language-safety filter (§4.1) on each section's output.
  4. Assemble into a `reports.content` JSON document (source of truth — the PDF is a rendering of this, not the other way around, so we can also show it in-browser).
  5. Render to HTML using the same design tokens as the web report viewer → Playwright → PDF → upload to object storage.
  6. Mark `entitlements` active, email the user (transactional path) with a signed, short-lived download link + the report also viewable at a private URL tied to their session/email.
- Template registry in `packages/pdf` is generic — it takes a `content` JSON + a layout config, so a new assessment's report "just works" once its `report_templates` row exists.
- Reports are versioned (`template_version`) so we can regenerate/upgrade older reports without breaking already-delivered ones.

---

## 8. Recommendation engine

Three inputs blended, in this priority:

1. **Config graph** (`catalog.recommendation_rules`): admin-declared "assessment A commonly leads to B/C" edges with a condition (e.g. "if Independence and Connection both score high").
2. **Dimension similarity**: cosine-similarity-ish comparison between the user's current dimension scores and other assessments' dimension footprints, to catch patterns the admin didn't explicitly wire.
3. **History/behavior**: previous assessments taken, previous purchases, recency — deprioritize an experience already completed; boost one that complements what's missing from their profile so far.

The **Recommendation AI** only writes the 1–2 sentence bridge narrative ("Your answers showed an interesting relationship between independence and connection. Would you like to explore how this pattern appears in intimacy?") over a candidate the deterministic blend already selected — this keeps recommendations feeling contextual rather than like served ads, while guaranteeing the AI can't recommend something irrelevant or not-yet-published.

**Explore INNER** is a separate, always-available surface (not the default post-completion screen) that lists the full published catalog — satisfies "progressive discovery by default, full catalog on demand."

---

## 9. Mobile-first UX architecture

### 9.1 Core interaction model
- **One question per screen**, full-viewport, single primary action. Structured options render as large tappable cards (not tiny radio buttons); open-text uses an autosizing textarea with a keyboard-safe sticky "Continue" CTA that respects `visualViewport` on iOS so the button never hides behind the keyboard.
- Persistent, unobtrusive **progress bar + "Question X of ~Y"** (Y is the `recommendedQuestions` estimate, not a false promise, since actual count is adaptive — copy reads "About X questions left" rather than a hard number past the core set).
- Transitions: short (150–200ms), directional (forward = slide+fade), never blocking input.
- Design tokens: generous type scale (question text large enough to read one-handed at arm's length), high-contrast but warm neutral palette, no default component-library look — closer to an editorial/print feel than a "SaaS dashboard" or "dating app," per spec's explicit avoid-list.
- Breakpoints validated at 360/375/390/414px as the primary design surface; desktop is a centered, capped-width rendering of the same layout (not a separate design).

### 9.2 Screen inventory (per experience)
```
/[slug]  → landing (hook, single "Begin" CTA, no pricing yet, no catalog)
/[slug]/session/[id] → one-question-per-screen adaptive flow
/[slug]/session/[id]/result → free result + curiosity gap + locked-insights teaser
/[slug]/session/[id]/paywall → elegant paywall (what's known / what's included / price / delivery)
/[slug]/session/[id]/checkout → email capture (+ separate marketing opt-in checkbox) → Stripe
/[slug]/session/[id]/report → premium report viewer (post-payment) + PDF download + recommendation card
/explore → full catalog (opt-in discovery)
```
- Component system: a generic `QuestionRenderer` that switches on `question.type` (single_select/multi_select/scale/open_text) — this is the component that must never know what assessment it's in, enforcing the "no assessment-specific logic in generic components" rule from §1.2.
- Accessibility: WCAG AA target — large touch targets (≥44px), sufficient contrast, screen-reader labels on option cards, reduced-motion respect.

---

## 10. Admin architecture

- Lives at `/admin` inside the same Next app, gated by Clerk auth + `admin.admin_users.role` (owner/editor/viewer) middleware — kept in-app initially rather than a separate service, split out later only if it earns it.
- **Assessment builder**: schema-driven CRUD over `catalog.*` — dimensions picker, question bank editor (core + adaptive pool), adaptive rule editor (condition/action builder, not raw JSON for common cases), profile/matching-rule editor, report section editor, pricing editor, recommendation graph editor.
- **Draft → Published → Archived** lifecycle per `assessment_versions` — edits happen on a draft version; publishing snapshots the config so in-flight user sessions never see a config change mid-assessment.
- Read-only views: sessions/funnel per assessment, purchases/refunds, marketing consent stats — deliberately **not** a raw-answer browser; open-text content is not surfaced in bulk admin views (§12), only in narrow, audited per-session support lookups if ever needed.
- Every write goes through `admin.audit_log` (who changed what, diff, when).
- This is exactly the surface that lets a non-engineer add experience #11 without a deploy.

---

## 11. Analytics architecture

- Every funnel event from the spec (`landing_view` … `next_purchase`) is a row in `analytics.events`, written server-side (not purely client-fired, so ad-blockers/JS failures don't blind the funnel) with `assessment_id`, `anonymous_session_id`, `user_id` (once known), UTM fields, and a small `properties` JSONB (event-specific, never raw answer text).
- Funnel/conversion dashboards are SQL views/materialized rollups over `events`, sliced by assessment + UTM — this is what the admin analytics screen reads.
- Optional pluggable forwarding (`packages/analytics` sinks) to PostHog/GA4/Meta CAPI for ad-platform optimization — internal Postgres stays the source of truth regardless, since ad accounts get suspended/reset and shouldn't take our funnel history with them.
- Hard boundary: analytics events are structurally incapable of carrying `open_responses.raw_text` — there's no column for it, not just a policy against populating one.

---

## 12. Security & privacy concerns

- **Structural PII separation** (§2 schemas) so a breach or a bad query in one domain can't casually leak another — e.g., an analytics dashboard query literally cannot join to `raw_text`.
- **Encryption at rest** for `open_responses.raw_text` and `users.email`; TLS everywhere; secrets in a managed vault, never in repo/config.
- **Anonymous session = signed opaque token** in an HttpOnly, Secure cookie — no password, but still needs CSRF protection on state-changing endpoints and rate limiting (Redis) keyed by session/IP-hash to stop scripted assessment farming.
- **GDPR mechanics**: explicit, versioned, timestamped marketing consent (never inferred from "email given at checkout" — spec is explicit about this); self-serve or support-assisted **export** (Art. 20) and **deletion** (Art. 17) covering identity + runtime schemas, with commerce data anonymized-but-retained where tax law requires; unsubscribe is one click and updates `marketing.unsubscribes`, checked before every marketing send.
- **PCI scope avoidance**: card data never touches our servers — Stripe Checkout/Elements only.
- **Prompt-injection defense** (§4.1) — required specifically because this product invites long, personal, freeform text from users, which is exactly the injection surface.
- **Crisis-language safety net** (§4.1) — this product's subject matter (intimacy, vulnerability, jealousy) makes this not optional.
- **Content moderation on open-text** beyond crisis detection — basic abuse/spam filtering before anything is stored or sent to a model.
- **Age gate**: intimacy/vulnerability/jealousy content plus payment collection means we need an explicit 18+ (or at minimum 16+ with jurisdiction-aware handling) affirmation at entry — flagged as a genuine gap, see §14.
- **Report delivery security**: signed, short-lived URLs for PDFs, not permanently public object-storage links; report viewer page requires the session token or a magic-link tied to the purchasing email.

---

## 13. Risks in the product concept

- **AI cost/latency at scale**: every live question and every report section is a model call; needs real budget modeling before ad spend scales up, plus the caching/async strategy in §4.2 — without it, unit economics on a €7.99 report are fragile.
- **Report quality consistency / hallucination**: a "premium personalized report" that reads generically or gets a detail wrong breaks the entire value proposition; needs the eval harness implied by §4.1's versioned-output logging, ideally with human spot-review before wide launch.
- **Legal/positioning risk**: relationship/intimacy/psychological framing sits close to lines around health/medical claims on ad platforms (Meta/Google) and in some jurisdictions — non-diagnostic language (§4.1) is necessary but the marketing copy and ad creative need the same discipline, or the ad accounts get flagged regardless of what the app itself says.
- **Ad platform content policy**: `/intimacy`, `/jealousy` etc. as ad-driven landing pages may trip dating/relationship/sexual-content ad policies — worth a policy review before the media buy, independent of the product build.
- **Abuse/bot farming of free assessments**: no account + free entry point is exactly the shape bad actors farm for scraped content or ad-fraud; rate limiting (§12) is necessary but should be budgeted as ongoing, not one-time.
- **Value-gap risk in the free result**: if the free insight is too thin, conversion suffers; if it's too generous, nobody pays — this is a tuning problem that needs real user data, not something architecture alone solves, but the config-driven `freeResultTemplate` (§3) at least makes it iterable without a deploy.
- **Cross-experience cannibalization**: 10 separate €7.99 purchases is a harder sell than it looks; bundle/master-profile pricing is listed as "future" in the spec but the recommendation engine's whole value depends on repeat purchase — worth sequencing bundle pricing earlier than "future" if early data shows single-report repeat-purchase is weak.
- **Sensitive-topic support burden**: users disclosing real emotional distress in open-text will happen at some volume; the crisis safety net (§12) needs an actual owned process behind it (who/what happens when flagged), not just a UI message.

---

## 14. Gaps in the spec (things to decide before/soon after Phase 0)

- **Age gate / minimum age policy** — not specified; recommended before intimacy-adjacent content goes live with payment collection.
- **Terms of Service / Privacy Policy content** — referenced implicitly by GDPR requirements but not drafted; needed before real payment/email collection.
- **Localization** — spec is written in English/EUR; is launch single-market (EN, €) or multi-language from day one? Affects question-bank and AI-prompt structure now vs. later.
- **Refund policy** — €7.99/€12.99 digital goods; need an explicit policy (esp. since EU consumer law has specific digital-content withdrawal rules).
- **Abandoned-session re-engagement** — spec covers the happy path funnel; no mention of recovering a user who starts but doesn't finish, or finishes free but doesn't buy. Recommend at least an optional-email-capture-earlier experiment or an on-page nudge, decided later with data.
- **Session continuity across devices** — user starts on phone via ad, might want to open the emailed report on desktop later; the email-linked report viewer (§9.1) covers this, but resuming an *in-progress* assessment cross-device isn't specified — recommend: not supported at launch (assessments are short enough that this is low priority).
- **Multi-currency** — `prices` table (§2) supports it structurally; go-to-market currency scope needs a decision.
- **A/B testing / experimentation** — paywall copy, price points, and free-result generosity are all things worth testing; not in spec, but the config-driven model (§3) makes it feasible to bolt on later (e.g. a `variant` field) without a redesign.
- **Support flow** — "I didn't receive my report," "my payment failed but I was charged" — needs an owned channel (even just a monitored inbox) before launch.
- **Testing/eval strategy for AI outputs** — implied by the guardrails in §4.1 but not an explicit deliverable; recommend a small golden-set of session transcripts we regression-test report/question generation against whenever prompts change.

I'd like your input on the age-gate and localization questions specifically since they affect the data model (age gate) and content authoring workload (localization) from Phase 1 onward — everything else above I'm comfortable making a default call on and revisiting later.

---

## 15. Phased implementation plan

| Phase | Scope | Exit criteria |
|---|---|---|
| **0 — Foundations** | Monorepo scaffold, CI, Prisma schema + migrations for all 5 schemas, design tokens, legal-page skeletons, env/config setup | `pnpm build` green, empty app deploys, schema migrated on a real Postgres instance |
| **1 — Assessment engine core (no AI yet)** | `assessment-engine` package, seed config for `/love` only, deterministic adaptive rules (no AI follow-ups yet), scoring + profile matching, one-question-per-screen UI, free result screen | A user can complete `/love` end-to-end on mobile and see a correct, deterministic free result |
| **2 — AI layer** | Question AI + Response AI wired into the live flow, guardrails (§4.1), Profile AI annotation, eval harness/golden set | `/love` follow-ups feel adaptive; non-diagnostic filter verified against a test set of edge-case answers |
| **3 — Commerce + reports** | Email capture with explicit marketing consent, Stripe Checkout, entitlements, Report AI + PDF pipeline, transactional email delivery | Real €7.99 purchase on `/love` produces a delivered, correctly-branded PDF |
| **4 — Recommendation + catalog breadth** | Recommendation engine (rules + similarity + AI narrative), author remaining 9 experiences as config, Explore Mode | All 10 slugs live; completing one experience produces a contextual next-experience prompt |
| **5 — Admin** | Assessment builder UI, draft/publish lifecycle, funnel/purchase dashboards, audit log | A non-engineer can create experience #11 from the admin without a deploy |
| **6 — Growth tooling** | Analytics sink forwarding, abandoned-session re-engagement, referral/sharing, experimentation scaffolding | Funnel dashboards match ad-platform numbers within an agreed tolerance |
| **7 — Hardening** | Security review, GDPR export/delete self-serve, accessibility audit, AI cost/latency monitoring, load test | Passes an explicit security/privacy review before scaling ad spend |
| **8 — Future (per spec)** | Bundles, couple experiences, INNER Master Profile, localization, native app | — |

Each phase is meant to ship something real and demoable, not a layer with nothing to look at — Phase 1 in particular is deliberately AI-free so we validate the mobile UX and scoring model on solid ground before adding AI's cost and variability on top.

---

## Open decision before I start Phase 0

Confirm or redirect on:
1. Hosting/infra defaults in §1.1 (Vercel + managed Postgres/Redis, Clerk for admin) — go with these, or do you have existing infra preferences?
2. Age gate + localization scope (§14) — comfortable deferring both to "English/EUR, 18+ affirmation, decide localization later" unless you want it decided differently now.

Everything else in this document I'm treating as approved-by-default unless you flag it — let me know and I'll start Phase 0.
