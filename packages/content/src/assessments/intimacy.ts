import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Intimacy Profile" — /intimacy. See docs/ARCHITECTURE.md §3. */
export const intimacyAssessment: AssessmentConfig = {
  slug: "intimacy",
  name: "Your Intimacy Profile",
  category: "intimacy",
  description: "A short, adaptive conversation about what actually helps you feel close to someone.",
  hook: "Closeness isn't just about proximity — it's about what makes it feel safe to stay.",
  targetAudience: "Adults curious about their own comfort with real closeness.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "vulnerability", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "security", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "risk", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "physical_closeness_comfort",
        type: "single_select",
        isCore: true,
        prompt: "How comfortable are you with physical closeness before emotional closeness is established?",
        options: [
          { key: "very_comfortable", label: "Very comfortable — physical closeness comes easily", dimensionContributions: { risk: 2, curiosity: 1 } },
          { key: "somewhat", label: "Somewhat, depends on the person", dimensionContributions: { risk: 1 } },
          { key: "need_trust_first", label: "I need emotional trust first", dimensionContributions: { trust: 1, security: 1 } },
          { key: "guarded", label: "Physical closeness makes me guarded", dimensionContributions: { vulnerability: -2 } },
        ],
      },
      {
        key: "sharing_feelings",
        type: "single_select",
        isCore: true,
        prompt: "When you're falling for someone, how much do you let them see?",
        options: [
          { key: "everything_fast", label: "Pretty much everything, fast", dimensionContributions: { emotional_openness: 2, vulnerability: 2 } },
          { key: "curated", label: "A curated version at first", dimensionContributions: { vulnerability: -1 } },
          { key: "only_safe", label: "Only what feels safe", dimensionContributions: { vulnerability: -1, security: 1 } },
          { key: "hold_back", label: "I hold back until I'm sure", dimensionContributions: { vulnerability: -2, trust: -1 } },
        ],
      },
      {
        key: "intimacy_scale",
        type: "scale",
        isCore: true,
        prompt: "How easily do you let yourself be fully present during intimate moments, rather than in your head?",
        scaleMax: 5,
        scaleDimension: "emotional_openness",
      },
      {
        key: "after_intimacy",
        type: "single_select",
        isCore: true,
        prompt: "Right after a moment of real closeness, you usually feel...",
        options: [
          { key: "closer_open", label: "Closer and more open", dimensionContributions: { vulnerability: 2 } },
          { key: "exposed", label: "A little exposed", dimensionContributions: { vulnerability: -1, security: -1 } },
          { key: "pull_back", label: "Like pulling back to reset", dimensionContributions: { vulnerability: -2, risk: -1 } },
          { key: "curious_more", label: "Curious to go deeper next time", dimensionContributions: { curiosity: 2 } },
        ],
      },
      {
        key: "new_experience_openness",
        type: "single_select",
        isCore: true,
        prompt: "Trying something new and vulnerable with a partner feels...",
        options: [
          { key: "exciting", label: "Exciting", dimensionContributions: { curiosity: 2, risk: 1 } },
          { key: "fine_with_trust", label: "Fine once I trust them", dimensionContributions: { trust: 1 } },
          { key: "nerve_worth_it", label: "Nerve-wracking but worth it", dimensionContributions: { risk: 1, vulnerability: 1 } },
          { key: "not_appealing", label: "Not really appealing", dimensionContributions: { curiosity: -2, risk: -2 } },
        ],
      },
      {
        key: "intimacy_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a moment you felt truly close to someone — what made it feel safe, or what got in the way?",
        dynamicFollowupCandidates: ["what_made_it_safe", "what_got_in_the_way"],
      },
      {
        key: "asking_for_what_you_want",
        type: "single_select",
        isCore: true,
        prompt: "Telling a partner what you actually want or need feels...",
        options: [
          { key: "natural", label: "Natural — I just say it", dimensionContributions: { emotional_openness: 2 } },
          { key: "easier_indirect", label: "Easier in writing or indirectly", dimensionContributions: { emotional_openness: -1 } },
          { key: "too_much", label: "Hard — I worry it's too much", dimensionContributions: { vulnerability: -2, security: -1 } },
          { key: "usually_dont", label: "I usually don't", dimensionContributions: { emotional_openness: -2 } },
        ],
      },
      {
        key: "trust_pace",
        type: "single_select",
        isCore: true,
        prompt: "How quickly do you typically trust someone enough to be fully yourself?",
        options: [
          { key: "quickly", label: "Pretty quickly", dimensionContributions: { trust: 2 } },
          { key: "consistent_time", label: "It takes consistent time", dimensionContributions: { trust: 1, security: 1 } },
          { key: "slowly_rarely", label: "Slowly, and rarely completely", dimensionContributions: { trust: -2 } },
          { key: "varies", label: "It varies a lot by person", dimensionContributions: {} },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "what_made_it_safe",
        type: "single_select",
        isCore: false,
        prompt: "What made that moment feel safe?",
        options: [
          { key: "present_too", label: "They were fully present too", dimensionContributions: { emotional_openness: 1 } },
          { key: "nothing_expected", label: "Nothing was expected of me", dimensionContributions: { vulnerability: 1 } },
          { key: "built_trust", label: "I'd built trust with them over time", dimensionContributions: { trust: 2 } },
          { key: "not_sure_safe", label: "Honestly I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "what_got_in_the_way",
        type: "single_select",
        isCore: false,
        prompt: "What got in the way?",
        options: [
          { key: "own_guardedness", label: "My own guardedness", dimensionContributions: { vulnerability: -2 } },
          { key: "felt_rushed", label: "Feeling rushed", dimensionContributions: { risk: -1 } },
          { key: "not_trusting_yet", label: "Not fully trusting them yet", dimensionContributions: { trust: -2 } },
          { key: "external_pressure", label: "External pressure or timing", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "guarded_signal",
      trigger: { questionKey: "physical_closeness_comfort", op: "answered_option", optionKey: "guarded" },
      action: { type: "ask_followup", followupQuestionKey: "what_got_in_the_way" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "intimacy_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_open_book",
      name: "The Open Book",
      descriptionTemplate:
        "Your responses suggest you let people see the real you fairly quickly, and tend to stay present rather than guarded once closeness starts building. This can create fast, genuine connection — and occasionally means trust catches up after the fact rather than before.",
      matchingRule: { dimensionRanges: { emotional_openness: [60, 100], vulnerability: [55, 100] } },
    },
    {
      key: "the_slow_unfolder",
      name: "The Slow Unfolder",
      descriptionTemplate:
        "Your responses suggest you open up gradually, letting trust build before you let closeness in fully. This appears less like distance for its own sake, and more like a pattern of protecting something real until it feels earned.",
      matchingRule: { dimensionRanges: { trust: [0, 55], vulnerability: [0, 50] } },
    },
    {
      key: "the_adventurous_connector",
      name: "The Adventurous Connector",
      descriptionTemplate:
        "Your responses suggest closeness feels like something to explore rather than something to be cautious around — new and vulnerable territory tends to read as exciting to you more than threatening.",
      matchingRule: { dimensionRanges: { curiosity: [60, 100], risk: [55, 100] } },
    },
    {
      key: "the_guarded_romantic",
      name: "The Guarded Romantic",
      descriptionTemplate:
        "Your responses suggest you hold back until safety feels well-established, even when part of you wants closeness. One pattern worth noticing: the guardedness may be less about the other person, and more about needing solid ground first.",
      matchingRule: { dimensionRanges: { vulnerability: [0, 45], security: [55, 100] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your intimacy pattern is:",
    insightIntro:
      "Your responses suggest a specific balance between how much you open up and how much safety you need before you do — one that shapes what real closeness looks like for you.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you experience intimacy.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "intimacy.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "intimacy.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "intimacy.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "intimacy.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "intimacy.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "intimacy.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "intimacy.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "intimacy.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "intimacy.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "intimacy.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "vulnerability",
      condition: { dimensionRanges: { vulnerability: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers pointed to guardedness playing a role here — want to explore your vulnerability profile more directly?",
    },
    {
      assessmentSlug: "connection",
      condition: { dimensionRanges: { curiosity: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "Curious what draws you to people in the first place, before intimacy even enters the picture?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
