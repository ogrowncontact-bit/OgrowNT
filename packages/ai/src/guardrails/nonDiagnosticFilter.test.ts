import { describe, expect, it } from "vitest";
import { enforceNonDiagnostic } from "./nonDiagnosticFilter";

describe("enforceNonDiagnostic", () => {
  const clean = [
    "Your responses suggest you tend to value independence.",
    "One pattern in your answers is a tendency to protect your independence.",
    "You appear to value deep connection over reassurance.",
    "Your responses may indicate a preference for slow-building trust.",
  ];

  const rewritableThenClean = [
    "You are someone who values independence.",
    "You have a pattern of pulling away when things intensify.",
    "You're quick to reassure people close to you.",
  ];

  const hardBanned = [
    "This may indicate an attachment disorder.",
    "Your responses may indicate narcissistic tendencies.",
    "Some people might describe this as codependent.",
    "You suffer from unresolved trauma.",
    "A clinical read of your answers points to dysfunction.",
    "This pattern could be a sign of a personality disorder.",
  ];

  it.each(clean)("accepts already-hedged copy: %s", (text) => {
    const result = enforceNonDiagnostic(text);
    expect(result.ok).toBe(true);
    expect(result.violations).toHaveLength(0);
  });

  it.each(rewritableThenClean)("auto-hedges absolute openers: %s", (text) => {
    const result = enforceNonDiagnostic(text);
    expect(result.ok).toBe(true);
    // the raw, unhedged opener should be gone even though a hedged rewrite may
    // legitimately still contain "you have" inside "your responses suggest you have"
    expect(result.text.startsWith("You are") || result.text.startsWith("You have") || result.text.startsWith("You're")).toBe(
      false
    );
    expect(result.text).toMatch(/your responses suggest/i);
  });

  it.each(hardBanned)("rejects clinical/diagnostic language: %s", (text) => {
    const result = enforceNonDiagnostic(text);
    expect(result.ok).toBe(false);
    expect(result.violations.length).toBeGreaterThan(0);
  });

  it("rewrites without mangling the rest of the sentence", () => {
    const result = enforceNonDiagnostic("You are ambitious and you have a strong sense of self.");
    expect(result.text).toBe(
      "your responses suggest you tend to be ambitious and your responses suggest you have a strong sense of self."
    );
  });
});
