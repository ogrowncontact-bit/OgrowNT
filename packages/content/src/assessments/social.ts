import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "How Do People Really See You?" — /social. Compares self-perception
 * against behavioral-signal questions (docs/ARCHITECTURE.md §3) — some
 * questions ask directly how someone sees themselves, others ask what they
 * actually do in the moment, and the report draws out the gap between the
 * two rather than claiming to literally know how others perceive the user.
 */
export const socialAssessment: AssessmentConfig = {
  slug: "social",
  name: "How Do People Really See You?",
  category: "self",
  description: "A short, adaptive conversation comparing how you see your social presence with what you actually do in social moments.",
  hook: "Is the person you think you are the same person other people experience?",
  targetAudience: "Adults curious about the gap between self-image and social behavior.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "social_confidence", weight: 1 },
    { key: "approachability", weight: 1 },
    { key: "assertiveness", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "independence", weight: 1 },
    { key: "social_awareness", weight: 1 },
    { key: "first_impression", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "confidence_low_first_impression",
      label: "feeling genuinely confident internally while believing you come across as more reserved than you are",
      dimensionA: "social_confidence",
      thresholdA: 60,
      dimensionB: "first_impression",
      thresholdB: 40,
      directionB: "lte",
    },
    {
      key: "awareness_low_assertiveness",
      label: "reading a room accurately while still holding back from speaking up in it",
      dimensionA: "social_awareness",
      thresholdA: 60,
      dimensionB: "assertiveness",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "self_perception_presence",
        type: "single_select",
        isCore: true,
        prompt: "How would you describe your own social presence, honestly?",
        options: [
          { key: "warm_and_open_self", label: "Warm and open", dimensionContributions: { approachability: 2, emotional_openness: 1 } },
          { key: "confident_and_direct_self", label: "Confident and direct", dimensionContributions: { social_confidence: 2, assertiveness: 1 } },
          { key: "quiet_and_observant_self", label: "Quiet and observant", dimensionContributions: { social_confidence: -1, social_awareness: 2 } },
          { key: "reserved_until_comfortable_self", label: "Reserved until I'm comfortable", dimensionContributions: { first_impression: -1, social_confidence: -1 } },
        ],
      },
      {
        key: "entering_a_room_behavior",
        type: "single_select",
        isCore: true,
        prompt: "When you walk into a room of strangers, what do you actually do first?",
        options: [
          { key: "scan_and_approach", label: "Scan the room and approach someone", dimensionContributions: { social_confidence: 2, approachability: 1 } },
          { key: "wait_to_be_approached", label: "Wait for someone to approach me", dimensionContributions: { social_confidence: -1, approachability: -1 } },
          { key: "find_a_familiar_face", label: "Look for a familiar face first", dimensionContributions: { independence: -1 } },
          { key: "observe_before_engaging", label: "Observe the room before engaging", dimensionContributions: { social_awareness: 2, social_confidence: -1 } },
        ],
      },
      {
        key: "social_confidence_scale",
        type: "scale",
        isCore: true,
        prompt: "How confident do you feel in a room full of people you don't know?",
        scaleMax: 5,
        scaleDimension: "social_confidence",
      },
      {
        key: "approachability_self_rating",
        type: "single_select",
        isCore: true,
        prompt: "Do you think strangers find you easy to approach?",
        options: [
          { key: "yes_very_easy", label: "Yes, very easy", dimensionContributions: { approachability: 2, first_impression: 1 } },
          { key: "somewhat_easy", label: "Somewhat easy", dimensionContributions: { approachability: 1 } },
          { key: "depends_on_mood", label: "Depends entirely on my mood that day", dimensionContributions: {} },
          { key: "probably_not_very", label: "Probably not very approachable", dimensionContributions: { approachability: -2, first_impression: -1 } },
        ],
      },
      {
        key: "speaking_up_behavior",
        type: "single_select",
        isCore: true,
        prompt: "In a group discussion, when do you actually speak up?",
        options: [
          { key: "early_and_often", label: "Early, and fairly often", dimensionContributions: { assertiveness: 2, social_confidence: 1 } },
          { key: "when_i_have_something_specific", label: "When I have something specific to add", dimensionContributions: { assertiveness: 1 } },
          { key: "only_if_directly_asked", label: "Only if I'm directly asked", dimensionContributions: { assertiveness: -2 } },
          { key: "rarely_unless_strongly_opinionated", label: "Rarely, unless I feel strongly", dimensionContributions: { assertiveness: -1, communication: -1 } },
        ],
      },
      {
        key: "assertiveness_scale",
        type: "scale",
        isCore: true,
        prompt: "How comfortable are you stating your opinion when you know others might disagree?",
        scaleMax: 5,
        scaleDimension: "assertiveness",
      },
      {
        key: "emotional_expression_behavior",
        type: "single_select",
        isCore: true,
        prompt: "In a social setting, how visible are your actual emotions to people around you?",
        options: [
          { key: "very_visible_social", label: "Very visible — people can read me easily", dimensionContributions: { emotional_openness: 2 } },
          { key: "somewhat_visible_social", label: "Somewhat visible", dimensionContributions: { emotional_openness: 1 } },
          { key: "mostly_hidden_social", label: "Mostly hidden behind a neutral presence", dimensionContributions: { emotional_openness: -2 } },
          { key: "depends_on_the_group_social", label: "Depends entirely on the group", dimensionContributions: {} },
        ],
      },
      {
        key: "communication_clarity_social",
        type: "scale",
        isCore: true,
        prompt: "How clearly do you think you communicate what you actually mean, in social settings?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "social_energy_source",
        type: "single_select",
        isCore: true,
        prompt: "After a few hours of socializing, how do you usually feel?",
        options: [
          { key: "energized_social", label: "Energized", dimensionContributions: { social_confidence: 1, approachability: 1 } },
          { key: "fine_but_ready_for_quiet", label: "Fine, but ready for some quiet", dimensionContributions: { independence: 1 } },
          { key: "genuinely_drained_social", label: "Genuinely drained", dimensionContributions: { independence: 2, social_confidence: -1 } },
          { key: "depends_entirely_on_the_people", label: "Depends entirely on the people", dimensionContributions: {} },
        ],
      },
      {
        key: "reading_the_room_behavior",
        type: "single_select",
        isCore: true,
        prompt: "In a group, how quickly do you pick up on shifts in mood or tension?",
        options: [
          { key: "almost_immediately", label: "Almost immediately", dimensionContributions: { social_awareness: 2 } },
          { key: "fairly_quickly_room", label: "Fairly quickly", dimensionContributions: { social_awareness: 1 } },
          { key: "eventually_room", label: "Eventually, once it's obvious", dimensionContributions: { social_awareness: -1 } },
          { key: "often_miss_it_room", label: "I often miss it entirely", dimensionContributions: { social_awareness: -2 } },
        ],
      },
      {
        key: "first_impression_belief",
        type: "single_select",
        isCore: true,
        prompt: "What do you believe people usually think of you within the first few minutes of meeting you?",
        options: [
          { key: "warm_and_friendly_belief", label: "Warm and friendly", dimensionContributions: { first_impression: 2, approachability: 1 } },
          { key: "confident_belief", label: "Confident", dimensionContributions: { first_impression: 2, social_confidence: 1 } },
          { key: "hard_to_read_belief", label: "Hard to read", dimensionContributions: { first_impression: -1 } },
          { key: "quiet_or_distant_belief", label: "Quiet, maybe a little distant", dimensionContributions: { first_impression: -2 } },
        ],
      },
      {
        key: "feedback_received_behavior",
        type: "single_select",
        isCore: true,
        prompt: "When people describe you after just meeting you, what do they say most often?",
        options: [
          { key: "youre_so_easy_to_talk_to", label: "\"You're so easy to talk to\"", dimensionContributions: { approachability: 2, first_impression: 1 } },
          { key: "youre_really_confident", label: "\"You're really confident\"", dimensionContributions: { social_confidence: 2, first_impression: 1 } },
          { key: "youre_hard_to_read", label: "\"You're hard to read\"", dimensionContributions: { emotional_openness: -1, first_impression: -1 } },
          { key: "not_sure_what_they_say", label: "Honestly, I don't know what they'd say", dimensionContributions: {} },
        ],
      },
      {
        key: "disagreement_in_group_behavior",
        type: "single_select",
        isCore: true,
        prompt: "When you disagree with the group consensus, what do you actually do?",
        options: [
          { key: "say_it_directly_group", label: "Say it directly", dimensionContributions: { assertiveness: 2, communication: 1 } },
          { key: "mention_it_carefully_group", label: "Mention it, but carefully", dimensionContributions: { assertiveness: 1 } },
          { key: "keep_it_to_myself_group", label: "Keep it to myself", dimensionContributions: { assertiveness: -2, communication: -1 } },
          { key: "bring_it_up_privately_later", label: "Bring it up with someone privately, later", dimensionContributions: { social_awareness: 1, assertiveness: -1 } },
        ],
      },
      {
        key: "self_perception_open_text",
        type: "open_text",
        isCore: true,
        prompt: "How do you think you come across to people who don't know you well yet?",
        dynamicFollowupCandidates: ["perception_gap_awareness", "perception_source"],
      },
      {
        key: "social_moment_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a recent social situation where you felt most like yourself. What made that possible?",
        dynamicFollowupCandidates: ["most_like_myself_cause", "most_like_myself_frequency"],
      },
    ],
    adaptivePool: [
      {
        key: "perception_gap_awareness",
        type: "single_select",
        isCore: false,
        prompt: "Has anyone ever told you they see you differently than you see yourself?",
        options: [
          { key: "yes_often_gap", label: "Yes, fairly often", dimensionContributions: { social_awareness: 1, first_impression: -1 } },
          { key: "yes_once_or_twice_gap", label: "Once or twice", dimensionContributions: {} },
          { key: "no_never_gap", label: "No, not that I remember", dimensionContributions: { first_impression: 1 } },
          { key: "not_sure_gap", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "perception_source",
        type: "single_select",
        isCore: false,
        prompt: "Where do you think your sense of how you come across mostly comes from?",
        options: [
          { key: "direct_feedback_source", label: "Direct feedback from people", dimensionContributions: { communication: 1 } },
          { key: "how_i_feel_inside", label: "Mostly how I feel inside, projected outward", dimensionContributions: { social_awareness: -1 } },
          { key: "past_social_experiences_source", label: "Past social experiences", dimensionContributions: {} },
          { key: "never_really_thought_source", label: "I've never really thought about it", dimensionContributions: {} },
        ],
      },
      {
        key: "most_like_myself_cause",
        type: "single_select",
        isCore: false,
        prompt: "What specifically made you feel most like yourself in that moment?",
        options: [
          { key: "people_who_know_me_well", label: "Being with people who know me well", dimensionContributions: { approachability: 1, emotional_openness: 1 } },
          { key: "no_pressure_to_perform", label: "No pressure to perform a certain way", dimensionContributions: { social_confidence: 1 } },
          { key: "topic_i_care_about", label: "Talking about something I actually care about", dimensionContributions: { emotional_openness: 1, communication: 1 } },
          { key: "not_sure_most_like_myself", label: "I'm not entirely sure", dimensionContributions: {} },
        ],
      },
      {
        key: "most_like_myself_frequency",
        type: "single_select",
        isCore: false,
        prompt: "Does that feeling of being fully yourself happen often, or was it rare?",
        options: [
          { key: "fairly_often_myself", label: "Fairly often", dimensionContributions: { social_confidence: 1 } },
          { key: "with_specific_people_myself", label: "Mostly with specific people", dimensionContributions: {} },
          { key: "quite_rare_myself", label: "Quite rare, honestly", dimensionContributions: { independence: 1 } },
          { key: "that_was_unusual_myself", label: "That was fairly unusual for me", dimensionContributions: {} },
        ],
      },
      {
        key: "scan_approach_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What usually determines who you approach first in a room?",
        options: [
          { key: "who_looks_approachable", label: "Who looks approachable themselves", dimensionContributions: { social_awareness: 1 } },
          { key: "who_im_genuinely_curious_about", label: "Who I'm genuinely curious about", dimensionContributions: { assertiveness: 1 } },
          { key: "whoever_is_closest", label: "Honestly, whoever's closest", dimensionContributions: {} },
          { key: "not_sure_who_i_approach", label: "I'm not sure I have a pattern", dimensionContributions: {} },
        ],
      },
      {
        key: "observe_before_engaging_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What are you usually looking for while you observe before engaging?",
        options: [
          { key: "who_seems_safe_to_approach", label: "Who seems safe to approach", dimensionContributions: { social_confidence: -1 } },
          { key: "the_overall_dynamic_of_the_room", label: "The overall dynamic of the room", dimensionContributions: { social_awareness: 2 } },
          { key: "an_opening_to_join_in", label: "A natural opening to join in", dimensionContributions: { social_awareness: 1, assertiveness: 1 } },
          { key: "not_sure_looking_for", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "drained_after_social_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What specifically drains you most in social settings?",
        options: [
          { key: "performing_a_version_of_myself", label: "Feeling like I'm performing a version of myself", dimensionContributions: { emotional_openness: -1, first_impression: -1 } },
          { key: "small_talk_itself", label: "Small talk itself, more than the people", dimensionContributions: { communication: -1 } },
          { key: "just_the_volume_of_people", label: "Just the sheer volume of people", dimensionContributions: { independence: 1 } },
          { key: "not_sure_whats_draining", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "hard_to_read_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "If people find you hard to read, what do you think that's actually about?",
        options: [
          { key: "i_keep_emotions_contained", label: "I tend to keep my emotions contained", dimensionContributions: { emotional_openness: -1 } },
          { key: "i_only_open_up_once_comfortable", label: "I only open up once I feel comfortable", dimensionContributions: { first_impression: -1 } },
          { key: "i_dont_think_thats_true", label: "I don't actually think that's true", dimensionContributions: { first_impression: 1 } },
          { key: "not_sure_hard_to_read", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "independence_social_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you need alone time to recover after a socially demanding day?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
      {
        key: "first_impression_confidence_scale",
        type: "scale",
        isCore: false,
        prompt: "How confident are you that your first impression on people is generally accurate to who you are?",
        scaleMax: 5,
        scaleDimension: "first_impression",
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "self_perception_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "social_moment_dynamic_followup",
      trigger: { questionKey: "social_moment_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "scan_approach_signal",
      trigger: { questionKey: "entering_a_room_behavior", op: "answered_option", optionKey: "scan_and_approach" },
      action: { type: "ask_followup", followupQuestionKey: "scan_approach_deep_dive" },
      priority: 6,
    },
    {
      key: "observe_before_engaging_signal",
      trigger: { questionKey: "entering_a_room_behavior", op: "answered_option", optionKey: "observe_before_engaging" },
      action: { type: "ask_followup", followupQuestionKey: "observe_before_engaging_deep_dive" },
      priority: 6,
    },
    {
      key: "drained_signal",
      trigger: { questionKey: "social_energy_source", op: "answered_option", optionKey: "genuinely_drained_social" },
      action: { type: "ask_followup", followupQuestionKey: "drained_after_social_deep_dive" },
      priority: 5,
    },
    {
      key: "hard_to_read_signal",
      trigger: { questionKey: "feedback_received_behavior", op: "answered_option", optionKey: "youre_hard_to_read" },
      action: { type: "ask_followup", followupQuestionKey: "hard_to_read_deep_dive" },
      priority: 5,
    },
  ],

  profiles: [
    {
      key: "warm_presence",
      name: "The Warm Presence",
      descriptionTemplate:
        "Your responses suggest people find you genuinely easy to approach, and your emotions tend to show fairly openly. Warmth appears to be one of the more consistent signals you send, whether or not you're consciously trying to.",
      matchingRule: {
        dimensionRanges: { approachability: [65, 100], emotional_openness: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "quiet_observer",
      name: "The Quiet Observer",
      descriptionTemplate:
        "Your responses suggest you hang back and read a room before engaging with it, taking in far more than you say. This isn't the same as low confidence — it looks more like a deliberate preference for understanding before participating.",
      matchingRule: {
        dimensionRanges: { social_confidence: [0, 45], social_awareness: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "confident_presence",
      name: "The Confident Presence",
      descriptionTemplate:
        "Your responses suggest you enter social situations without much hesitation, comfortable stating your position even when others might disagree. This combination tends to make you a fairly visible presence in a room.",
      matchingRule: {
        dimensionRanges: { social_confidence: [65, 100], assertiveness: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "selective_socializer",
      name: "The Selective Socializer",
      descriptionTemplate:
        "Your responses suggest you're genuinely attentive to social dynamics, but you don't extend that openness to everyone equally. Approachability, for you, appears to be something extended selectively rather than by default.",
      matchingRule: {
        dimensionRanges: { approachability: [0, 50], social_awareness: [55, 100] },
        optionalConditions: { independence: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "direct_presence",
      name: "The Direct Presence",
      descriptionTemplate:
        "Your responses suggest you say what you mean fairly plainly and hold your position under social pressure. Clarity, more than warmth or subtlety, appears to be the signal you send most consistently.",
      matchingRule: {
        dimensionRanges: { assertiveness: [65, 100], communication: [60, 100] },
      },
      priority: 5,
    },
    {
      key: "adaptive_socializer",
      name: "The Adaptive Socializer",
      descriptionTemplate:
        "Your responses suggest you're highly attuned to shifts in a room and adjust how you engage accordingly, without necessarily pushing your own position hard. Reading the dynamic appears to matter more to you than steering it.",
      matchingRule: {
        dimensionRanges: { social_awareness: [65, 100], communication: [55, 100] },
        excludeConditions: { assertiveness: [75, 100] },
      },
      priority: 3,
    },
    {
      key: "reserved_presence",
      name: "The Reserved Presence",
      descriptionTemplate:
        "Your responses suggest you believe you come across as more distant or harder to read than you may actually intend, and social settings don't appear to be where you feel most naturally confident. Independence seems to matter more to you than social visibility.",
      matchingRule: {
        dimensionRanges: { social_confidence: [0, 45], first_impression: [0, 45] },
        optionalConditions: { independence: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "magnetic_presence",
      name: "The Magnetic Presence",
      descriptionTemplate:
        "Your responses suggest a rare combination — genuine approachability paired with real confidence in how you come across. People likely form a strong first impression of you quickly, and your own sense of that impression appears accurate.",
      matchingRule: {
        dimensionRanges: { approachability: [65, 100], first_impression: [65, 100] },
        optionalConditions: { social_confidence: [60, 100] },
      },
      priority: 5,
    },
  ],

  freeResultTemplate: {
    headline: "Your social presence pattern is:",
    insightIntro:
      "Your responses suggest a specific way you show up socially — and reveal a first gap worth noticing between how you see yourself and what you actually do in the room.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you come across.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Social Presence:",
    shareTextTemplate: "I discovered my INNER Social Presence: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "social.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "social.dominant_pattern" },
    { key: "self_perception", title: "How You See Yourself", promptRef: "social.self_perception" },
    { key: "behavioral_signals", title: "What You Actually Do", promptRef: "social.behavioral_signals" },
    { key: "the_gap", title: "The Gap Between the Two", promptRef: "social.the_gap" },
    { key: "first_impression_analysis", title: "Your First Impression", promptRef: "social.first_impression_analysis" },
    { key: "strengths", title: "Your Strengths", promptRef: "social.strengths" },
    { key: "possible_blind_spots", title: "Possible Blind Spots", promptRef: "social.possible_blind_spots" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "social.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "social.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "social.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "communication",
      condition: { dimensionRanges: { assertiveness: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers touched on how directly you speak up — want to see the fuller pattern behind how you communicate?",
    },
    {
      assessmentSlug: "hidden-self",
      condition: { dimensionRanges: { first_impression: [0, 50] } },
      weight: 0.7,
      bridgeCopy: "There's often more underneath a gap like this than meets the eye — curious what your hidden self might reveal?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
