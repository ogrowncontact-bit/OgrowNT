import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "Your Intimacy Profile" — /intimacy. Emotional and relational intimacy —
 * trust, vulnerability, and closeness — kept adult and sophisticated, never
 * explicit (docs/ARCHITECTURE.md §3).
 */
export const intimacyAssessment: AssessmentConfig = {
  slug: "intimacy",
  name: "Your Intimacy Profile",
  category: "relationships",
  description: "A short, adaptive conversation about how close you actually let people get, and what makes that feel safe.",
  hook: "Closeness isn't just about proximity — it's about what makes it feel safe to stay.",
  targetAudience: "Adults curious about their own patterns of emotional and relational intimacy.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "trust", weight: 1 },
    { key: "vulnerability", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "connection", weight: 1 },
    { key: "security", weight: 1 },
    { key: "boundaries", weight: 1 },
    { key: "affection_expression", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "independence", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "connection_high_boundaries",
      label: "wanting real closeness while still holding fairly firm personal boundaries",
      dimensionA: "connection",
      thresholdA: 60,
      dimensionB: "boundaries",
      thresholdB: 65,
    },
    {
      key: "trust_low_vulnerability",
      label: "trusting people fairly easily while still keeping your inner world mostly private",
      dimensionA: "trust",
      thresholdA: 60,
      dimensionB: "vulnerability",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "closeness_definition_intimacy",
        type: "single_select",
        isCore: true,
        prompt: "When you imagine feeling truly close to someone, what matters most?",
        options: [
          { key: "seen_fully", label: "Being fully seen, without editing myself", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "feel_safe", label: "Feeling genuinely safe with them", dimensionContributions: { security: 2 } },
          { key: "still_myself", label: "Still feeling like myself inside it", dimensionContributions: { independence: 2, boundaries: 1 } },
          { key: "mutual_effort", label: "Knowing it's being built by both of us", dimensionContributions: { connection: 2, communication: 1 } },
        ],
      },
      {
        key: "vulnerability_pace_scale",
        type: "scale",
        isCore: true,
        prompt: "How quickly do you usually let someone see the more private parts of who you are?",
        scaleMax: 5,
        scaleDimension: "vulnerability",
      },
      {
        key: "trust_extension",
        type: "single_select",
        isCore: true,
        prompt: "How do you typically decide someone is safe to open up to?",
        options: [
          { key: "time_and_consistency", label: "Time and consistency", dimensionContributions: { trust: 1, security: 1 } },
          { key: "gut_feeling", label: "A gut feeling, fairly quickly", dimensionContributions: { trust: 2 } },
          { key: "they_open_first", label: "Once they open up first", dimensionContributions: { trust: 1, vulnerability: -1 } },
          { key: "rarely_fully_safe", label: "Honestly, it rarely feels fully safe", dimensionContributions: { trust: -2, boundaries: 1 } },
        ],
      },
      {
        key: "boundaries_scale",
        type: "scale",
        isCore: true,
        prompt: "How clear are your personal boundaries with someone you're close to?",
        scaleMax: 5,
        scaleDimension: "boundaries",
      },
      {
        key: "emotional_sharing_instinct",
        type: "single_select",
        isCore: true,
        prompt: "When something emotional is going on for you, your instinct with a partner is to...",
        options: [
          { key: "share_as_it_happens", label: "Share it as it's happening", dimensionContributions: { emotional_openness: 2, vulnerability: 1 } },
          { key: "process_then_share", label: "Process it alone first, then share", dimensionContributions: { independence: 1, emotional_openness: 1 } },
          { key: "share_if_asked", label: "Share it only if asked", dimensionContributions: { emotional_openness: -1 } },
          { key: "keep_it_private", label: "Keep it mostly private", dimensionContributions: { emotional_openness: -2, vulnerability: -1 } },
        ],
      },
      {
        key: "affection_natural_style_intimacy",
        type: "single_select",
        isCore: true,
        prompt: "How do you most naturally express affection once you feel it?",
        options: [
          { key: "say_it_intimacy", label: "I say it directly", dimensionContributions: { affection_expression: 2, emotional_openness: 1 } },
          { key: "physical_closeness", label: "Through physical closeness", dimensionContributions: { affection_expression: 2, connection: 1 } },
          { key: "quiet_consistency", label: "Through quiet, consistent presence", dimensionContributions: { affection_expression: 1, security: 1 } },
          { key: "dont_show_much_intimacy", label: "Honestly, I don't show it much", dimensionContributions: { affection_expression: -2 } },
        ],
      },
      {
        key: "security_intimacy_scale",
        type: "scale",
        isCore: true,
        prompt: "How safe does emotional closeness generally feel to you, once you're in it?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "independence_within_intimacy",
        type: "single_select",
        isCore: true,
        prompt: "Even in your closest relationship, how important is it to keep some things entirely your own?",
        options: [
          { key: "very_important_intimacy", label: "Very important", dimensionContributions: { independence: 2, boundaries: 1 } },
          { key: "somewhat_important_intimacy", label: "Somewhat important", dimensionContributions: { independence: 1 } },
          { key: "not_important_intimacy", label: "Not especially — I like sharing most things", dimensionContributions: { independence: -2, connection: 2 } },
          { key: "depends_on_what", label: "Depends entirely on what it is", dimensionContributions: {} },
        ],
      },
      {
        key: "communication_of_needs_intimacy",
        type: "single_select",
        isCore: true,
        prompt: "When you need more closeness than you're currently getting, you tend to...",
        options: [
          { key: "ask_directly_intimacy", label: "Ask for it directly", dimensionContributions: { communication: 2, vulnerability: 1 } },
          { key: "create_opportunities", label: "Create opportunities for it instead of asking", dimensionContributions: { communication: 1 } },
          { key: "wait_it_out_intimacy", label: "Wait and hope it happens naturally", dimensionContributions: { communication: -2 } },
          { key: "pull_back_instead", label: "Pull back instead of asking", dimensionContributions: { communication: -2, boundaries: 1 } },
        ],
      },
      {
        key: "connection_daily_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you crave daily emotional check-ins with someone close to you?",
        scaleMax: 5,
        scaleDimension: "connection",
      },
      {
        key: "boundary_pushed",
        type: "single_select",
        isCore: true,
        prompt: "When someone pushes past a boundary without realizing it, what do you do?",
        options: [
          { key: "name_it_calmly", label: "Name it calmly, in the moment", dimensionContributions: { boundaries: 2, communication: 2 } },
          { key: "let_it_slide_once", label: "Let it slide, at least the first time", dimensionContributions: { boundaries: -1 } },
          { key: "quietly_withdraw_boundary", label: "Quietly withdraw a little", dimensionContributions: { boundaries: 1, emotional_openness: -1 } },
          { key: "rarely_notice_boundary", label: "I rarely notice until much later", dimensionContributions: { boundaries: -2 } },
        ],
      },
      {
        key: "what_makes_it_safe",
        type: "single_select",
        isCore: true,
        prompt: "What makes emotional closeness actually feel safe to you, rather than risky?",
        options: [
          { key: "consistency_safe", label: "Consistency over time", dimensionContributions: { trust: 1, security: 2 } },
          { key: "reciprocity_safe", label: "Knowing it's mutual", dimensionContributions: { connection: 2, communication: 1 } },
          { key: "control_pace_safe", label: "Being able to control the pace", dimensionContributions: { boundaries: 2, independence: 1 } },
          { key: "not_sure_safe", label: "Honestly, I'm not always sure", dimensionContributions: {} },
        ],
      },
      {
        key: "affection_receiving",
        type: "single_select",
        isCore: true,
        prompt: "How comfortable are you receiving affection, rather than giving it?",
        options: [
          { key: "very_comfortable_receiving", label: "Very comfortable", dimensionContributions: { vulnerability: 2, affection_expression: 1 } },
          { key: "somewhat_comfortable_receiving", label: "Somewhat, depending on who it's from", dimensionContributions: { trust: 1 } },
          { key: "a_little_awkward_receiving", label: "A little awkward, honestly", dimensionContributions: { vulnerability: -1 } },
          { key: "much_harder_than_giving", label: "Much harder than giving it", dimensionContributions: { vulnerability: -2, emotional_openness: -1 } },
        ],
      },
      {
        key: "intimacy_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a moment you felt truly close to someone — what made that possible?",
        dynamicFollowupCandidates: ["closeness_what_helped", "closeness_how_rare"],
      },
      {
        key: "holding_back_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a time you wanted to be closer to someone but held part of yourself back.",
        dynamicFollowupCandidates: ["holding_back_reason", "holding_back_pattern"],
        sensitive: true,
        difficulty: "deep",
      },
    ],
    adaptivePool: [
      {
        key: "closeness_what_helped",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, what specifically made that closeness possible?",
        options: [
          { key: "they_went_first", label: "They opened up first", dimensionContributions: { trust: 1, vulnerability: 1 } },
          { key: "enough_time_passed", label: "Enough time had passed", dimensionContributions: { security: 1 } },
          { key: "i_chose_to_risk_it", label: "I chose to take the risk myself", dimensionContributions: { vulnerability: 2 } },
          { key: "not_sure_what_helped", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "closeness_how_rare",
        type: "single_select",
        isCore: false,
        prompt: "Is that kind of closeness something you've felt often, or rarely?",
        options: [
          { key: "fairly_often_close", label: "Fairly often", dimensionContributions: { connection: 1, trust: 1 } },
          { key: "with_a_few_people", label: "With a small number of people", dimensionContributions: { boundaries: 1 } },
          { key: "quite_rare_close", label: "Quite rare, honestly", dimensionContributions: { vulnerability: -1 } },
          { key: "that_was_a_first_close", label: "That was close to a first for me", dimensionContributions: {} },
        ],
      },
      {
        key: "holding_back_reason",
        type: "single_select",
        isCore: false,
        prompt: "What was underneath holding back, in that moment?",
        options: [
          { key: "fear_of_too_much", label: "Fear of giving too much too fast", dimensionContributions: { boundaries: 1, vulnerability: -1 } },
          { key: "not_fully_safe_yet", label: "It didn't feel fully safe yet", dimensionContributions: { security: -1, trust: -1 } },
          { key: "wanted_to_stay_independent", label: "Wanting to stay independent", dimensionContributions: { independence: 2 } },
          { key: "not_sure_why_held_back", label: "I'm honestly not sure why", dimensionContributions: {} },
        ],
      },
      {
        key: "holding_back_pattern",
        type: "single_select",
        isCore: false,
        prompt: "Does this happen often when things start to get close, or was it specific to that person?",
        options: [
          { key: "happens_often_held_back", label: "It happens fairly often", dimensionContributions: { vulnerability: -1, boundaries: 1 } },
          { key: "specific_to_person", label: "It felt specific to that situation", dimensionContributions: {} },
          { key: "never_noticed_pattern", label: "I've never really noticed a pattern", dimensionContributions: {} },
          { key: "only_with_certain_people_held", label: "Only with certain kinds of people", dimensionContributions: {} },
        ],
      },
      {
        key: "trust_rarely_safe_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What would make closeness feel more consistently safe for you?",
        options: [
          { key: "more_time_deep", label: "More time before it deepens", dimensionContributions: { security: 1, boundaries: 1 } },
          { key: "clearer_communication_deep", label: "Clearer communication along the way", dimensionContributions: { communication: 2 } },
          { key: "proof_over_words_deep", label: "Proof through actions, not just words", dimensionContributions: { trust: 1 } },
          { key: "not_sure_would_help_deep", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "boundary_communication_scale",
        type: "scale",
        isCore: false,
        prompt: "How clearly do you communicate a boundary once you notice it's been crossed?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "receiving_affection_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What makes receiving affection harder than giving it, for you?",
        options: [
          { key: "feels_exposing", label: "It feels exposing", dimensionContributions: { vulnerability: -1 } },
          { key: "dont_know_how_to_respond", label: "I don't always know how to respond", dimensionContributions: { emotional_openness: -1 } },
          { key: "waiting_for_the_catch", label: "Some part of me waits for the catch", dimensionContributions: { trust: -1, security: -1 } },
          { key: "not_sure_why_harder", label: "I'm not sure why, honestly", dimensionContributions: {} },
        ],
      },
      {
        key: "affection_pace_scale",
        type: "scale",
        isCore: false,
        prompt: "How openly do you show affection early on, before things feel fully secure?",
        scaleMax: 5,
        scaleDimension: "affection_expression",
      },
      {
        key: "independence_intimacy_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What does keeping things \"your own\" actually protect for you?",
        options: [
          { key: "sense_of_self_deep", label: "A clear sense of who I am", dimensionContributions: { independence: 2 } },
          { key: "room_to_retreat_deep", label: "Room to retreat if things go wrong", dimensionContributions: { boundaries: 1, security: -1 } },
          { key: "just_preference_deep", label: "Honestly, it's just preference", dimensionContributions: { independence: 1 } },
          { key: "not_sure_protects_deep", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "connection_frequency_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "If you went a week without real emotional connection with someone close, how would you feel?",
        options: [
          { key: "genuinely_off_week", label: "Genuinely off", dimensionContributions: { connection: 2 } },
          { key: "would_notice_week", label: "I'd notice, but I'd be fine", dimensionContributions: { connection: 1, independence: 1 } },
          { key: "wouldnt_think_much_week", label: "I wouldn't think much of it", dimensionContributions: { independence: 2, connection: -1 } },
          { key: "depends_on_context_week", label: "It depends entirely on the context", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "intimacy_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "holding_back_dynamic_followup",
      trigger: { questionKey: "holding_back_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "rarely_safe_signal",
      trigger: { questionKey: "trust_extension", op: "answered_option", optionKey: "rarely_fully_safe" },
      action: { type: "ask_followup", followupQuestionKey: "trust_rarely_safe_deep_dive" },
      priority: 6,
    },
    {
      key: "receiving_harder_signal",
      trigger: { questionKey: "affection_receiving", op: "answered_option", optionKey: "much_harder_than_giving" },
      action: { type: "ask_followup", followupQuestionKey: "receiving_affection_deep_dive" },
      priority: 5,
    },
    {
      key: "high_independence_signal_intimacy",
      trigger: { questionKey: "independence_within_intimacy", dimensionKey: "independence", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "independence_intimacy_deep_dive" },
      priority: 4,
    },
    {
      key: "low_boundary_communication_signal",
      trigger: { questionKey: "boundary_pushed", op: "answered_option", optionKey: "rarely_notice_boundary" },
      action: { type: "ask_followup", followupQuestionKey: "boundary_communication_scale" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "deep_connector",
      name: "The Deep Connector",
      descriptionTemplate:
        "Your responses suggest trust and vulnerability come fairly naturally to you once someone earns a place in your life. You don't appear to hold much back — closeness seems to be something you build by actually showing up as yourself.",
      matchingRule: {
        dimensionRanges: { trust: [65, 100], vulnerability: [60, 100] },
        optionalConditions: { emotional_openness: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "selective_connector",
      name: "The Selective Connector",
      descriptionTemplate:
        "Your responses suggest you hold fairly clear boundaries, but that doesn't appear to limit how deeply you connect with the people who make it through them. Intimacy looks less common for you, and more concentrated.",
      matchingRule: {
        dimensionRanges: { boundaries: [60, 100], connection: [50, 100] },
        optionalConditions: { trust: [0, 55] },
      },
      priority: 4,
    },
    {
      key: "trust_builder",
      name: "The Trust Builder",
      descriptionTemplate:
        "Your responses suggest closeness needs to be earned gradually for you — security appears to come before real openness, not the other way around. Once that foundation is there, though, your answers suggest it tends to hold.",
      matchingRule: {
        dimensionRanges: { security: [60, 100], trust: [0, 55] },
        optionalConditions: { communication: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "private_heart",
      name: "The Private Heart",
      descriptionTemplate:
        "Your responses suggest you keep your inner world largely to yourself, with a strong instinct to maintain independence even inside close relationships. This isn't necessarily about distrust — it may simply be how you stay grounded.",
      matchingRule: {
        dimensionRanges: { vulnerability: [0, 40], boundaries: [60, 100], independence: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "open_connector",
      name: "The Open Connector",
      descriptionTemplate:
        "Your responses suggest you express what you feel fairly openly, both emotionally and through visible affection. Closeness appears to show up quickly and clearly in how you communicate care.",
      matchingRule: {
        dimensionRanges: { emotional_openness: [65, 100], affection_expression: [60, 100] },
      },
      priority: 4,
    },
    {
      key: "self_protector",
      name: "The Self-Protector",
      descriptionTemplate:
        "Your responses suggest a strong instinct to keep your guard up until safety is thoroughly established, extending trust cautiously and independence generously. This tends to keep you steady, though it may leave others working harder than they expect to feel truly let in.",
      matchingRule: {
        dimensionRanges: { vulnerability: [0, 40], trust: [0, 45], independence: [60, 100] },
        excludeConditions: { boundaries: [75, 100] },
      },
      priority: 3,
    },
    {
      key: "slow_opener",
      name: "The Slow Opener",
      descriptionTemplate:
        "Your responses suggest you genuinely want closeness, but you appear to need a longer runway to get there than most — boundaries loosen gradually as trust accumulates, rather than all at once.",
      matchingRule: {
        dimensionRanges: { connection: [55, 100], vulnerability: [0, 50] },
        optionalConditions: { boundaries: [45, 100] },
        excludeConditions: { independence: [75, 100] },
      },
      priority: 4,
    },
    {
      key: "balanced_intimate",
      name: "The Balanced Intimate",
      descriptionTemplate:
        "Your responses don't show a strong lean toward one extreme — openness and boundaries, closeness and independence, appear fairly evenly held. This suggests real flexibility in how much of yourself you share, depending on who's in front of you.",
      matchingRule: {
        dimensionRanges: { connection: [45, 70], vulnerability: [40, 65] },
      },
      priority: 0,
    },
  ],

  freeResultTemplate: {
    headline: "Your intimacy pattern is:",
    insightIntro:
      "Your responses suggest a specific way you build emotional closeness — how much you let people see, and what needs to be true before that starts to feel safe.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you experience intimacy.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Intimacy Profile:",
    shareTextTemplate: "I discovered my INNER Intimacy Profile: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "intimacy.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "intimacy.dominant_pattern" },
    { key: "trust_and_vulnerability", title: "Trust & Vulnerability", promptRef: "intimacy.trust_and_vulnerability" },
    { key: "how_closeness_feels_safe", title: "What Makes Closeness Feel Safe", promptRef: "intimacy.how_closeness_feels_safe" },
    { key: "your_boundaries", title: "Your Boundaries", promptRef: "intimacy.your_boundaries" },
    { key: "how_you_express_affection", title: "How You Express Affection", promptRef: "intimacy.how_you_express_affection" },
    { key: "communication_in_closeness", title: "Communication in Closeness", promptRef: "intimacy.communication_in_closeness" },
    { key: "strengths", title: "Your Strengths", promptRef: "intimacy.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "intimacy.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "intimacy.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "intimacy.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "intimacy.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "vulnerability",
      condition: { dimensionRanges: { vulnerability: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers pointed to vulnerability shaping a lot of this pattern — want to see the fuller shape of that on its own?",
    },
    {
      assessmentSlug: "connection",
      condition: { dimensionRanges: { connection: [55, 100] } },
      weight: 0.7,
      bridgeCopy: "Curious what specifically deepens connection and attraction for you, beyond emotional closeness?",
    },
    {
      assessmentSlug: "love",
      condition: { dimensionRanges: { trust: [55, 100] } },
      weight: 0.6,
      bridgeCopy: "Want to see how this pattern of trust and closeness shows up right from the very beginning of something new?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
