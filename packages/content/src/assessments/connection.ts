import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "Connection & Desire Profile" — /connection. What creates a deeper sense
 * of connection and attraction — kept within personal reflection and
 * relationship discovery, never explicit (docs/ARCHITECTURE.md §3).
 */
export const connectionAssessment: AssessmentConfig = {
  slug: "connection",
  name: "Connection & Desire Profile",
  category: "relationships",
  description: "A short, adaptive conversation about what actually creates a deeper sense of connection and interest for you.",
  hook: "Attraction has a shape. Most people have never mapped their own.",
  targetAudience: "Adults curious about what genuinely deepens connection and interest for them.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "novelty", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "spontaneity", weight: 1 },
    { key: "affection_expression", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "security", weight: 1 },
    { key: "independence", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "novelty_high_security",
      label: "craving new experiences together while also wanting real predictability underneath",
      dimensionA: "novelty",
      thresholdA: 60,
      dimensionB: "security",
      thresholdB: 60,
    },
    {
      key: "curiosity_low_trust",
      label: "feeling genuinely curious about people while still holding back full trust",
      dimensionA: "curiosity",
      thresholdA: 60,
      dimensionB: "trust",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "what_pulls_you_in",
        type: "single_select",
        isCore: true,
        prompt: "What tends to pull you in most, when you're getting to know someone?",
        options: [
          { key: "emotional_depth_pull", label: "Emotional depth", dimensionContributions: { connection: 2, affection_expression: 1 } },
          { key: "unpredictability_pull", label: "A bit of unpredictability", dimensionContributions: { novelty: 2, spontaneity: 1 } },
          { key: "shared_curiosity_pull", label: "Shared curiosity about the world", dimensionContributions: { curiosity: 2 } },
          { key: "consistency_pull", label: "Consistency and steadiness", dimensionContributions: { security: 2, trust: 1 } },
        ],
      },
      {
        key: "connection_deepening_scale",
        type: "scale",
        isCore: true,
        prompt: "How much does emotional depth need to be there for you to feel real attraction?",
        scaleMax: 5,
        scaleDimension: "connection",
      },
      {
        key: "novelty_or_routine",
        type: "single_select",
        isCore: true,
        prompt: "In a connection that's going well, do you find yourself craving new experiences or comfortable routine?",
        options: [
          { key: "new_experiences_crave", label: "New experiences, often", dimensionContributions: { novelty: 2, curiosity: 1 } },
          { key: "a_bit_of_both_crave", label: "A healthy mix of both", dimensionContributions: {} },
          { key: "mostly_routine_crave", label: "Mostly comfortable routine", dimensionContributions: { novelty: -2, security: 1 } },
          { key: "routine_with_surprises_crave", label: "Routine, with occasional surprises", dimensionContributions: { security: 1, spontaneity: 1 } },
        ],
      },
      {
        key: "curiosity_about_people_scale",
        type: "scale",
        isCore: true,
        prompt: "How curious are you, generally, about how other people think and feel?",
        scaleMax: 5,
        scaleDimension: "curiosity",
      },
      {
        key: "trust_before_desire",
        type: "single_select",
        isCore: true,
        prompt: "How much does trust need to be established before real interest deepens for you?",
        options: [
          { key: "trust_first_deep", label: "Trust really needs to come first", dimensionContributions: { trust: 2, security: 1 } },
          { key: "grows_alongside", label: "They tend to grow alongside each other", dimensionContributions: { trust: 1, connection: 1 } },
          { key: "attraction_can_precede_trust", label: "Attraction can be there before trust", dimensionContributions: { trust: -1, curiosity: 1 } },
          { key: "not_closely_linked", label: "The two aren't closely linked for me", dimensionContributions: { independence: 1 } },
        ],
      },
      {
        key: "spontaneity_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you enjoy doing something unplanned with someone you're interested in?",
        scaleMax: 5,
        scaleDimension: "spontaneity",
      },
      {
        key: "affection_expression_natural_connection",
        type: "single_select",
        isCore: true,
        prompt: "When interest turns into real affection, how do you naturally show it?",
        options: [
          { key: "say_it_connection", label: "I say it fairly directly", dimensionContributions: { affection_expression: 2, communication: 1 } },
          { key: "show_through_attention", label: "Through focused attention", dimensionContributions: { affection_expression: 1, connection: 1 } },
          { key: "through_shared_experiences", label: "Through creating shared experiences", dimensionContributions: { novelty: 1, affection_expression: 1 } },
          { key: "dont_show_it_much_connection", label: "Honestly, I don't show it much", dimensionContributions: { affection_expression: -2 } },
        ],
      },
      {
        key: "communication_of_interest",
        type: "single_select",
        isCore: true,
        prompt: "When you're interested in someone, how clearly do you communicate it?",
        options: [
          { key: "very_clearly_interest", label: "Very clearly", dimensionContributions: { communication: 2 } },
          { key: "through_actions_interest", label: "Mostly through actions, not words", dimensionContributions: { communication: 1, affection_expression: 1 } },
          { key: "cautiously_interest", label: "Cautiously, testing the waters first", dimensionContributions: { communication: -1, security: 1 } },
          { key: "rarely_directly_interest", label: "Rarely directly at all", dimensionContributions: { communication: -2 } },
        ],
      },
      {
        key: "security_in_connection_scale",
        type: "scale",
        isCore: true,
        prompt: "How much predictability do you need to feel secure while a connection is deepening?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "independence_within_desire",
        type: "single_select",
        isCore: true,
        prompt: "Even amid strong attraction, how important is it to keep your own life and interests intact?",
        options: [
          { key: "very_important_desire", label: "Very important", dimensionContributions: { independence: 2 } },
          { key: "somewhat_important_desire", label: "Somewhat important", dimensionContributions: { independence: 1 } },
          { key: "happy_to_merge_desire", label: "I'm happy to let it merge in", dimensionContributions: { independence: -2, connection: 1 } },
          { key: "depends_on_the_person_desire", label: "It depends on the person", dimensionContributions: {} },
        ],
      },
      {
        key: "what_sustains_interest",
        type: "single_select",
        isCore: true,
        prompt: "Once initial attraction settles, what actually keeps your interest alive?",
        options: [
          { key: "ongoing_novelty_sustains", label: "Ongoing novelty and surprise", dimensionContributions: { novelty: 2, spontaneity: 1 } },
          { key: "deepening_understanding_sustains", label: "Deepening emotional understanding", dimensionContributions: { connection: 2, curiosity: 1 } },
          { key: "reliability_sustains", label: "Reliability and follow-through", dimensionContributions: { security: 2, trust: 1 } },
          { key: "not_sure_sustains", label: "Honestly, I'm not always sure", dimensionContributions: {} },
        ],
      },
      {
        key: "boredom_response_connection",
        type: "single_select",
        isCore: true,
        prompt: "When a connection starts feeling routine, what's your instinct?",
        options: [
          { key: "introduce_something_new", label: "Introduce something new", dimensionContributions: { novelty: 2, spontaneity: 1 } },
          { key: "talk_about_it_connection", label: "Talk about it openly", dimensionContributions: { communication: 2 } },
          { key: "assume_its_just_a_phase", label: "Assume it's just a natural phase", dimensionContributions: { security: 1 } },
          { key: "quietly_lose_interest", label: "Quietly start losing interest", dimensionContributions: { novelty: 1, connection: -1 } },
        ],
      },
      {
        key: "curiosity_about_partner",
        type: "single_select",
        isCore: true,
        prompt: "How much do you actively try to learn new things about someone you're already close to?",
        options: [
          { key: "constantly_curious", label: "Constantly — there's always more to learn", dimensionContributions: { curiosity: 2, connection: 1 } },
          { key: "sometimes_curious", label: "Sometimes, when something prompts it", dimensionContributions: { curiosity: 1 } },
          { key: "assume_i_know_them", label: "I assume I mostly already know them", dimensionContributions: { curiosity: -2 } },
          { key: "not_something_i_think_about", label: "Not something I actively think about", dimensionContributions: {} },
        ],
      },
      {
        key: "connection_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a moment you felt a real spark of connection with someone. What created it?",
        dynamicFollowupCandidates: ["spark_what_specifically", "spark_how_often"],
      },
      {
        key: "losing_interest_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a time your interest in someone faded. What changed?",
        dynamicFollowupCandidates: ["fading_specific_cause", "fading_pattern"],
      },
    ],
    adaptivePool: [
      {
        key: "spark_what_specifically",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, what specifically created that spark?",
        options: [
          { key: "unexpected_honesty", label: "Unexpected honesty", dimensionContributions: { connection: 2, trust: 1 } },
          { key: "shared_curiosity_spark", label: "A shared curiosity about something", dimensionContributions: { curiosity: 2 } },
          { key: "an_unplanned_moment", label: "An unplanned moment together", dimensionContributions: { spontaneity: 2, novelty: 1 } },
          { key: "not_sure_spark", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "spark_how_often",
        type: "single_select",
        isCore: false,
        prompt: "Does that kind of spark happen often for you, or is it rare?",
        options: [
          { key: "fairly_often_spark", label: "Fairly often", dimensionContributions: { curiosity: 1, novelty: 1 } },
          { key: "with_the_right_person_spark", label: "Only with the right kind of person", dimensionContributions: { trust: 1 } },
          { key: "quite_rare_spark", label: "Quite rare, honestly", dimensionContributions: { security: 1 } },
          { key: "that_was_unusual_spark", label: "That moment was unusual for me", dimensionContributions: {} },
        ],
      },
      {
        key: "fading_specific_cause",
        type: "single_select",
        isCore: false,
        prompt: "What was underneath your interest fading, looking back?",
        options: [
          { key: "it_got_too_predictable", label: "It got too predictable", dimensionContributions: { novelty: 2 } },
          { key: "emotional_connection_stalled", label: "The emotional connection stalled", dimensionContributions: { connection: 2 } },
          { key: "trust_never_fully_formed", label: "Trust never fully formed", dimensionContributions: { trust: -1 } },
          { key: "not_sure_cause", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "fading_pattern",
        type: "single_select",
        isCore: false,
        prompt: "Does that same thing tend to happen across your connections, or was it specific to that one?",
        options: [
          { key: "happens_often_fading", label: "It happens fairly often", dimensionContributions: { novelty: 1 } },
          { key: "specific_to_that_one_fading", label: "That felt specific to that situation", dimensionContributions: {} },
          { key: "never_really_noticed_fading", label: "I've never really tracked it", dimensionContributions: {} },
          { key: "only_certain_dynamics_fading", label: "Only in certain kinds of dynamics", dimensionContributions: {} },
        ],
      },
      {
        key: "trust_first_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What does having trust in place actually give the connection, for you?",
        options: [
          { key: "safety_to_be_curious", label: "Safety to actually be curious and open", dimensionContributions: { curiosity: 1, security: 1 } },
          { key: "room_for_real_novelty", label: "Room to try new things without worry", dimensionContributions: { novelty: 1 } },
          { key: "just_a_baseline_requirement", label: "It's just a baseline requirement", dimensionContributions: { security: 1 } },
          { key: "not_sure_gives_trust", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "novelty_seeking_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "When you introduce something new into a connection, what are you usually hoping for?",
        options: [
          { key: "reignite_excitement", label: "To reignite excitement", dimensionContributions: { novelty: 2 } },
          { key: "learn_something_new_about_them", label: "To learn something new about them", dimensionContributions: { curiosity: 2 } },
          { key: "just_enjoy_the_moment", label: "Just to enjoy the moment itself", dimensionContributions: { spontaneity: 1 } },
          { key: "not_sure_hoping_novelty", label: "I'm not sure I think about it that much", dimensionContributions: {} },
        ],
      },
      {
        key: "affection_expression_scale_connection",
        type: "scale",
        isCore: false,
        prompt: "How openly do you show interest, even before you know it's mutual?",
        scaleMax: 5,
        scaleDimension: "affection_expression",
      },
      {
        key: "communication_directness_scale_connection",
        type: "scale",
        isCore: false,
        prompt: "How directly do you tell someone you're interested in them, rather than waiting for them to notice?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "independence_deep_dive_connection",
        type: "single_select",
        isCore: false,
        prompt: "What does keeping your own life intact actually protect, when a connection deepens?",
        options: [
          { key: "sense_of_self_connection", label: "A clear sense of who I am", dimensionContributions: { independence: 2 } },
          { key: "the_ability_to_walk_away", label: "The ability to walk away if needed", dimensionContributions: { security: -1, independence: 1 } },
          { key: "just_a_practical_preference", label: "It's mostly just a practical preference", dimensionContributions: { independence: 1 } },
          { key: "not_sure_protects_connection", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "curiosity_fading_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "When you feel like you already know someone fully, what happens to your interest?",
        options: [
          { key: "it_settles_into_something_calmer", label: "It settles into something calmer, not weaker", dimensionContributions: { connection: 1, security: 1 } },
          { key: "it_genuinely_fades_a_bit", label: "It genuinely fades a little", dimensionContributions: { curiosity: -1, novelty: 1 } },
          { key: "i_look_for_new_layers", label: "I start looking for new layers to discover", dimensionContributions: { curiosity: 2 } },
          { key: "hasnt_really_happened_curiosity", label: "That hasn't really happened to me", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "connection_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "losing_interest_dynamic_followup",
      trigger: { questionKey: "losing_interest_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "trust_first_signal",
      trigger: { questionKey: "trust_before_desire", op: "answered_option", optionKey: "trust_first_deep" },
      action: { type: "ask_followup", followupQuestionKey: "trust_first_deep_dive" },
      priority: 6,
    },
    {
      key: "novelty_signal",
      trigger: { questionKey: "novelty_or_routine", op: "answered_option", optionKey: "new_experiences_crave" },
      action: { type: "ask_followup", followupQuestionKey: "novelty_seeking_deep_dive" },
      priority: 5,
    },
    {
      key: "high_independence_signal_connection",
      trigger: { questionKey: "independence_within_desire", dimensionKey: "independence", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "independence_deep_dive_connection" },
      priority: 4,
    },
    {
      key: "assume_know_them_signal",
      trigger: { questionKey: "curiosity_about_partner", op: "answered_option", optionKey: "assume_i_know_them" },
      action: { type: "ask_followup", followupQuestionKey: "curiosity_fading_deep_dive" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "connection_seeker",
      name: "The Connection Seeker",
      descriptionTemplate:
        "Your responses suggest emotional depth is what actually creates attraction for you — surface-level chemistry doesn't appear to be enough on its own. Once real connection is there, your interest looks like it deepens quickly.",
      matchingRule: {
        dimensionRanges: { connection: [65, 100] },
        optionalConditions: { curiosity: [40, 70] },
      },
      priority: 5,
    },
    {
      key: "novelty_explorer",
      name: "The Novelty Explorer",
      descriptionTemplate:
        "Your responses suggest new experiences and unfamiliar territory are what keep a connection alive for you. Curiosity about the world and the person both seem to feed into the same appetite for discovery.",
      matchingRule: {
        dimensionRanges: { novelty: [65, 100], curiosity: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "emotional_connector",
      name: "The Emotional Connector",
      descriptionTemplate:
        "Your responses suggest you connect and express affection in the same breath — once interest is there, you tend to show it fairly openly, and closeness itself seems to be part of what draws you in further.",
      matchingRule: {
        dimensionRanges: { connection: [60, 100], affection_expression: [60, 100] },
      },
      priority: 4,
    },
    {
      key: "trust_first",
      name: "The Trust First",
      descriptionTemplate:
        "Your responses suggest real attraction only fully forms once trust and predictability are established — for you, safety appears to be a precondition for desire, not a byproduct of it.",
      matchingRule: {
        dimensionRanges: { trust: [65, 100], security: [55, 100] },
        optionalConditions: { spontaneity: [0, 50] },
      },
      priority: 5,
    },
    {
      key: "spontaneous_connector",
      name: "The Spontaneous Connector",
      descriptionTemplate:
        "Your responses suggest unplanned moments carry real weight in how connection forms for you — spontaneity and novelty appear to work together to keep interest genuinely alive.",
      matchingRule: {
        dimensionRanges: { spontaneity: [65, 100], novelty: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "selective_explorer",
      name: "The Selective Explorer",
      descriptionTemplate:
        "Your responses suggest genuine curiosity about people, paired with real caution about how quickly you extend trust. You appear drawn to explore, but on a timeline that stays firmly your own.",
      matchingRule: {
        dimensionRanges: { curiosity: [55, 100], trust: [0, 50] },
      },
      priority: 3,
    },
    {
      key: "security_connector",
      name: "The Security Connector",
      descriptionTemplate:
        "Your responses suggest predictability, not novelty, is what actually deepens connection for you. A known, steady dynamic appears to feel more compelling than the unfamiliar.",
      matchingRule: {
        dimensionRanges: { security: [65, 100], novelty: [0, 45] },
      },
      priority: 4,
    },
    {
      key: "balanced_connector",
      name: "The Balanced Connector",
      descriptionTemplate:
        "Your responses don't show a strong lean toward one extreme — emotional depth, novelty, and security all appear to play a role for you, rather than one dominating. This suggests real range in what can spark your interest.",
      matchingRule: {
        dimensionRanges: { connection: [45, 70], curiosity: [35, 65] },
      },
      priority: 0,
    },
  ],

  freeResultTemplate: {
    headline: "Your connection pattern is:",
    insightIntro:
      "Your responses suggest a specific combination of what actually deepens interest for you — some mix of emotional depth, novelty, and security.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in what creates connection for you.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Connection & Desire Profile:",
    shareTextTemplate: "I discovered my INNER Connection & Desire Profile: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "connection.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "connection.dominant_pattern" },
    { key: "what_creates_connection", title: "What Creates Connection for You", promptRef: "connection.what_creates_connection" },
    { key: "novelty_and_security", title: "Novelty & Security", promptRef: "connection.novelty_and_security" },
    { key: "trust_and_attraction", title: "Trust & Attraction", promptRef: "connection.trust_and_attraction" },
    { key: "how_you_show_interest", title: "How You Show Interest", promptRef: "connection.how_you_show_interest" },
    { key: "strengths", title: "Your Strengths", promptRef: "connection.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "connection.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "connection.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "connection.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "connection.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { connection: [55, 100] } },
      weight: 1,
      bridgeCopy: "Your answers point to emotional depth mattering a lot in what draws you in — want to see how that extends into deeper intimacy?",
    },
    {
      assessmentSlug: "love",
      condition: { dimensionRanges: { trust: [0, 55] } },
      weight: 0.7,
      bridgeCopy: "Curious how this pattern shows up right from the very start of falling for someone?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
