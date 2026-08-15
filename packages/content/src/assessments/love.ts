import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "How Do You Love?" — /love. The reference implementation every other
 * experience's config should follow. See docs/ARCHITECTURE.md §3.
 *
 * Dimensions used here: connection, independence, trust, vulnerability,
 * validation, security (a subset of the global pool in ./dimensions.ts).
 */
export const loveAssessment: AssessmentConfig = {
  slug: "love",
  name: "How Do You Love?",
  category: "relationships",
  description:
    "A short, adaptive conversation about how you connect, protect yourself, and show up when things get close.",
  hook: "There's a pattern in how you love — most people have never seen it written down.",
  targetAudience: "Adults curious about their own relationship patterns.",
  status: "published",
  version: 1,
  minQuestions: 7,
  recommendedQuestions: 11,
  maxQuestions: 14,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "independence", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "vulnerability", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "security", weight: 1 },
  ],

  scoringModel: {
    normalization: "min-max",
    aiInfluenceCap: 0.15,
  },

  questionBank: {
    core: [
      {
        key: "closeness_reaction",
        type: "single_select",
        isCore: true,
        prompt: "How do you usually react when someone becomes emotionally distant?",
        options: [
          { key: "move_closer", label: "I move closer", dimensionContributions: { connection: 2 } },
          { key: "give_space", label: "I give them space", dimensionContributions: { independence: 2, connection: -1 } },
          { key: "pretend_fine", label: "I pretend it doesn't bother me", dimensionContributions: { vulnerability: -2, security: -1 } },
          { key: "become_uncertain", label: "I become uncertain", dimensionContributions: { security: -2, validation: 1 } },
          { key: "depends", label: "It depends", dimensionContributions: {} },
        ],
      },
      {
        key: "closeness_definition",
        type: "single_select",
        isCore: true,
        prompt: "When you imagine being truly close to someone, what matters most?",
        options: [
          { key: "emotionally_safe", label: "Feeling emotionally safe", dimensionContributions: { security: 2 } },
          { key: "fully_myself", label: "Being fully myself without editing", dimensionContributions: { vulnerability: 2 } },
          { key: "wont_leave", label: "Knowing they won't leave", dimensionContributions: { trust: -1, validation: 1 } },
          { key: "own_space", label: "Having space to be independent too", dimensionContributions: { independence: 2 } },
        ],
      },
      {
        key: "trust_default",
        type: "single_select",
        isCore: true,
        prompt: "When someone new shows real interest in you, your first instinct is...",
        options: [
          { key: "lean_in", label: "I lean in with curiosity", dimensionContributions: { trust: 2 } },
          { key: "wait_observe", label: "I wait and observe before opening up", dimensionContributions: { trust: -1, vulnerability: -1 } },
          { key: "skeptical", label: "I look for reasons it might not be genuine", dimensionContributions: { trust: -2 } },
          { key: "flattered_cautious", label: "I feel flattered but cautious", dimensionContributions: { validation: 1, trust: -1 } },
        ],
      },
      {
        key: "independence_scale",
        type: "scale",
        isCore: true,
        prompt: "In a typical week, how much time completely to yourself do you need to feel like yourself?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
      {
        key: "after_argument",
        type: "single_select",
        isCore: true,
        prompt: "After a disagreement with someone close to you, what do you usually want first?",
        options: [
          { key: "reconnect", label: "To reconnect quickly", dimensionContributions: { connection: 2 } },
          { key: "time_apart", label: "Some time apart to process", dimensionContributions: { independence: 2 } },
          { key: "reassurance", label: "Reassurance that we're okay", dimensionContributions: { validation: 2, security: 1 } },
          { key: "understand", label: "To understand exactly what went wrong", dimensionContributions: { trust: 1 } },
        ],
      },
      {
        key: "love_expression",
        type: "single_select",
        isCore: true,
        prompt: "You feel most loved when someone...",
        options: [
          { key: "consistent_effort", label: "Makes consistent, small efforts", dimensionContributions: { security: 2 } },
          { key: "truly_listens", label: "Truly listens without trying to fix things", dimensionContributions: { vulnerability: 2 } },
          { key: "gives_room", label: "Gives you room to be independent", dimensionContributions: { independence: 2 } },
          { key: "reassures_often", label: "Reassures you often", dimensionContributions: { validation: 2 } },
        ],
      },
      {
        key: "closeness_dependency",
        type: "open_text",
        isCore: true,
        prompt: "Tell us about a time you felt close to someone, but the thought of pulling away still crossed your mind. What was happening?",
        // Question AI may pick at most one of these — never a question outside this list (§4/§5).
        dynamicFollowupCandidates: ["what_would_help", "what_pattern_notice"],
      },
      {
        key: "new_relationship_pace",
        type: "single_select",
        isCore: true,
        prompt: "When something new starts moving quickly, you feel...",
        options: [
          { key: "excited", label: "Excited — I like where this is going", dimensionContributions: { connection: 1, security: -1 } },
          { key: "cautious", label: "Cautious — I'd rather slow down", dimensionContributions: { security: 2, trust: -1 } },
          { key: "excited_nervous", label: "Both excited and nervous", dimensionContributions: { validation: 1 } },
          { key: "red_flags", label: "I start looking for red flags", dimensionContributions: { trust: -2 } },
        ],
      },
      {
        key: "reassurance_need",
        type: "scale",
        isCore: true,
        prompt: "How often do you find yourself needing reassurance that someone still wants you around?",
        scaleMax: 5,
        scaleDimension: "validation",
      },
      {
        key: "someone_pulls_away",
        type: "single_select",
        isCore: true,
        prompt: "When someone you're close to pulls away, what do you assume first?",
        options: [
          { key: "needs_space", label: "They need space, not distance from me", dimensionContributions: { security: 2, trust: 1 } },
          { key: "my_fault", label: "I did something wrong", dimensionContributions: { security: -2 } },
          { key: "losing_interest", label: "They're losing interest", dimensionContributions: { trust: -2 } },
          { key: "no_assume", label: "I try not to assume anything", dimensionContributions: { security: 1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "protect_what",
        type: "single_select",
        isCore: false,
        prompt: "When you start pulling away, what are you usually trying to protect?",
        options: [
          { key: "my_independence", label: "My independence", dimensionContributions: { independence: 2 } },
          { key: "my_emotions", label: "My emotions", dimensionContributions: { vulnerability: -1, security: -1 } },
          { key: "my_control", label: "My sense of control", dimensionContributions: { independence: 1 } },
          { key: "from_rejection", label: "Myself from rejection", dimensionContributions: { validation: 1, security: -2 } },
          { key: "not_sure", label: "I'm not sure", dimensionContributions: {} },
          { key: "something_else", label: "Something else", dimensionContributions: {} },
        ],
      },
      {
        key: "independence_after_connection",
        type: "single_select",
        isCore: false,
        prompt: "After a period of really close connection, what usually happens for you?",
        options: [
          { key: "want_more", label: "I want even more closeness", dimensionContributions: { connection: 2 } },
          { key: "need_space", label: "I start needing space", dimensionContributions: { independence: 2 } },
          { key: "steady", label: "I feel steady either way", dimensionContributions: { security: 2 } },
          { key: "worry", label: "I start worrying it won't last", dimensionContributions: { validation: 1, security: -1 } },
        ],
      },
      {
        key: "trust_when_hurt",
        type: "single_select",
        isCore: false,
        prompt: "If someone you trusted let you down, what would rebuild your trust fastest?",
        options: [
          { key: "consistency", label: "Consistent follow-through over time", dimensionContributions: { trust: 2, security: 1 } },
          { key: "honest_conversation", label: "An honest, vulnerable conversation", dimensionContributions: { vulnerability: 2, trust: 1 } },
          { key: "proof_actions", label: "Them proving it through actions, not words", dimensionContributions: { trust: 1, independence: 1 } },
          { key: "not_sure_trust", label: "I'm not sure I'd fully trust again", dimensionContributions: { trust: -2 } },
        ],
      },
      {
        // Candidate for Question AI, chosen when the open-text answer reads as
        // more "I want to fix this" than "this keeps happening to me."
        key: "what_would_help",
        type: "single_select",
        isCore: false,
        prompt: "What do you think would help you stay close instead of pulling away?",
        options: [
          { key: "clear_reassurance", label: "Clear, low-pressure reassurance", dimensionContributions: { security: 2, validation: 1 } },
          { key: "naming_it", label: "Being able to name what I'm feeling out loud", dimensionContributions: { vulnerability: 2 } },
          { key: "slower_pace", label: "Simply moving at a slower pace", dimensionContributions: { independence: 1, security: 1 } },
          { key: "not_sure_help", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        // Candidate for Question AI, chosen when the open-text answer reads as
        // describing a repeated pattern rather than a one-off moment.
        key: "what_pattern_notice",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, is this a pattern you recognize in other relationships too?",
        options: [
          { key: "yes_often", label: "Yes, it comes up often", dimensionContributions: { independence: 1, security: -1 } },
          { key: "yes_sometimes", label: "Sometimes, depending on the person", dimensionContributions: {} },
          { key: "no_specific", label: "No, this felt specific to that situation", dimensionContributions: { security: 1 } },
          { key: "never_noticed", label: "I've never really looked for a pattern", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "ambiguous_closeness_reaction",
      trigger: { questionKey: "closeness_reaction", op: "answered_option", optionKey: "depends" },
      action: { type: "ask_followup", followupQuestionKey: "protect_what" },
      priority: 10,
    },
    {
      // Question AI resolves this dynamically per-session (packages/ai) and bakes its
      // choice into the recorded answer before this rule ever runs — see §4/§5.
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "closeness_dependency", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "uncertain_closeness_reaction",
      trigger: { questionKey: "closeness_reaction", op: "answered_option", optionKey: "become_uncertain" },
      action: { type: "ask_followup", followupQuestionKey: "protect_what" },
      priority: 9,
    },
    {
      key: "strong_independence_signal",
      trigger: { questionKey: "independence_scale", dimensionKey: "independence", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "independence_after_connection" },
      priority: 5,
    },
    {
      key: "low_trust_signal",
      trigger: { questionKey: "trust_default", op: "answered_option", optionKey: "skeptical" },
      action: { type: "ask_followup", followupQuestionKey: "trust_when_hurt" },
      priority: 5,
    },
  ],

  profiles: [
    {
      key: "independent_connector",
      name: "The Independent Connector",
      descriptionTemplate:
        "Your responses suggest you value deep connection while strongly protecting your independence. One pattern in your answers is a tendency to pull back right when things start to feel very close — often as a way of staying yourself inside the relationship, not a sign of losing interest.",
      matchingRule: { dimensionRanges: { connection: [55, 100], independence: [60, 100] } },
    },
    {
      key: "steady_anchor",
      name: "The Steady Anchor",
      descriptionTemplate:
        "Your responses suggest a grounded, low-reactivity style — you tend not to need frequent reassurance and stay relatively steady even when things feel uncertain. This can be a real strength for people close to you, though it may sometimes read as more distant than you intend.",
      matchingRule: { dimensionRanges: { security: [65, 100], validation: [0, 45] } },
    },
    {
      key: "devoted_romantic",
      name: "The Devoted Romantic",
      descriptionTemplate:
        "Your responses suggest you invest fully once connection is there, and you tend to look for consistent signs that it's returned. One pattern worth noticing: your sense of security may lean on how reassured you feel, more than on your own steadiness.",
      matchingRule: { dimensionRanges: { connection: [60, 100], validation: [55, 100] } },
    },
    {
      key: "careful_opener",
      name: "The Careful Opener",
      descriptionTemplate:
        "Your responses suggest you open up gradually and watch for consistency before fully trusting. This appears less like guardedness for its own sake, and more like a pattern of protecting yourself until safety is well-established.",
      matchingRule: { dimensionRanges: { trust: [0, 55], vulnerability: [0, 50] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your primary pattern is:",
    insightIntro:
      "Your responses suggest a specific way you balance closeness and self-protection — one that shapes how you show up early in relationships and how you react when things intensify.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you love.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "love.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "love.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "love.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "love.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "love.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "love.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "love.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "love.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "love.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "love.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { independence: [55, 100], connection: [55, 100] } },
      weight: 1,
      bridgeCopy:
        "Your answers showed an interesting relationship between independence and connection. Would you like to explore how this pattern appears in intimacy?",
    },
    {
      assessmentSlug: "relationship",
      condition: { dimensionRanges: { security: [0, 50] } },
      weight: 0.8,
      bridgeCopy: "Curious how this pattern plays out over the life of a relationship, not just the beginning?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
