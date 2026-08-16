import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Relationship Pattern" — /relationship. See docs/ARCHITECTURE.md §3. */
export const relationshipAssessment: AssessmentConfig = {
  slug: "relationship",
  name: "Your Relationship Pattern",
  category: "relationships",
  description: "A short, adaptive conversation about the dynamic you tend to build once a relationship settles in.",
  hook: "The pattern isn't in any one relationship — it's in the shape they keep taking.",
  targetAudience: "Adults curious about recurring dynamics across their relationships.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "conflict", weight: 1 },
    { key: "control", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "security", weight: 1 },
    { key: "communication", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "conflict_response",
        type: "single_select",
        isCore: true,
        prompt: "When a disagreement starts heating up, what do you usually do?",
        options: [
          { key: "push_through", label: "Keep going until it's resolved", dimensionContributions: { conflict: 2, connection: 1 } },
          { key: "need_pause", label: "Need a pause before continuing", dimensionContributions: { conflict: -1, flexibility: 1 } },
          { key: "smooth_over", label: "Try to smooth it over quickly", dimensionContributions: { conflict: -2, security: 1 } },
          { key: "withdraw", label: "Go quiet and withdraw", dimensionContributions: { conflict: -2, communication: -1 } },
        ],
      },
      {
        key: "relationship_rhythm",
        type: "single_select",
        isCore: true,
        prompt: "Over time, your relationships tend to settle into...",
        options: [
          { key: "steady", label: "A steady, predictable rhythm", dimensionContributions: { security: 2 } },
          { key: "cycles", label: "Cycles of closeness and distance", dimensionContributions: { connection: 1, security: -1 } },
          { key: "renegotiation", label: "Constant renegotiation", dimensionContributions: { flexibility: 2, control: -1 } },
          { key: "accommodating", label: "Whatever the other person needs", dimensionContributions: { control: -2, flexibility: 1 } },
        ],
      },
      {
        key: "decision_making_together",
        type: "single_select",
        isCore: true,
        prompt: "When making a big decision together, you...",
        options: [
          { key: "lead", label: "Want to lead the process", dimensionContributions: { control: 2 } },
          { key: "follow", label: "Prefer to follow their lead", dimensionContributions: { control: -2 } },
          { key: "split", label: "Push for a genuine 50/50 split", dimensionContributions: { flexibility: 1, communication: 1 } },
          { key: "avoid", label: "Avoid deciding as long as possible", dimensionContributions: { conflict: -1, communication: -1 } },
        ],
      },
      {
        key: "routine_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you rely on routine and predictability in a relationship?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "when_things_change",
        type: "single_select",
        isCore: true,
        prompt: "When a relationship's dynamic shifts unexpectedly, you feel...",
        options: [
          { key: "adaptable", label: "Adaptable — I go with it", dimensionContributions: { flexibility: 2 } },
          { key: "unsettled", label: "Unsettled until things stabilize", dimensionContributions: { security: -2, flexibility: -1 } },
          { key: "regain_control", label: "Like I need to regain control", dimensionContributions: { control: 2 } },
          { key: "curious", label: "Curious about where it's going", dimensionContributions: { flexibility: 1, connection: 1 } },
        ],
      },
      {
        key: "long_term_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a relationship pattern you keep noticing in yourself — good or bad.",
        dynamicFollowupCandidates: ["what_triggers_pattern", "how_pattern_started"],
      },
      {
        key: "expressing_needs",
        type: "single_select",
        isCore: true,
        prompt: "When something's bothering you in a relationship, you usually...",
        options: [
          { key: "direct", label: "Say it directly, right away", dimensionContributions: { communication: 2 } },
          { key: "right_moment", label: "Wait for the right moment", dimensionContributions: { communication: 1, control: -1 } },
          { key: "hope_notice", label: "Hope they notice on their own", dimensionContributions: { communication: -2 } },
          { key: "indirect", label: "Bring it up indirectly", dimensionContributions: { communication: -1, conflict: -1 } },
        ],
      },
      {
        key: "power_balance",
        type: "single_select",
        isCore: true,
        prompt: "In your relationships, you tend to feel...",
        options: [
          { key: "matched", label: "Equally matched", dimensionContributions: { control: 1, connection: 1 } },
          { key: "gives_more", label: "Like the one who gives more", dimensionContributions: { control: -1, security: -1 } },
          { key: "holds_control", label: "Like the one who holds more control", dimensionContributions: { control: 2 } },
          { key: "depends", label: "It depends entirely on the person", dimensionContributions: { flexibility: 1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "what_triggers_pattern",
        type: "single_select",
        isCore: false,
        prompt: "What usually triggers that pattern for you?",
        options: [
          { key: "unheard", label: "Feeling unheard", dimensionContributions: { communication: -1, conflict: 1 } },
          { key: "too_controlled", label: "Feeling too controlled", dimensionContributions: { control: -2 } },
          { key: "uncertain", label: "Feeling uncertain about where things stand", dimensionContributions: { security: -2 } },
          { key: "not_sure_trigger", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "how_pattern_started",
        type: "single_select",
        isCore: false,
        prompt: "Does this feel like a pattern you learned early on, or something newer?",
        options: [
          { key: "goes_back", label: "It goes way back", dimensionContributions: { security: -1 } },
          { key: "recent", label: "It's shown up more recently", dimensionContributions: { flexibility: 1 } },
          { key: "both", label: "A bit of both", dimensionContributions: {} },
          { key: "never_thought", label: "I've never thought about it", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "withdraw_signal",
      trigger: { questionKey: "conflict_response", op: "answered_option", optionKey: "withdraw" },
      action: { type: "ask_followup", followupQuestionKey: "what_triggers_pattern" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "long_term_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "steady_builder",
      name: "The Steady Builder",
      descriptionTemplate:
        "Your responses suggest you build relationships around consistency and follow-through, tending to value predictability over spontaneity. One pattern worth noticing: you may find shifts in a relationship's rhythm more unsettling than most.",
      matchingRule: { dimensionRanges: { security: [65, 100], control: [0, 55] } },
    },
    {
      key: "the_negotiator",
      name: "The Negotiator",
      descriptionTemplate:
        "Your responses suggest you treat a relationship's dynamic as something to actively renegotiate together, rather than something fixed. Communication tends to be your primary tool for keeping things balanced.",
      matchingRule: { dimensionRanges: { flexibility: [60, 100], communication: [55, 100] } },
    },
    {
      key: "the_quiet_anchor",
      name: "The Quiet Anchor",
      descriptionTemplate:
        "Your responses suggest you prefer smoothing things over to prolonged conflict, often providing steadiness for a relationship rather than stirring it. This can be a real strength, though it may occasionally mean your own friction goes unspoken.",
      matchingRule: { dimensionRanges: { conflict: [0, 45], security: [55, 100] } },
    },
    {
      key: "the_watchful_one",
      name: "The Watchful One",
      descriptionTemplate:
        "Your responses suggest a tendency to hold onto more control when things feel uncertain. One pattern worth noticing: this may be less about wanting control for its own sake, and more about managing the discomfort of not knowing where things stand.",
      matchingRule: { dimensionRanges: { control: [60, 100], security: [0, 45] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your relationship pattern is:",
    insightIntro:
      "Your responses suggest a specific way you handle closeness, conflict, and control across relationships — one that likely repeats more than you've consciously noticed.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you do relationships.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "relationship.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "relationship.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "relationship.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "relationship.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "relationship.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "relationship.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "relationship.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "relationship.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "relationship.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "relationship.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "jealousy",
      condition: { dimensionRanges: { security: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers touched on control and uncertainty in relationships — want to see how that shows up specifically around jealousy?",
    },
    {
      assessmentSlug: "communication",
      condition: { dimensionRanges: { communication: [0, 50] } },
      weight: 0.8,
      bridgeCopy: "Curious how this pattern plays out in the way you actually communicate day to day?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
