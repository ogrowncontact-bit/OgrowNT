import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Communication DNA" — /communication. Docs/ARCHITECTURE.md §3. */
export const communicationAssessment: AssessmentConfig = {
  slug: "communication",
  name: "Your Communication DNA",
  category: "self",
  description: "A short, adaptive conversation about how you actually communicate — not how you mean to.",
  hook: "You may know what you meant. But what do people actually receive?",
  targetAudience: "Adults curious about the gap between what they intend to say and what actually lands.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "directness", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "listening", weight: 1 },
    { key: "assertiveness", weight: 1 },
    { key: "conflict", weight: 1 },
    { key: "diplomacy", weight: 1 },
    { key: "openness", weight: 1 },
    { key: "interpretation", weight: 1 },
    { key: "boundaries", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "directness_high_diplomacy",
      label: "valuing plain, direct language while also working hard to soften how it lands",
      dimensionA: "directness",
      thresholdA: 60,
      dimensionB: "diplomacy",
      thresholdB: 60,
    },
    {
      key: "listening_low_assertiveness",
      label: "listening closely to everyone else while rarely stating your own position as clearly",
      dimensionA: "listening",
      thresholdA: 60,
      dimensionB: "assertiveness",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "bothered_first_move",
        type: "single_select",
        isCore: true,
        prompt: "Someone says something that bothers you. What are you most likely to do first?",
        options: [
          { key: "say_something_right_away", label: "Say something right away", dimensionContributions: { directness: 2, assertiveness: 1 } },
          { key: "let_it_go_by", label: "Let it go, at least for now", dimensionContributions: { conflict: -2, diplomacy: 1 } },
          { key: "think_about_how_to_say_it", label: "Think about how to say it well first", dimensionContributions: { diplomacy: 2 } },
          { key: "assume_i_misread_it", label: "Assume I might have misread it", dimensionContributions: { interpretation: -1, directness: -1 } },
        ],
      },
      {
        key: "directness_scale",
        type: "scale",
        isCore: true,
        prompt: "How directly do you typically say what you actually mean?",
        scaleMax: 5,
        scaleDimension: "directness",
      },
      {
        key: "emotional_expression_communication",
        type: "single_select",
        isCore: true,
        prompt: "When you're upset, how visible is that in how you communicate?",
        options: [
          { key: "very_visible_comm", label: "Very visible — it comes through clearly", dimensionContributions: { emotional_openness: 2, directness: 1 } },
          { key: "somewhat_visible_comm", label: "Somewhat visible", dimensionContributions: { emotional_openness: 1 } },
          { key: "carefully_controlled_comm", label: "Carefully controlled", dimensionContributions: { emotional_openness: -2, diplomacy: 1 } },
          { key: "hidden_entirely_comm", label: "Hidden entirely, if I can help it", dimensionContributions: { emotional_openness: -2, boundaries: 1 } },
        ],
      },
      {
        key: "listening_scale",
        type: "scale",
        isCore: true,
        prompt: "When someone's talking to you, how much of your attention is actually on what they're saying, versus what you'll say next?",
        scaleMax: 5,
        scaleDimension: "listening",
      },
      {
        key: "group_opinion_moment",
        type: "single_select",
        isCore: true,
        prompt: "In a group conversation, when do you state your actual opinion?",
        options: [
          { key: "immediately_opinion", label: "Immediately, without much hesitation", dimensionContributions: { assertiveness: 2, directness: 1 } },
          { key: "once_ive_gauged_the_room", label: "Once I've gauged the room", dimensionContributions: { interpretation: 1 } },
          { key: "only_if_pushed_opinion", label: "Only if someone pushes me on it", dimensionContributions: { assertiveness: -2 } },
          { key: "rarely_unless_strongly_felt", label: "Rarely, unless I feel strongly", dimensionContributions: { assertiveness: -1, openness: -1 } },
        ],
      },
      {
        key: "conflict_engagement",
        type: "single_select",
        isCore: true,
        prompt: "When a conversation starts turning into a real disagreement, you...",
        options: [
          { key: "stay_and_work_through_it", label: "Stay and work through it", dimensionContributions: { conflict: 2, assertiveness: 1 } },
          { key: "try_to_de_escalate", label: "Try to de-escalate it quickly", dimensionContributions: { conflict: -1, diplomacy: 2 } },
          { key: "shut_down_a_little", label: "Shut down a little", dimensionContributions: { conflict: -2, emotional_openness: -1 } },
          { key: "get_more_direct", label: "Get more direct, not less", dimensionContributions: { conflict: 1, directness: 2 } },
        ],
      },
      {
        key: "diplomacy_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you soften a difficult message before delivering it?",
        scaleMax: 5,
        scaleDimension: "diplomacy",
      },
      {
        key: "receiving_feedback",
        type: "single_select",
        isCore: true,
        prompt: "When someone gives you feedback you didn't ask for, what's your instinct?",
        options: [
          { key: "genuinely_consider_it", label: "Genuinely consider it, even if it stings", dimensionContributions: { openness: 2 } },
          { key: "listen_but_defend_myself", label: "Listen, but explain my side", dimensionContributions: { openness: 1, directness: 1 } },
          { key: "feel_defensive_first", label: "Feel defensive before anything else", dimensionContributions: { openness: -2 } },
          { key: "assume_they_dont_understand", label: "Assume they don't fully understand the situation", dimensionContributions: { openness: -2, interpretation: -1 } },
        ],
      },
      {
        key: "interpretation_scale",
        type: "scale",
        isCore: true,
        prompt: "How often do you read into what someone means beyond their literal words?",
        scaleMax: 5,
        scaleDimension: "interpretation",
      },
      {
        key: "boundaries_communication_moment",
        type: "single_select",
        isCore: true,
        prompt: "When someone asks something of you that you'd rather not do, what happens?",
        options: [
          { key: "say_no_clearly", label: "I say no clearly", dimensionContributions: { boundaries: 2, directness: 1 } },
          { key: "say_yes_then_regret_it", label: "I usually say yes, then regret it", dimensionContributions: { boundaries: -2 } },
          { key: "give_a_soft_no", label: "I give a softened, indirect no", dimensionContributions: { boundaries: 1, diplomacy: 1 } },
          { key: "delay_answering", label: "I delay answering as long as possible", dimensionContributions: { boundaries: -1, directness: -1 } },
        ],
      },
      {
        key: "misunderstanding_response",
        type: "single_select",
        isCore: true,
        prompt: "When you realize you've been misunderstood, what do you usually do?",
        options: [
          { key: "clarify_immediately", label: "Clarify immediately", dimensionContributions: { directness: 2, listening: 1 } },
          { key: "let_it_go_misunderstanding", label: "Let it go if it's not a big deal", dimensionContributions: { diplomacy: 1 } },
          { key: "assume_it_will_sort_itself_out", label: "Assume it'll sort itself out", dimensionContributions: { directness: -1 } },
          { key: "get_frustrated_misunderstanding", label: "Get a little frustrated that I wasn't clearer", dimensionContributions: { emotional_openness: 1, directness: -1 } },
        ],
      },
      {
        key: "listening_while_disagreeing",
        type: "single_select",
        isCore: true,
        prompt: "When you strongly disagree with someone mid-conversation, are you still really listening?",
        options: [
          { key: "yes_fully_listening", label: "Yes, fully — I want to understand their point", dimensionContributions: { listening: 2, openness: 1 } },
          { key: "partly_listening", label: "Partly — I'm also building my response", dimensionContributions: { listening: -1 } },
          { key: "mostly_waiting_to_respond", label: "Mostly waiting for my turn to respond", dimensionContributions: { listening: -2, assertiveness: 1 } },
          { key: "depends_on_the_topic", label: "Depends entirely on the topic", dimensionContributions: {} },
        ],
      },
      {
        key: "reading_between_lines_scenario",
        type: "single_select",
        isCore: true,
        prompt: "A friend says \"it's fine\" in a tone that doesn't quite match the words. What do you do?",
        options: [
          { key: "ask_whats_actually_going_on", label: "Ask what's actually going on", dimensionContributions: { interpretation: 2, directness: 1 } },
          { key: "take_the_words_at_face_value", label: "Take the words at face value", dimensionContributions: { interpretation: -2 } },
          { key: "notice_but_dont_push", label: "Notice it, but don't push", dimensionContributions: { interpretation: 1, boundaries: 1 } },
          { key: "assume_i_know_whats_wrong", label: "Assume I already know what's wrong", dimensionContributions: { interpretation: 1, openness: -1 } },
        ],
      },
      {
        key: "hard_conversation_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a hard conversation you've had recently. How did you approach it?",
        dynamicFollowupCandidates: ["hard_conversation_outcome", "hard_conversation_pattern"],
      },
      {
        key: "misread_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a time something you said was taken very differently than you meant it.",
        dynamicFollowupCandidates: ["misread_cause", "misread_frequency"],
      },
    ],
    adaptivePool: [
      {
        key: "hard_conversation_outcome",
        type: "single_select",
        isCore: false,
        prompt: "How did that conversation go, overall?",
        options: [
          { key: "went_better_than_expected", label: "Better than I expected", dimensionContributions: { directness: 1, openness: 1 } },
          { key: "went_about_as_expected", label: "About as I expected", dimensionContributions: {} },
          { key: "went_worse_than_expected", label: "Worse than I expected", dimensionContributions: { diplomacy: 1 } },
          { key: "still_unresolved", label: "Honestly, it's still unresolved", dimensionContributions: { conflict: -1 } },
        ],
      },
      {
        key: "hard_conversation_pattern",
        type: "single_select",
        isCore: false,
        prompt: "Is that roughly how hard conversations usually go for you?",
        options: [
          { key: "yes_pretty_typical", label: "Yes, pretty typical", dimensionContributions: {} },
          { key: "depends_a_lot_on_topic", label: "Depends a lot on the topic", dimensionContributions: {} },
          { key: "that_one_was_unusual", label: "That one was unusual for me", dimensionContributions: {} },
          { key: "i_avoid_them_when_i_can", label: "Honestly, I avoid them when I can", dimensionContributions: { conflict: -2 } },
        ],
      },
      {
        key: "misread_cause",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, what do you think caused the misunderstanding?",
        options: [
          { key: "my_tone_not_words", label: "My tone, more than my actual words", dimensionContributions: { directness: -1 } },
          { key: "i_wasnt_clear_enough", label: "I genuinely wasn't clear enough", dimensionContributions: { directness: -1, openness: 1 } },
          { key: "they_read_into_it_too_much", label: "They read into it more than I meant", dimensionContributions: { interpretation: -1 } },
          { key: "not_sure_cause_misread", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "misread_frequency",
        type: "single_select",
        isCore: false,
        prompt: "Does this happen often, or was that a one-off?",
        options: [
          { key: "fairly_often_misread", label: "Fairly often, honestly", dimensionContributions: { directness: -1 } },
          { key: "occasionally_misread", label: "Occasionally", dimensionContributions: {} },
          { key: "that_was_rare_misread", label: "That was rare for me", dimensionContributions: { directness: 1 } },
          { key: "never_really_tracked_misread", label: "I've never really tracked it", dimensionContributions: {} },
        ],
      },
      {
        key: "shutdown_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "When you shut down a little during conflict, what's usually happening for you?",
        options: [
          { key: "overwhelmed_by_the_intensity", label: "I'm overwhelmed by the intensity", dimensionContributions: { emotional_openness: -1, conflict: -1 } },
          { key: "dont_trust_what_id_say", label: "I don't trust what I'd say in the moment", dimensionContributions: { diplomacy: 1 } },
          { key: "genuinely_dont_see_the_point", label: "I genuinely don't see the point anymore", dimensionContributions: { conflict: -2 } },
          { key: "not_sure_shutdown", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "defensive_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What usually triggers that defensiveness for you?",
        options: [
          { key: "feeling_attacked_not_helped", label: "Feeling attacked rather than helped", dimensionContributions: { openness: -1 } },
          { key: "the_timing_feels_off", label: "The timing feels off", dimensionContributions: {} },
          { key: "i_already_knew_and_it_stings", label: "I already knew, and hearing it stings more", dimensionContributions: { emotional_openness: 1, openness: -1 } },
          { key: "not_sure_defensive", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "say_yes_regret_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What usually stops you from saying no in the moment?",
        options: [
          { key: "dont_want_to_disappoint", label: "Not wanting to disappoint them", dimensionContributions: { boundaries: -1 } },
          { key: "havent_thought_of_a_good_reason", label: "Not having a ready reason", dimensionContributions: { directness: -1 } },
          { key: "worried_about_the_reaction", label: "Worrying about their reaction", dimensionContributions: { conflict: -1 } },
          { key: "not_sure_say_yes", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "clarify_immediately_scale",
        type: "scale",
        isCore: false,
        prompt: "How often do you circle back to clarify something you said, even hours or days later?",
        scaleMax: 5,
        scaleDimension: "directness",
      },
      {
        key: "openness_to_being_wrong_scale",
        type: "scale",
        isCore: false,
        prompt: "How easy is it for you to say \"I was wrong about that\" out loud?",
        scaleMax: 5,
        scaleDimension: "openness",
      },
      {
        key: "boundaries_after_saying_no_scale",
        type: "scale",
        isCore: false,
        prompt: "After you say no to something, how much guilt do you tend to carry about it?",
        scaleMax: 5,
        scaleDimension: "boundaries",
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "hard_conversation_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "misread_dynamic_followup",
      trigger: { questionKey: "misread_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "shutdown_signal",
      trigger: { questionKey: "conflict_engagement", op: "answered_option", optionKey: "shut_down_a_little" },
      action: { type: "ask_followup", followupQuestionKey: "shutdown_deep_dive" },
      priority: 6,
    },
    {
      key: "defensive_signal",
      trigger: { questionKey: "receiving_feedback", op: "answered_option", optionKey: "feel_defensive_first" },
      action: { type: "ask_followup", followupQuestionKey: "defensive_deep_dive" },
      priority: 6,
    },
    {
      key: "boundary_regret_signal",
      trigger: { questionKey: "boundaries_communication_moment", op: "answered_option", optionKey: "say_yes_then_regret_it" },
      action: { type: "ask_followup", followupQuestionKey: "say_yes_regret_deep_dive" },
      priority: 5,
    },
    {
      key: "low_directness_signal",
      trigger: { questionKey: "directness_scale", dimensionKey: "directness", op: "lte", value: 30 },
      action: { type: "ask_followup", followupQuestionKey: "clarify_immediately_scale" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "clear_direct",
      name: "The Clear Direct",
      descriptionTemplate:
        "Your responses suggest you say what you mean plainly, and you're actually listening while you do it — not just waiting for your turn. That combination tends to make you unusually easy to understand, even when what you're saying isn't easy to hear.",
      matchingRule: {
        dimensionRanges: { directness: [65, 100], listening: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "diplomatic_communicator",
      name: "The Diplomatic Communicator",
      descriptionTemplate:
        "Your responses suggest you work hard to soften a difficult message before it leaves your mouth, often more focused on how something lands than on saying it as plainly as possible. This tends to make hard conversations gentler, sometimes at the cost of clarity.",
      matchingRule: {
        dimensionRanges: { diplomacy: [65, 100], directness: [0, 50] },
      },
      priority: 4,
    },
    {
      key: "emotional_expresser",
      name: "The Emotional Expresser",
      descriptionTemplate:
        "Your responses suggest what you feel comes through clearly in how you communicate, and you tend to say it plainly rather than hide it. People likely have a fairly accurate read on your emotional state at any given moment.",
      matchingRule: {
        dimensionRanges: { emotional_openness: [65, 100], directness: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "controlled_communicator",
      name: "The Controlled Communicator",
      descriptionTemplate:
        "Your responses suggest you keep your emotional state largely out of view and choose your words carefully before speaking. This gives you real command over how a conversation unfolds, though it may leave others guessing at how you actually feel.",
      matchingRule: {
        dimensionRanges: { emotional_openness: [0, 45], diplomacy: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "listener",
      name: "The Listener",
      descriptionTemplate:
        "Your responses suggest you put real attention into understanding what others are saying, often more than into stating your own position. This makes you the kind of person others feel genuinely heard by — though your own view may not always make it into the room.",
      matchingRule: {
        dimensionRanges: { listening: [65, 100], assertiveness: [0, 50] },
      },
      priority: 5,
    },
    {
      key: "assertive_communicator",
      name: "The Assertive Communicator",
      descriptionTemplate:
        "Your responses suggest you hold your ground once a conversation gets tense, rather than backing off. Assertiveness and a willingness to stay in disagreement appear to go hand in hand for you.",
      matchingRule: {
        dimensionRanges: { assertiveness: [65, 100], conflict: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "peacekeeper",
      name: "The Peacekeeper",
      descriptionTemplate:
        "Your responses suggest you actively work to de-escalate tension and prefer smoothing things over to prolonged disagreement. This can be a genuine strength for group harmony, though it may occasionally mean your own friction goes unspoken.",
      matchingRule: {
        dimensionRanges: { diplomacy: [60, 100], conflict: [0, 40] },
      },
      priority: 4,
    },
    {
      key: "context_reader",
      name: "The Context Reader",
      descriptionTemplate:
        "Your responses suggest you pay close attention to what's underneath the literal words — tone, timing, what's left unsaid. This tends to make you attuned to things others miss, though it can occasionally mean reading into something that wasn't actually there.",
      matchingRule: {
        dimensionRanges: { interpretation: [65, 100], listening: [55, 100] },
        excludeConditions: { directness: [70, 100] },
      },
      priority: 3,
    },
  ],

  freeResultTemplate: {
    headline: "Your communication pattern is:",
    insightIntro:
      "Your responses suggest a specific way you deliver and receive what matters — one that shapes what actually lands, versus what you meant.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you communicate.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Communication DNA:",
    shareTextTemplate: "I discovered my INNER Communication DNA: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "communication.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "communication.dominant_pattern" },
    { key: "how_you_speak", title: "How You Speak", promptRef: "communication.how_you_speak" },
    { key: "how_you_listen", title: "How You Listen", promptRef: "communication.how_you_listen" },
    { key: "conflict_and_criticism", title: "Conflict & Criticism", promptRef: "communication.conflict_and_criticism" },
    { key: "emotional_expression_in_words", title: "Emotional Expression in Your Words", promptRef: "communication.emotional_expression_in_words" },
    { key: "boundaries_in_conversation", title: "Boundaries in Conversation", promptRef: "communication.boundaries_in_conversation" },
    { key: "strengths", title: "Your Strengths", promptRef: "communication.strengths" },
    { key: "friction_points", title: "Where Misunderstandings Happen", promptRef: "communication.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "communication.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "communication.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "communication.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "relationship",
      condition: { dimensionRanges: { conflict: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers touched on how you handle disagreement — want to see how that shapes the whole dynamic of a relationship over time?",
    },
    {
      assessmentSlug: "social",
      condition: { dimensionRanges: { assertiveness: [55, 100] } },
      weight: 0.7,
      bridgeCopy: "Curious whether how you communicate matches how people actually experience your social presence?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
