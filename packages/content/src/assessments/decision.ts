import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Decision DNA" — /decision. Everyday, relationship, and hypothetical scenarios only — never financial or medical advice (docs/ARCHITECTURE.md §3). */
export const decisionAssessment: AssessmentConfig = {
  slug: "decision",
  name: "Your Decision DNA",
  category: "self",
  description: "A short, adaptive conversation about what actually drives your decisions when something important is at stake.",
  hook: "When something important is at stake, what actually drives your decisions?",
  targetAudience: "Adults curious about their own decision-making style under real stakes.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "analysis", weight: 1 },
    { key: "intuition", weight: 1 },
    { key: "risk", weight: 1 },
    { key: "certainty", weight: 1 },
    { key: "speed", weight: 1 },
    { key: "emotional_influence", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "control", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "action", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "analysis_high_speed",
      label: "wanting to think things through thoroughly while also feeling pressure to decide quickly",
      dimensionA: "analysis",
      thresholdA: 60,
      dimensionB: "speed",
      thresholdB: 60,
    },
    {
      key: "certainty_low_action",
      label: "wanting to feel fully sure before deciding, while also feeling the pull to just act",
      dimensionA: "certainty",
      thresholdA: 60,
      dimensionB: "action",
      thresholdB: 60,
    },
  ],

  questionBank: {
    core: [
      {
        key: "big_decision_first_move",
        type: "single_select",
        isCore: true,
        prompt: "When something important is genuinely at stake, what's your first move?",
        options: [
          { key: "list_out_the_options", label: "List out the options and weigh them", dimensionContributions: { analysis: 2, control: 1 } },
          { key: "notice_gut_reaction", label: "Notice what my gut says first", dimensionContributions: { intuition: 2 } },
          { key: "talk_it_through_with_someone", label: "Talk it through with someone I trust", dimensionContributions: { validation: 1, emotional_influence: 1 } },
          { key: "sit_with_it_a_while", label: "Sit with it for a while before doing anything", dimensionContributions: { certainty: 1, speed: -2 } },
        ],
      },
      {
        key: "analysis_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you rely on structured reasoning — pros and cons, weighing options — before deciding?",
        scaleMax: 5,
        scaleDimension: "analysis",
      },
      {
        key: "gut_feeling_trust",
        type: "single_select",
        isCore: true,
        prompt: "When your gut feeling contradicts the logical case, which usually wins?",
        options: [
          { key: "gut_usually_wins", label: "My gut, most of the time", dimensionContributions: { intuition: 2, analysis: -1 } },
          { key: "logic_usually_wins", label: "The logical case, most of the time", dimensionContributions: { analysis: 2, intuition: -1 } },
          { key: "depends_on_the_stakes", label: "Depends on how high the stakes are", dimensionContributions: {} },
          { key: "i_try_to_reconcile_both", label: "I try to find where they actually agree", dimensionContributions: { analysis: 1, intuition: 1 } },
        ],
      },
      {
        key: "risk_tolerance_scale",
        type: "scale",
        isCore: true,
        prompt: "How comfortable are you making a decision when the outcome is genuinely uncertain?",
        scaleMax: 5,
        scaleDimension: "risk",
      },
      {
        key: "certainty_need",
        type: "single_select",
        isCore: true,
        prompt: "How sure do you need to feel before you're willing to commit to a decision?",
        options: [
          { key: "mostly_sure_enough", label: "Mostly sure is enough", dimensionContributions: { certainty: -1, action: 1 } },
          { key: "quite_sure_needed", label: "I need to feel quite sure", dimensionContributions: { certainty: 2 } },
          { key: "fully_certain_needed", label: "I need to feel fully certain", dimensionContributions: { certainty: 3, flexibility: -1 } },
          { key: "comfortable_deciding_uncertain", label: "I'm comfortable deciding without full certainty", dimensionContributions: { certainty: -2, flexibility: 2 } },
        ],
      },
      {
        key: "decision_speed_scale",
        type: "scale",
        isCore: true,
        prompt: "Once you have enough information, how quickly do you move from noticing a decision to acting on it?",
        scaleMax: 5,
        scaleDimension: "speed",
      },
      {
        key: "emotional_influence_scenario",
        type: "single_select",
        isCore: true,
        prompt: "When you're deciding something important while also feeling emotional about it, what happens?",
        options: [
          { key: "emotion_shapes_the_call", label: "The emotion genuinely shapes the call", dimensionContributions: { emotional_influence: 2 } },
          { key: "i_wait_for_the_emotion_to_settle", label: "I wait for the emotion to settle first", dimensionContributions: { emotional_influence: -1, certainty: 1 } },
          { key: "i_try_to_set_it_aside", label: "I try to set it aside deliberately", dimensionContributions: { emotional_influence: -2, control: 1 } },
          { key: "i_dont_notice_it_much", label: "I don't notice it affecting me much either way", dimensionContributions: { emotional_influence: -1 } },
        ],
      },
      {
        key: "seeking_others_opinions",
        type: "single_select",
        isCore: true,
        prompt: "Before a big decision, how much do you seek out other people's opinions?",
        options: [
          { key: "a_lot_of_opinions", label: "A lot — I want multiple perspectives", dimensionContributions: { validation: 2 } },
          { key: "one_or_two_trusted_opinions", label: "One or two people I really trust", dimensionContributions: { validation: 1 } },
          { key: "mostly_decide_alone_opinions", label: "I mostly decide alone", dimensionContributions: { validation: -2, control: 1 } },
          { key: "share_after_not_before", label: "I share it after I've decided, not before", dimensionContributions: { validation: -1, control: 1 } },
        ],
      },
      {
        key: "control_scale_decision",
        type: "scale",
        isCore: true,
        prompt: "How much do you need to feel like you're steering the outcome, rather than letting things unfold?",
        scaleMax: 5,
        scaleDimension: "control",
      },
      {
        key: "changing_your_mind",
        type: "single_select",
        isCore: true,
        prompt: "Once you've made a decision, how open are you to changing it if new information shows up?",
        options: [
          { key: "very_open_to_changing", label: "Very open — I'll adjust immediately", dimensionContributions: { flexibility: 2 } },
          { key: "open_but_need_good_reason", label: "Open, but I need a genuinely good reason", dimensionContributions: { flexibility: 1, analysis: 1 } },
          { key: "reluctant_to_change", label: "Reluctant — I like to commit fully", dimensionContributions: { flexibility: -2, certainty: 1 } },
          { key: "rarely_reconsider", label: "I rarely reconsider once I've decided", dimensionContributions: { flexibility: -2, control: 1 } },
        ],
      },
      {
        key: "action_vs_deliberation",
        type: "single_select",
        isCore: true,
        prompt: "When you're torn between two good options, what usually happens?",
        options: [
          { key: "just_pick_one_and_move", label: "I just pick one and move forward", dimensionContributions: { action: 2, speed: 1 } },
          { key: "keep_deliberating_a_while", label: "I keep deliberating for a while longer", dimensionContributions: { action: -2, analysis: 1 } },
          { key: "look_for_a_tiebreaker", label: "I look for something to tip the balance", dimensionContributions: { analysis: 1, action: 1 } },
          { key: "wait_for_one_to_feel_more_right", label: "I wait until one starts to feel more right", dimensionContributions: { intuition: 1, action: -1 } },
        ],
      },
      {
        key: "hypothetical_move_decision",
        type: "single_select",
        isCore: true,
        prompt: "Imagine you're offered a genuinely exciting but uncertain opportunity that requires a fast answer. What do you do?",
        options: [
          { key: "say_yes_and_figure_it_out", label: "Say yes and figure out the details after", dimensionContributions: { action: 2, risk: 2 } },
          { key: "ask_for_more_time", label: "Ask for more time, even if it costs the opportunity", dimensionContributions: { certainty: 2, speed: -2 } },
          { key: "make_a_fast_gut_call", label: "Make a fast call based on gut instinct", dimensionContributions: { intuition: 2, speed: 2 } },
          { key: "decline_the_pressure", label: "Decline — I don't decide well under pressure", dimensionContributions: { risk: -2, certainty: 1 } },
        ],
      },
      {
        key: "relationship_decision_scenario",
        type: "single_select",
        isCore: true,
        prompt: "Deciding whether to bring up something important in a relationship, what do you do first?",
        options: [
          { key: "plan_out_what_to_say", label: "Plan out exactly what I want to say", dimensionContributions: { analysis: 2, control: 1 } },
          { key: "wait_for_the_right_feeling", label: "Wait until it feels like the right moment", dimensionContributions: { intuition: 1, certainty: 1 } },
          { key: "just_say_it_when_it_comes_up", label: "Just say it when it naturally comes up", dimensionContributions: { action: 2, flexibility: 1 } },
          { key: "check_with_someone_first", label: "Check with someone else first about how to approach it", dimensionContributions: { validation: 2 } },
        ],
      },
      {
        key: "regret_after_deciding",
        type: "single_select",
        isCore: true,
        prompt: "After making a decision, how much do you replay it wondering if you chose right?",
        options: [
          { key: "rarely_replay", label: "Rarely — once it's decided, it's decided", dimensionContributions: { certainty: -1, control: 1 } },
          { key: "sometimes_replay", label: "Sometimes, especially for bigger ones", dimensionContributions: {} },
          { key: "often_replay", label: "Often — I second-guess myself a fair amount", dimensionContributions: { certainty: 2, validation: 1 } },
          { key: "depends_entirely_on_outcome", label: "Depends entirely on how it turns out", dimensionContributions: {} },
        ],
      },
      {
        key: "decision_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a big decision you made and how you actually arrived at it.",
        dynamicFollowupCandidates: ["decision_confidence_after", "decision_would_change"],
      },
      {
        key: "hard_call_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a decision that was genuinely hard to make. What made it hard?",
        dynamicFollowupCandidates: ["hard_call_resolution", "hard_call_pattern"],
      },
    ],
    adaptivePool: [
      {
        key: "decision_confidence_after",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, how confident are you that it was the right call?",
        options: [
          { key: "very_confident_after", label: "Very confident", dimensionContributions: { certainty: -1, action: 1 } },
          { key: "mostly_confident_after", label: "Mostly confident", dimensionContributions: {} },
          { key: "still_unsure_after", label: "Honestly, still a little unsure", dimensionContributions: { certainty: 1 } },
          { key: "not_sure_ever_know_after", label: "I'm not sure you can ever fully know", dimensionContributions: { flexibility: 1 } },
        ],
      },
      {
        key: "decision_would_change",
        type: "single_select",
        isCore: false,
        prompt: "If you could redo how you made that decision, would you change your process?",
        options: [
          { key: "yes_more_analysis", label: "Yes, I'd analyze it more", dimensionContributions: { analysis: 1 } },
          { key: "yes_trust_gut_more", label: "Yes, I'd trust my gut more", dimensionContributions: { intuition: 1 } },
          { key: "no_same_process", label: "No, I'd do it the same way", dimensionContributions: { control: 1 } },
          { key: "not_sure_change", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "hard_call_resolution",
        type: "single_select",
        isCore: false,
        prompt: "What ultimately resolved it for you?",
        options: [
          { key: "ran_out_of_time_resolution", label: "I ran out of time to keep deliberating", dimensionContributions: { speed: 1, action: 1 } },
          { key: "a_conversation_resolution", label: "A conversation with someone", dimensionContributions: { validation: 1 } },
          { key: "a_moment_of_clarity_resolution", label: "A sudden moment of clarity", dimensionContributions: { intuition: 2 } },
          { key: "still_not_fully_resolved", label: "It's still not fully resolved for me", dimensionContributions: { certainty: 1 } },
        ],
      },
      {
        key: "hard_call_pattern",
        type: "single_select",
        isCore: false,
        prompt: "Do decisions like that tend to be hard for you specifically, or was that one unusual?",
        options: [
          { key: "hard_decisions_pattern", label: "That kind of decision is consistently hard for me", dimensionContributions: { certainty: 1 } },
          { key: "depends_on_the_domain_pattern", label: "Depends heavily on the area of life", dimensionContributions: {} },
          { key: "that_one_was_unusual_pattern", label: "That one was unusual", dimensionContributions: {} },
          { key: "never_really_tracked_pattern", label: "I've never really tracked it", dimensionContributions: {} },
        ],
      },
      {
        key: "sit_with_it_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What are you usually waiting for, when you sit with a decision for a while?",
        options: [
          { key: "waiting_for_clarity", label: "A sense of clarity to arrive", dimensionContributions: { intuition: 1, certainty: 1 } },
          { key: "waiting_for_more_information", label: "More information to become available", dimensionContributions: { analysis: 1 } },
          { key: "waiting_for_the_feeling_to_settle", label: "The emotional charge to settle first", dimensionContributions: { emotional_influence: 1 } },
          { key: "not_sure_waiting_for", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "rarely_reconsider_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What makes committing fully, without looking back, feel important to you?",
        options: [
          { key: "second_guessing_wastes_energy", label: "Second-guessing feels like wasted energy", dimensionContributions: { control: 1 } },
          { key: "i_trust_my_original_process", label: "I trust the process I used to get there", dimensionContributions: { analysis: 1, certainty: -1 } },
          { key: "changing_feels_like_failure", label: "Changing course can feel like a kind of failure", dimensionContributions: { certainty: 1, flexibility: -1 } },
          { key: "not_sure_why_commit", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "intuition_reliability_scale",
        type: "scale",
        isCore: false,
        prompt: "Looking back, how often has your gut instinct actually turned out to be right?",
        scaleMax: 5,
        scaleDimension: "intuition",
      },
      {
        key: "emotional_influence_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you think your mood on a given day changes what you'd decide?",
        scaleMax: 5,
        scaleDimension: "emotional_influence",
      },
      {
        key: "external_validation_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you need other people to agree with a decision for it to feel settled?",
        scaleMax: 5,
        scaleDimension: "validation",
      },
      {
        key: "action_orientation_scale",
        type: "scale",
        isCore: false,
        prompt: "Once you've decided, how quickly do you actually start acting on it?",
        scaleMax: 5,
        scaleDimension: "action",
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "decision_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "hard_call_dynamic_followup",
      trigger: { questionKey: "hard_call_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "sit_with_it_signal",
      trigger: { questionKey: "big_decision_first_move", op: "answered_option", optionKey: "sit_with_it_a_while" },
      action: { type: "ask_followup", followupQuestionKey: "sit_with_it_deep_dive" },
      priority: 6,
    },
    {
      key: "rarely_reconsider_signal",
      trigger: { questionKey: "changing_your_mind", op: "answered_option", optionKey: "rarely_reconsider" },
      action: { type: "ask_followup", followupQuestionKey: "rarely_reconsider_deep_dive" },
      priority: 6,
    },
    {
      key: "high_intuition_signal",
      trigger: { questionKey: "gut_feeling_trust", op: "answered_option", optionKey: "gut_usually_wins" },
      action: { type: "ask_followup", followupQuestionKey: "intuition_reliability_scale" },
      priority: 4,
    },
    {
      key: "low_certainty_tolerance_signal",
      trigger: { questionKey: "certainty_need", dimensionKey: "certainty", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "external_validation_scale" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "analytical_decider",
      name: "The Analytical Decider",
      descriptionTemplate:
        "Your responses suggest you decide through structured reasoning — weighing options, gathering information, working the problem systematically. Gut instinct doesn't appear to carry much independent weight for you until the analysis is done.",
      matchingRule: {
        dimensionRanges: { analysis: [65, 100], intuition: [0, 45] },
      },
      priority: 5,
    },
    {
      key: "intuitive_decider",
      name: "The Intuitive Decider",
      descriptionTemplate:
        "Your responses suggest your gut feeling tends to lead, with formal analysis playing a smaller supporting role. You appear to trust a fast, instinctive read on a situation more than a slow, methodical one.",
      matchingRule: {
        dimensionRanges: { intuition: [65, 100], analysis: [0, 45] },
      },
      priority: 5,
    },
    {
      key: "cautious_decider",
      name: "The Cautious Decider",
      descriptionTemplate:
        "Your responses suggest you need real certainty before committing, and genuine uncertainty tends to feel uncomfortable rather than exciting. You're unlikely to move on something important until you feel solidly sure.",
      matchingRule: {
        dimensionRanges: { certainty: [60, 100], risk: [0, 45] },
      },
      priority: 4,
    },
    {
      key: "fast_actor",
      name: "The Fast Actor",
      descriptionTemplate:
        "Your responses suggest you move quickly from noticing a decision to acting on it, without much appetite for prolonged deliberation. Momentum appears to matter more to you than exhaustive certainty.",
      matchingRule: {
        dimensionRanges: { speed: [65, 100], action: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "balanced_decider",
      name: "The Balanced Decider",
      descriptionTemplate:
        "Your responses suggest you draw on both analysis and intuition fairly evenly, rather than leaning hard on one. This tends to make your decisions well-rounded, even if it occasionally takes a little longer to land on one.",
      matchingRule: {
        dimensionRanges: { analysis: [40, 65], intuition: [40, 65] },
      },
      priority: 3,
    },
    {
      key: "risk_explorer",
      name: "The Risk Explorer",
      descriptionTemplate:
        "Your responses suggest genuine uncertainty doesn't hold you back — if anything, it appears to be part of what makes a decision worth making. You're comfortable acting before every variable is fully known.",
      matchingRule: {
        dimensionRanges: { risk: [65, 100], action: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "certainty_seeker",
      name: "The Certainty Seeker",
      descriptionTemplate:
        "Your responses suggest you lean hard on analysis specifically to manufacture the certainty you need before deciding — the reasoning isn't just information-gathering, it appears to be how you get yourself to feel sure.",
      matchingRule: {
        dimensionRanges: { certainty: [65, 100], analysis: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "adaptive_decider",
      name: "The Adaptive Decider",
      descriptionTemplate:
        "Your responses suggest you're genuinely comfortable deciding without full certainty, staying flexible enough to adjust course as new information arrives rather than needing it all upfront.",
      matchingRule: {
        dimensionRanges: { flexibility: [60, 100], certainty: [0, 45] },
      },
      priority: 4,
    },
  ],

  freeResultTemplate: {
    headline: "Your decision-making pattern is:",
    insightIntro:
      "Your responses suggest a specific way you actually decide when something matters — a mix of analysis, instinct, and how much certainty you need before moving.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you decide.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Decision DNA:",
    shareTextTemplate: "I discovered my INNER Decision DNA: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "decision.signature" },
    { key: "dominant_pattern", title: "Your Decision Style", promptRef: "decision.dominant_pattern" },
    { key: "analysis_and_intuition", title: "Analysis & Intuition", promptRef: "decision.analysis_and_intuition" },
    { key: "risk_and_certainty", title: "Risk & Certainty", promptRef: "decision.risk_and_certainty" },
    { key: "speed_and_action", title: "Speed & Action", promptRef: "decision.speed_and_action" },
    { key: "outside_influence", title: "Emotion & Outside Influence", promptRef: "decision.outside_influence" },
    { key: "strengths", title: "Your Strengths", promptRef: "decision.strengths" },
    { key: "blind_spots", title: "Your Potential Blind Spots", promptRef: "decision.blind_spots" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "decision.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "decision.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "decision.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "hidden-self",
      condition: { dimensionRanges: { control: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "This pattern of control and certainty often runs deeper than decision-making alone — curious what your hidden self might reveal?",
    },
    {
      assessmentSlug: "communication",
      condition: { dimensionRanges: { validation: [55, 100] } },
      weight: 0.6,
      bridgeCopy: "Wanting input before deciding often connects to how you communicate more broadly — want to see that fuller pattern?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
