import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "Your Jealousy Profile" — /jealousy. Positioned as how someone responds
 * to uncertainty, comparison, and perceived threat in relationships — never
 * framed as pathology (docs/ARCHITECTURE.md §3, §4.1 non-diagnostic
 * guardrail applies to every generated section here just like LOVE).
 */
export const jealousyAssessment: AssessmentConfig = {
  slug: "jealousy",
  name: "Your Jealousy Profile",
  category: "relationships",
  description: "How you respond to uncertainty, comparison, and perceived threats in relationships.",
  hook: "Everyone has a guard. The interesting part is what's behind it.",
  targetAudience: "Adults curious about their own reactions to uncertainty and comparison in relationships.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "security", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "comparison", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "uncertainty", weight: 1 },
    { key: "control", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "emotional_regulation", weight: 1 },
    { key: "independence", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "trust_high_control",
      label: "saying you trust easily while still wanting to know a lot about where things stand",
      dimensionA: "trust",
      thresholdA: 60,
      dimensionB: "control",
      thresholdB: 60,
    },
    {
      key: "comparison_low_validation_awareness",
      label: "comparing yourself to others fairly often while not always naming how much reassurance you actually want",
      dimensionA: "comparison",
      thresholdA: 60,
      dimensionB: "communication",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "scenario_closeness_with_other",
        type: "single_select",
        isCore: true,
        prompt: "You notice someone you care about becoming unusually close to another person. What's closest to your first reaction?",
        options: [
          { key: "curious_not_worried", label: "Curious, but not worried", dimensionContributions: { security: 2, trust: 1 } },
          { key: "want_to_understand", label: "I want to understand the dynamic", dimensionContributions: { communication: 2 } },
          { key: "quietly_track_it", label: "I start quietly paying closer attention", dimensionContributions: { control: 2, communication: -1 } },
          { key: "feel_a_pull_of_comparison", label: "I feel a pull to compare myself to them", dimensionContributions: { comparison: 2, validation: 1 } },
        ],
      },
      {
        key: "uncertainty_tolerance_scale",
        type: "scale",
        isCore: true,
        prompt: "How okay are you with not knowing exactly where you stand with someone?",
        scaleMax: 5,
        scaleDimension: "uncertainty",
      },
      {
        key: "trust_default",
        type: "single_select",
        isCore: true,
        prompt: "When someone you're with spends time with people you don't know, your instinct is...",
        options: [
          { key: "trust_it", label: "To trust it completely", dimensionContributions: { trust: 2 } },
          { key: "mildly_curious", label: "Mildly curious, nothing more", dimensionContributions: { trust: 1, comparison: 1 } },
          { key: "want_details", label: "To want some details", dimensionContributions: { control: 2, communication: 1 } },
          { key: "assume_the_worst", label: "To assume the worst a little", dimensionContributions: { trust: -2, security: -1 } },
        ],
      },
      {
        key: "validation_need_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you need to hear that you're still valued, even when nothing seems wrong?",
        scaleMax: 5,
        scaleDimension: "validation",
      },
      {
        key: "comparison_instinct",
        type: "single_select",
        isCore: true,
        prompt: "When you think about someone you're interested in, do you compare yourself to others in their life?",
        options: [
          { key: "rarely", label: "Rarely", dimensionContributions: { comparison: -2 } },
          { key: "sometimes", label: "Sometimes", dimensionContributions: { comparison: 1 } },
          { key: "often", label: "Fairly often", dimensionContributions: { comparison: 2, validation: 1 } },
          { key: "constantly", label: "Pretty much constantly", dimensionContributions: { comparison: 3, security: -1 } },
        ],
      },
      {
        key: "emotional_regulation_response",
        type: "single_select",
        isCore: true,
        prompt: "When a jealous feeling shows up, what happens next for you?",
        options: [
          { key: "passes_quickly", label: "It passes fairly quickly on its own", dimensionContributions: { emotional_regulation: 2 } },
          { key: "sits_with_me_a_while", label: "It sits with me for a while", dimensionContributions: { emotional_regulation: -1 } },
          { key: "i_act_on_it", label: "I usually act on it somehow", dimensionContributions: { emotional_regulation: -2, control: 1 } },
          { key: "i_hide_it", label: "I hide it and say nothing", dimensionContributions: { emotional_regulation: -1, communication: -2 } },
        ],
      },
      {
        key: "control_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you want to know about where a partner is and who they're with?",
        scaleMax: 5,
        scaleDimension: "control",
      },
      {
        key: "communication_when_uneasy",
        type: "single_select",
        isCore: true,
        prompt: "When you feel uneasy about a relationship, what do you usually do?",
        options: [
          { key: "say_it_directly", label: "Say it directly", dimensionContributions: { communication: 2 } },
          { key: "hint_at_it", label: "Hint at it and hope they pick up on it", dimensionContributions: { communication: -1 } },
          { key: "keep_it_to_myself", label: "Keep it entirely to myself", dimensionContributions: { communication: -2, emotional_regulation: -1 } },
          { key: "ask_indirect_questions", label: "Ask indirect questions to test the waters", dimensionContributions: { communication: -1, control: 1 } },
        ],
      },
      {
        key: "independence_identity_scale",
        type: "scale",
        isCore: true,
        prompt: "How much does your sense of self stay steady, regardless of how a relationship is going?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
      {
        key: "security_first_instinct",
        type: "single_select",
        isCore: true,
        prompt: "If a partner mentions an ex in a completely neutral way, what's your first internal reaction?",
        options: [
          { key: "no_reaction", label: "Genuinely no reaction", dimensionContributions: { security: 2, trust: 1 } },
          { key: "mild_curiosity", label: "Mild curiosity", dimensionContributions: { security: 1 } },
          { key: "slight_tension", label: "A slight flicker of tension", dimensionContributions: { security: -1, comparison: 1 } },
          { key: "need_more_context", label: "A wish for a bit more context", dimensionContributions: { control: 1, communication: 1 } },
        ],
      },
      {
        key: "trust_rebuilding_instinct",
        type: "single_select",
        isCore: true,
        prompt: "If your trust in someone were shaken, what would you do first?",
        options: [
          { key: "talk_to_them", label: "Talk to them directly", dimensionContributions: { communication: 2, trust: 1 } },
          { key: "watch_more_closely", label: "Start watching more closely", dimensionContributions: { control: 2, trust: -1 } },
          { key: "pull_back_a_bit", label: "Pull back a little, on my own", dimensionContributions: { independence: 1, trust: -1 } },
          { key: "assume_something_is_wrong", label: "Assume something is genuinely wrong", dimensionContributions: { security: -2, comparison: 1 } },
        ],
      },
      {
        key: "validation_from_partner",
        type: "single_select",
        isCore: true,
        prompt: "How much do compliments or reassurance from a partner change how secure you feel?",
        options: [
          { key: "changes_a_lot", label: "Quite a lot", dimensionContributions: { validation: 3, security: -1 } },
          { key: "changes_a_little", label: "A little", dimensionContributions: { validation: 1 } },
          { key: "doesnt_change_much", label: "Not much, honestly", dimensionContributions: { validation: -2, security: 1 } },
          { key: "i_dont_expect_it", label: "I don't really expect it", dimensionContributions: { validation: -2, independence: 1 } },
        ],
      },
      {
        key: "comparison_social_media",
        type: "single_select",
        isCore: true,
        prompt: "Seeing a partner interact online with someone conventionally attractive, your instinct is...",
        options: [
          { key: "nothing_much", label: "Nothing much, honestly", dimensionContributions: { comparison: -2, security: 1 } },
          { key: "notice_but_let_it_go", label: "I notice it, then let it go", dimensionContributions: { comparison: 1, emotional_regulation: 1 } },
          { key: "feel_a_spike_i_manage", label: "A spike of something I manage on my own", dimensionContributions: { comparison: 2, emotional_regulation: -1 } },
          { key: "feel_a_spike_i_act_on", label: "A spike I usually act on somehow", dimensionContributions: { comparison: 3, control: 1 } },
        ],
      },
      {
        key: "control_partner_schedule",
        type: "single_select",
        isCore: true,
        prompt: "How do you feel about not knowing a partner's exact schedule on a given day?",
        options: [
          { key: "completely_fine", label: "Completely fine", dimensionContributions: { control: -2, trust: 1 } },
          { key: "slightly_uneasy", label: "A little uneasy", dimensionContributions: { control: 1 } },
          { key: "prefer_to_know", label: "I'd prefer to know", dimensionContributions: { control: 2 } },
          { key: "need_to_know", label: "I really want to know", dimensionContributions: { control: 3, security: -1 } },
        ],
      },
      {
        key: "jealousy_scenario_open",
        type: "open_text",
        isCore: true,
        prompt: "Describe a moment jealousy showed up for you — what triggered it, and what did you do?",
        dynamicFollowupCandidates: ["jealousy_regret", "jealousy_pattern_recognition"],
        sensitive: true,
        difficulty: "deep",
      },
      {
        key: "uncertainty_open",
        type: "open_text",
        isCore: true,
        prompt: "When you don't know how someone feels about you, what goes through your mind?",
        dynamicFollowupCandidates: ["uncertainty_coping", "uncertainty_frequency"],
      },
    ],
    adaptivePool: [
      {
        key: "jealousy_regret",
        type: "single_select",
        isCore: false,
        prompt: "Looking back at that moment, how do you feel about how you handled it?",
        options: [
          { key: "wish_id_said_something", label: "I wish I'd said something instead of holding it in", dimensionContributions: { communication: 2, emotional_regulation: -1 } },
          { key: "wish_id_stayed_calmer", label: "I wish I'd stayed calmer in the moment", dimensionContributions: { emotional_regulation: 2 } },
          { key: "dont_regret_it", label: "I don't really regret it", dimensionContributions: { control: 1 } },
          { key: "not_sure_regret", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "jealousy_pattern_recognition",
        type: "single_select",
        isCore: false,
        prompt: "Does this happen often, or was this situation unusual?",
        options: [
          { key: "yes_this_happens_often", label: "It happens fairly often", dimensionContributions: { comparison: 1, security: -1 } },
          { key: "only_with_certain_people", label: "Only with certain people", dimensionContributions: {} },
          { key: "this_was_unusual", label: "This was pretty unusual for me", dimensionContributions: { security: 1 } },
          { key: "never_really_noticed", label: "I've never really tracked it", dimensionContributions: {} },
        ],
      },
      {
        key: "uncertainty_coping",
        type: "single_select",
        isCore: false,
        prompt: "In moments like that, what do you usually do?",
        options: [
          { key: "i_distract_myself", label: "Distract myself with something else", dimensionContributions: { independence: 1, emotional_regulation: 1 } },
          { key: "i_seek_reassurance", label: "Seek reassurance from them", dimensionContributions: { validation: 2 } },
          { key: "i_try_to_figure_it_out_logically", label: "Try to reason through it logically", dimensionContributions: { communication: 1, control: 1 } },
          { key: "it_consumes_me_for_a_while", label: "Let it consume my thoughts for a while", dimensionContributions: { emotional_regulation: -2, security: -1 } },
        ],
      },
      {
        key: "uncertainty_frequency",
        type: "single_select",
        isCore: false,
        prompt: "How often does that feeling of not knowing show up for you?",
        options: [
          { key: "often_freq", label: "Often", dimensionContributions: { security: -1, validation: 1 } },
          { key: "occasionally_freq", label: "Occasionally", dimensionContributions: {} },
          { key: "rarely_freq", label: "Rarely", dimensionContributions: { security: 1 } },
          { key: "this_was_a_first", label: "This was actually a first", dimensionContributions: {} },
        ],
      },
      {
        key: "scenario_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What are you usually hoping to find, when you pay closer attention like that?",
        options: [
          { key: "reassurance_nothings_wrong", label: "Reassurance nothing's wrong", dimensionContributions: { validation: 2, control: 1 } },
          { key: "evidence_id_be_right_to_worry", label: "Honestly, evidence I'd be right to worry", dimensionContributions: { comparison: 2, trust: -1 } },
          { key: "just_information", label: "Just information, nothing more", dimensionContributions: { control: 2 } },
          { key: "not_sure_what_id_find", label: "I'm not sure what I'm looking for", dimensionContributions: {} },
        ],
      },
      {
        key: "control_underlying_need",
        type: "single_select",
        isCore: false,
        prompt: "What does knowing exactly where someone is actually give you?",
        options: [
          { key: "a_sense_of_safety", label: "A sense of safety", dimensionContributions: { security: 1, control: 1 } },
          { key: "proof_nothing_is_wrong", label: "Proof that nothing is wrong", dimensionContributions: { trust: -1, comparison: 1 } },
          { key: "just_habit", label: "Honestly, it's mostly just habit", dimensionContributions: { control: 1 } },
          { key: "not_sure_need", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "comparison_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "When you compare yourself to someone else, what are you usually measuring?",
        options: [
          { key: "attractiveness", label: "How I measure up physically", dimensionContributions: { comparison: 2, validation: 1 } },
          { key: "how_much_they_have_in_common", label: "How much they have in common with my partner", dimensionContributions: { comparison: 1 } },
          { key: "how_easily_they_get_along", label: "How easily they seem to connect", dimensionContributions: { comparison: 2, security: -1 } },
          { key: "not_sure_what_exactly", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "regulation_after_spike",
        type: "single_select",
        isCore: false,
        prompt: "After a jealous feeling passes, how do you usually feel about having had it?",
        options: [
          { key: "understanding_with_myself", label: "Understanding with myself about it", dimensionContributions: { emotional_regulation: 2 } },
          { key: "a_little_embarrassed", label: "A little embarrassed", dimensionContributions: { emotional_regulation: -1, validation: 1 } },
          { key: "like_it_was_justified", label: "Like it was probably justified", dimensionContributions: { comparison: 1, trust: -1 } },
          { key: "i_dont_think_about_it_again", label: "I don't really think about it again", dimensionContributions: { emotional_regulation: 1, independence: 1 } },
        ],
      },
      {
        key: "security_baseline_scale",
        type: "scale",
        isCore: false,
        prompt: "How steady do you feel in a relationship when nothing in particular is wrong?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "mood_independence_scale",
        type: "scale",
        isCore: false,
        prompt: "How much does your day-to-day mood stay independent of how the relationship is going?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "jealousy_scenario_open", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "uncertainty_open_dynamic_followup",
      trigger: { questionKey: "uncertainty_open", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "track_signal",
      trigger: { questionKey: "scenario_closeness_with_other", op: "answered_option", optionKey: "quietly_track_it" },
      action: { type: "ask_followup", followupQuestionKey: "scenario_deep_dive" },
      priority: 6,
    },
    {
      key: "control_signal",
      trigger: { questionKey: "control_partner_schedule", op: "answered_option", optionKey: "need_to_know" },
      action: { type: "ask_followup", followupQuestionKey: "control_underlying_need" },
      priority: 6,
    },
    {
      key: "comparison_signal",
      trigger: { questionKey: "comparison_instinct", op: "answered_option", optionKey: "constantly" },
      action: { type: "ask_followup", followupQuestionKey: "comparison_deep_dive" },
      priority: 5,
    },
    {
      key: "regulation_signal",
      trigger: { questionKey: "emotional_regulation_response", dimensionKey: "emotional_regulation", op: "lte", value: 30 },
      action: { type: "ask_followup", followupQuestionKey: "regulation_after_spike" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "quiet_observer",
      name: "The Quiet Observer",
      descriptionTemplate:
        "Your responses suggest that when something feels off, you tend to watch and gather information rather than say anything out loud. There's a real self-control in that — though it also means the people close to you may not know a concern exists until it's already been quietly resolved, one way or another.",
      matchingRule: {
        dimensionRanges: { communication: [0, 45], emotional_regulation: [55, 100] },
        optionalConditions: { control: [50, 100] },
      },
      priority: 4,
    },
    {
      key: "security_seeker",
      name: "The Security Seeker",
      descriptionTemplate:
        "Your responses suggest your sense of security in a relationship isn't automatic — it appears to depend fairly heavily on active reassurance. This isn't the same as being unable to trust; it looks more like trust that needs to be regularly refreshed rather than assumed.",
      matchingRule: {
        dimensionRanges: { security: [0, 45], validation: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "direct_communicator",
      name: "The Direct Communicator",
      descriptionTemplate:
        "Your responses suggest that when uncertainty shows up, your instinct is to name it out loud rather than let it sit. Combined with a steady emotional response, this appears to let you address what's bothering you before it has much chance to grow.",
      matchingRule: {
        dimensionRanges: { communication: [65, 100], emotional_regulation: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "internal_processor",
      name: "The Internal Processor",
      descriptionTemplate:
        "Your responses suggest you work through jealousy privately and fully on your own terms, without needing to control the situation or say much about it. Your sense of self appears to stay fairly intact regardless of what's happening in the relationship.",
      matchingRule: {
        dimensionRanges: { independence: [65, 100], communication: [0, 50] },
        optionalConditions: { emotional_regulation: [55, 100] },
        excludeConditions: { control: [70, 100] },
      },
      priority: 4,
    },
    {
      key: "reassurance_seeker",
      name: "The Reassurance Seeker",
      descriptionTemplate:
        "Your responses suggest comparison and a need for reassurance tend to arrive together — noticing someone else often comes with a pull to measure yourself against them, followed by a wish for something that confirms you're still valued.",
      matchingRule: {
        dimensionRanges: { validation: [60, 100], comparison: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "independent_observer",
      name: "The Independent Observer",
      descriptionTemplate:
        "Your responses suggest you rarely measure yourself against other people, and your independence appears to hold steady even in moments that might unsettle others. Uncertainty doesn't seem to automatically read as threat for you.",
      matchingRule: {
        dimensionRanges: { independence: [60, 100], comparison: [0, 45] },
        optionalConditions: { control: [0, 50] },
      },
      priority: 3,
    },
    {
      key: "trusted_connector",
      name: "The Trusted Connector",
      descriptionTemplate:
        "Your responses suggest trust comes fairly naturally to you, and not knowing every detail doesn't seem to cost you much. This combination appears to leave real room for other people in your partner's life, without it registering as a threat.",
      matchingRule: {
        dimensionRanges: { trust: [60, 100], uncertainty: [55, 100] },
        optionalConditions: { validation: [0, 50] },
      },
      priority: 4,
    },
    {
      key: "uncertainty_sensitive",
      name: "The Uncertainty Sensitive",
      descriptionTemplate:
        "Your responses suggest not knowing is one of the harder things for you to sit with — when something is ambiguous, the instinct appears to be to resolve it, often by gathering more information or more control over the situation.",
      matchingRule: {
        dimensionRanges: { uncertainty: [0, 40], control: [55, 100] },
        optionalConditions: { comparison: [55, 100] },
      },
      priority: 5,
    },
  ],

  freeResultTemplate: {
    headline: "Your jealousy pattern is:",
    insightIntro:
      "Your responses suggest a specific way you respond to uncertainty, comparison, and perceived distance in relationships — a pattern worth understanding rather than judging.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you respond to uncertainty.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Jealousy Profile:",
    shareTextTemplate: "I discovered my INNER Jealousy Profile: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "jealousy.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "jealousy.dominant_pattern" },
    { key: "what_triggers_it", title: "What Tends to Trigger It", promptRef: "jealousy.what_triggers_it" },
    { key: "how_you_process", title: "How You Process It", promptRef: "jealousy.how_you_process" },
    { key: "communication_style", title: "How You Communicate It", promptRef: "jealousy.communication_style" },
    { key: "trust_and_comparison", title: "Trust & Comparison", promptRef: "jealousy.trust_and_comparison" },
    { key: "boundaries_and_control", title: "Boundaries & Control", promptRef: "jealousy.boundaries_and_control" },
    { key: "strengths", title: "Your Strengths", promptRef: "jealousy.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "jealousy.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "jealousy.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "jealousy.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "jealousy.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "relationship",
      condition: { dimensionRanges: { security: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers touched on uncertainty and control — want to see how that plays out across the whole shape of a relationship?",
    },
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { trust: [55, 100] } },
      weight: 0.7,
      bridgeCopy: "Trust seems to come fairly naturally to you here — curious how that extends into emotional intimacy?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
