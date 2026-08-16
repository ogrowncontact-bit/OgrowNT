import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Connection & Desire Profile" — /connection. See docs/ARCHITECTURE.md §3. */
export const connectionAssessment: AssessmentConfig = {
  slug: "connection",
  name: "Connection & Desire Profile",
  category: "intimacy",
  description: "A short, adaptive conversation about what actually draws you to someone, and what keeps that pull alive.",
  hook: "Attraction has a shape. Most people have never mapped their own.",
  targetAudience: "Adults curious about their own patterns of attraction and desire.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "risk", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "social_confidence", weight: 1 },
    { key: "vulnerability", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "what_draws_you_in",
        type: "single_select",
        isCore: true,
        prompt: "What draws you to someone, most often, at the start?",
        options: [
          { key: "easy_conversation", label: "Easy conversation", dimensionContributions: { social_confidence: 2, connection: 1 } },
          { key: "mystery", label: "A sense of mystery", dimensionContributions: { curiosity: 2 } },
          { key: "chemistry", label: "Physical chemistry", dimensionContributions: { risk: 1 } },
          { key: "instant_comfort", label: "Feeling instantly comfortable", dimensionContributions: { connection: 2 } },
        ],
      },
      {
        key: "chemistry_or_compatibility",
        type: "single_select",
        isCore: true,
        prompt: "When choosing who to pursue, you lean toward...",
        options: [
          { key: "chemistry_unpredictable", label: "Chemistry, even if it's unpredictable", dimensionContributions: { risk: 2, curiosity: 1 } },
          { key: "compatibility_slower", label: "Compatibility, even if it's slower to build", dimensionContributions: { connection: 1 } },
          { key: "mix_chemistry", label: "A mix, weighted toward chemistry", dimensionContributions: { risk: 1 } },
          { key: "mix_compatibility", label: "A mix, weighted toward compatibility", dimensionContributions: { connection: 1 } },
        ],
      },
      {
        key: "boredom_scale",
        type: "scale",
        isCore: true,
        prompt: "How quickly do you lose interest once things become predictable?",
        scaleMax: 5,
        scaleDimension: "curiosity",
      },
      {
        key: "pursuing_someone",
        type: "single_select",
        isCore: true,
        prompt: "When you're genuinely interested in someone, you...",
        options: [
          { key: "make_obvious", label: "Make it obvious", dimensionContributions: { social_confidence: 2, risk: 1 } },
          { key: "let_them_move", label: "Let them make the first move", dimensionContributions: { social_confidence: -1 } },
          { key: "test_waters", label: "Test the waters carefully", dimensionContributions: { risk: -1, flexibility: 1 } },
          { key: "anxious_overthink", label: "Get anxious and overthink it", dimensionContributions: { social_confidence: -2 } },
        ],
      },
      {
        key: "desire_fades_or_grows",
        type: "single_select",
        isCore: true,
        prompt: "Once a relationship becomes familiar, your desire tends to...",
        options: [
          { key: "deepen", label: "Deepen with familiarity", dimensionContributions: { connection: 2 } },
          { key: "stay_steady", label: "Stay steady either way", dimensionContributions: { connection: 1 } },
          { key: "need_novelty", label: "Need novelty to stay alive", dimensionContributions: { curiosity: 2, flexibility: 1 } },
          { key: "fade_without_work", label: "Fade unless we actively work at it", dimensionContributions: { curiosity: 1, connection: -1 } },
        ],
      },
      {
        key: "connection_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a moment you felt real chemistry with someone. What was actually happening in that moment?",
        dynamicFollowupCandidates: ["what_was_happening", "does_this_repeat"],
      },
      {
        key: "rejection_response",
        type: "single_select",
        isCore: true,
        prompt: "If someone you were interested in didn't reciprocate, you'd...",
        options: [
          { key: "move_on", label: "Move on pretty quickly", dimensionContributions: { social_confidence: 1, risk: 1 } },
          { key: "feel_it_a_while", label: "Feel it for a while", dimensionContributions: { vulnerability: 1 } },
          { key: "wonder_whats_wrong", label: "Wonder what was wrong with me", dimensionContributions: { social_confidence: -2, vulnerability: -1 } },
          { key: "get_determined", label: "Get more determined", dimensionContributions: { risk: 2 } },
        ],
      },
      {
        key: "flirting_style",
        type: "single_select",
        isCore: true,
        prompt: "Your natural flirting style is closer to...",
        options: [
          { key: "playful_direct", label: "Playful and direct", dimensionContributions: { social_confidence: 2 } },
          { key: "witty_indirect", label: "Witty and indirect", dimensionContributions: { curiosity: 1, social_confidence: 1 } },
          { key: "quiet_attentive", label: "Quiet and attentive", dimensionContributions: { connection: 1, social_confidence: -1 } },
          { key: "avoid_flirting", label: "I mostly avoid flirting", dimensionContributions: { social_confidence: -2 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "what_was_happening",
        type: "single_select",
        isCore: false,
        prompt: "What was actually happening in that moment, underneath the chemistry?",
        options: [
          { key: "both_present", label: "We were both fully present", dimensionContributions: { connection: 2 } },
          { key: "real_unpredictability", label: "There was real unpredictability", dimensionContributions: { curiosity: 2, risk: 1 } },
          { key: "felt_confident", label: "I felt unusually confident", dimensionContributions: { social_confidence: 2 } },
          { key: "not_sure_moment", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "does_this_repeat",
        type: "single_select",
        isCore: false,
        prompt: "Does this kind of moment happen often for you, or rarely?",
        options: [
          { key: "fairly_often", label: "Fairly often", dimensionContributions: { curiosity: 1 } },
          { key: "rarely_stood_out", label: "Rarely — it stood out", dimensionContributions: { connection: 1 } },
          { key: "certain_people", label: "Only with certain kinds of people", dimensionContributions: {} },
          { key: "never_tracked", label: "I've never really tracked it", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "self_doubt_signal",
      trigger: { questionKey: "rejection_response", op: "answered_option", optionKey: "wonder_whats_wrong" },
      action: { type: "ask_followup", followupQuestionKey: "does_this_repeat" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "connection_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_spark_chaser",
      name: "The Spark Chaser",
      descriptionTemplate:
        "Your responses suggest you're drawn to unpredictability and novelty — chemistry tends to matter more to you than steady compatibility, at least at the start. This can make early attraction feel electric, though it may take more deliberate effort to keep that spark alive once things settle.",
      matchingRule: { dimensionRanges: { curiosity: [60, 100], risk: [55, 100] } },
    },
    {
      key: "the_steady_deepener",
      name: "The Steady Deepener",
      descriptionTemplate:
        "Your responses suggest your desire tends to grow with familiarity rather than fade — connection deepens for you the more known someone becomes, rather than requiring novelty to stay interesting.",
      matchingRule: { dimensionRanges: { connection: [60, 100], curiosity: [0, 50] } },
    },
    {
      key: "the_confident_pursuer",
      name: "The Confident Pursuer",
      descriptionTemplate:
        "Your responses suggest you tend to act on interest rather than wait for it to be reciprocated first — putting yourself out there seems to come naturally, even when the outcome is uncertain.",
      matchingRule: { dimensionRanges: { social_confidence: [60, 100], risk: [45, 100] } },
    },
    {
      key: "the_quiet_observer",
      name: "The Quiet Observer",
      descriptionTemplate:
        "Your responses suggest you tend to notice and feel connection deeply, while staying fairly reserved about acting on it. This appears less like disinterest, and more like a preference for certainty before you show your hand.",
      matchingRule: { dimensionRanges: { social_confidence: [0, 45], connection: [45, 100] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your connection pattern is:",
    insightIntro:
      "Your responses suggest a specific pattern in what draws you to people and what keeps that pull alive over time — one that shapes far more of your dating and relationship life than most people realize.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how connection and desire work for you.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "connection.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "connection.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "connection.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "connection.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "connection.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "connection.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "connection.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "connection.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "connection.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "connection.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "love",
      condition: { dimensionRanges: { connection: [55, 100] } },
      weight: 1,
      bridgeCopy: "You're drawn in fast when connection is real — curious how that same pull shows up once you're actually in love?",
    },
    {
      assessmentSlug: "social",
      condition: { dimensionRanges: { social_confidence: [0, 50] } },
      weight: 0.8,
      bridgeCopy: "There's often a gap between how confident you feel and how confident you come across — want to see how people actually read you?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
