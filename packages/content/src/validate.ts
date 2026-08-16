import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * Static content-correctness checks that Prisma's schema constraints don't
 * catch — dangling references between hand-authored questions, rules, and
 * profiles within one AssessmentConfig. Nothing here needs a database or a
 * live server; it's meant to catch typos the moment a config is authored.
 */
export function validateAssessmentConfig(config: AssessmentConfig): string[] {
  const violations: string[] = [];
  const allQuestions = [...config.questionBank.core, ...config.questionBank.adaptivePool];
  const questionKeys = new Set(allQuestions.map((q) => q.key));
  const adaptivePoolKeys = new Set(config.questionBank.adaptivePool.map((q) => q.key));
  const dimensionKeys = new Set(config.dimensions.map((d) => d.key));

  const dupQuestionKeys = allQuestions.map((q) => q.key).filter((k, i, arr) => arr.indexOf(k) !== i);
  if (dupQuestionKeys.length > 0) violations.push(`duplicate question key(s): ${[...new Set(dupQuestionKeys)].join(", ")}`);

  for (const q of allQuestions) {
    if (q.options) {
      const optKeys = q.options.map((o) => o.key);
      const dupOpts = optKeys.filter((k, i, arr) => arr.indexOf(k) !== i);
      if (dupOpts.length > 0) violations.push(`question "${q.key}": duplicate option key(s) ${dupOpts.join(", ")}`);
      for (const o of q.options) {
        for (const dimKey of Object.keys(o.dimensionContributions)) {
          if (!dimensionKeys.has(dimKey)) {
            violations.push(`question "${q.key}" option "${o.key}": contributes to undeclared dimension "${dimKey}"`);
          }
        }
      }
    }
    if (q.type === "scale" && q.scaleDimension && !dimensionKeys.has(q.scaleDimension)) {
      violations.push(`question "${q.key}": scaleDimension "${q.scaleDimension}" is not a declared dimension`);
    }
    for (const candidateKey of q.dynamicFollowupCandidates ?? []) {
      if (!adaptivePoolKeys.has(candidateKey)) {
        violations.push(`question "${q.key}": dynamicFollowupCandidates references unknown adaptivePool question "${candidateKey}"`);
      }
    }
  }

  for (const rule of config.adaptiveRules) {
    if (!questionKeys.has(rule.trigger.questionKey)) {
      violations.push(`rule "${rule.key}": trigger.questionKey "${rule.trigger.questionKey}" does not exist`);
      continue;
    }
    if (rule.trigger.op === "answered_option") {
      const question = allQuestions.find((q) => q.key === rule.trigger.questionKey);
      const hasOption = question?.options?.some((o) => o.key === rule.trigger.optionKey);
      if (!hasOption) {
        violations.push(
          `rule "${rule.key}": trigger.optionKey "${rule.trigger.optionKey}" does not exist on question "${rule.trigger.questionKey}"`
        );
      }
    }
    if (rule.action.type === "ask_followup") {
      if (!rule.action.followupQuestionKey || !adaptivePoolKeys.has(rule.action.followupQuestionKey)) {
        violations.push(`rule "${rule.key}": action.followupQuestionKey "${rule.action.followupQuestionKey}" is not in adaptivePool`);
      }
    }
  }

  const profileKeys = config.profiles.map((p) => p.key);
  const dupProfileKeys = profileKeys.filter((k, i, arr) => arr.indexOf(k) !== i);
  if (dupProfileKeys.length > 0) violations.push(`duplicate profile key(s): ${[...new Set(dupProfileKeys)].join(", ")}`);

  for (const profile of config.profiles) {
    for (const dimKey of Object.keys(profile.matchingRule.dimensionRanges)) {
      if (!dimensionKeys.has(dimKey)) {
        violations.push(`profile "${profile.key}": matchingRule references undeclared dimension "${dimKey}"`);
      }
    }
  }

  for (const candidate of config.recommendedNext) {
    if (candidate.assessmentSlug === config.slug) {
      violations.push(`recommendedNext: self-references "${config.slug}"`);
    }
    for (const dimKey of Object.keys(candidate.condition.dimensionRanges)) {
      if (!dimensionKeys.has(dimKey)) {
        violations.push(`recommendedNext -> "${candidate.assessmentSlug}": condition references undeclared dimension "${dimKey}"`);
      }
    }
  }

  return violations;
}
