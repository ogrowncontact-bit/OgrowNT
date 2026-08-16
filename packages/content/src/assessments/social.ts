import type { AssessmentConfig } from "@inner/assessment-engine";

/** "How Do People Really See You?" — /social. See docs/ARCHITECTURE.md §3. */
export const socialAssessment: AssessmentConfig = {
  slug: "social",
  name: "How Do People Really See You?",
  category: "social",
  description: "A short, adaptive conversation about the gap between how you feel and how you come across.",
  hook: "How you feel in a room and how the room sees you are two different things.",
  targetAudience: "Adults curious about the gap between self-perception and how others actually read them.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "social_confidence", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "connection", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "walking_into_room",
        type: "single_select",
        isCore: true,
        prompt: "Walking into a room full of strangers, you feel...",
        options: [
          { key: "energized", label: "Energized", dimensionContributions: { social_confidence: 2, curiosity: 1 } },
          { key: "fine_find_one", label: "Fine once I find one person to talk to", dimensionContributions: { social_confidence: 1 } },
          { key: "need_moment", label: "Like I need a moment to adjust", dimensionContributions: { social_confidence: -1 } },
          { key: "want_leave", label: "Like I want to leave", dimensionContributions: { social_confidence: -2 } },
        ],
      },
      {
        key: "how_others_describe_you",
        type: "single_select",
        isCore: true,
        prompt: "If your friends described you in one word, you think they'd say...",
        options: [
          { key: "confident", label: "Confident", dimensionContributions: { social_confidence: 2 } },
          { key: "funny", label: "Funny", dimensionContributions: { communication: 1, social_confidence: 1 } },
          { key: "thoughtful", label: "Thoughtful", dimensionContributions: { connection: 1 } },
          { key: "hard_to_read", label: "Hard to read", dimensionContributions: { communication: -2 } },
        ],
      },
      {
        key: "opinion_sharing_scale",
        type: "scale",
        isCore: true,
        prompt: "How readily do you share an unpopular opinion in a group?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "group_role",
        type: "single_select",
        isCore: true,
        prompt: "In a group setting, you naturally end up...",
        options: [
          { key: "leading", label: "Leading the conversation", dimensionContributions: { social_confidence: 2, communication: 1 } },
          { key: "connecting_others", label: "Connecting quieter people to the group", dimensionContributions: { connection: 2 } },
          { key: "listening_more", label: "Listening more than talking", dimensionContributions: { social_confidence: -1 } },
          { key: "watching_edges", label: "Watching from the edges", dimensionContributions: { social_confidence: -2 } },
        ],
      },
      {
        key: "feedback_reaction",
        type: "single_select",
        isCore: true,
        prompt: "When someone gives you unexpected feedback about how you come across, you...",
        options: [
          { key: "take_seriously", label: "Take it seriously and reflect", dimensionContributions: { flexibility: 2 } },
          { key: "defensive_first", label: "Feel a bit defensive at first", dimensionContributions: { validation: -1 } },
          { key: "assume_dont_know_me", label: "Assume they don't really know me", dimensionContributions: { validation: 1, flexibility: -1 } },
          { key: "seek_more_feedback", label: "Actively seek more feedback like it", dimensionContributions: { curiosity: 2, flexibility: 1 } },
        ],
      },
      {
        key: "social_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a time you found out someone saw you differently than you saw yourself. What was the gap?",
        dynamicFollowupCandidates: ["how_did_it_feel", "which_version_is_true"],
      },
      {
        key: "need_for_approval",
        type: "single_select",
        isCore: true,
        prompt: "How much does it matter to you whether a room likes you?",
        options: [
          { key: "not_much", label: "Not much — I'd rather be myself", dimensionContributions: { validation: -2, social_confidence: 1 } },
          { key: "little_notice", label: "A little, I notice it", dimensionContributions: {} },
          { key: "quite_a_bit", label: "Quite a bit, honestly", dimensionContributions: { validation: 2 } },
          { key: "depends_who", label: "It depends who's in the room", dimensionContributions: { flexibility: 1 } },
        ],
      },
      {
        key: "first_impression_accuracy",
        type: "single_select",
        isCore: true,
        prompt: "Do you think people's first impression of you is usually accurate?",
        options: [
          { key: "yes_pretty_much", label: "Yes, pretty much", dimensionContributions: { communication: 2 } },
          { key: "somewhat_misses", label: "Somewhat, but it misses things", dimensionContributions: {} },
          { key: "no_different", label: "No, I come across differently than I feel", dimensionContributions: { communication: -2 } },
          { key: "dont_know", label: "I genuinely don't know", dimensionContributions: { curiosity: 1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "how_did_it_feel",
        type: "single_select",
        isCore: false,
        prompt: "How did it feel to learn that?",
        options: [
          { key: "validating", label: "Validating", dimensionContributions: { validation: 1 } },
          { key: "unsettling", label: "Unsettling", dimensionContributions: { validation: -1 } },
          { key: "clarifying", label: "Clarifying, in a useful way", dimensionContributions: { flexibility: 1 } },
          { key: "brushed_off", label: "I brushed it off", dimensionContributions: {} },
        ],
      },
      {
        key: "which_version_is_true",
        type: "single_select",
        isCore: false,
        prompt: "Which version do you think is closer to true — how you see yourself, or how they saw you?",
        options: [
          { key: "how_i_see_myself", label: "How I see myself", dimensionContributions: { validation: -1 } },
          { key: "how_they_saw_me", label: "How they saw me", dimensionContributions: { flexibility: 1 } },
          { key: "somewhere_between", label: "Probably somewhere in between", dimensionContributions: {} },
          { key: "not_sure_version", label: "Genuinely not sure", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "watching_edges_signal",
      trigger: { questionKey: "group_role", op: "answered_option", optionKey: "watching_edges" },
      action: { type: "ask_followup", followupQuestionKey: "which_version_is_true" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "social_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_natural_connector",
      name: "The Natural Connector",
      descriptionTemplate:
        "Your responses suggest you move through social settings with genuine ease, and tend to bring people together rather than just holding your own space. This appears to come from real confidence rather than performance.",
      matchingRule: { dimensionRanges: { social_confidence: [55, 100], connection: [55, 100] } },
    },
    {
      key: "the_watchful_observer",
      name: "The Watchful Observer",
      descriptionTemplate:
        "Your responses suggest you tend to take in a room before engaging with it, staying curious about the dynamics even when you're not at the center of them. This isn't necessarily discomfort — it may simply be how you gather information before deciding to participate.",
      matchingRule: { dimensionRanges: { social_confidence: [0, 45], curiosity: [45, 100] } },
    },
    {
      key: "the_self_aware_adapter",
      name: "The Self-Aware Adapter",
      descriptionTemplate:
        "Your responses suggest you take feedback about how you come across seriously, and tend to adjust rather than dismiss it. One pattern worth noticing: your sense of who you are may shift somewhat depending on who's reflecting it back to you.",
      matchingRule: { dimensionRanges: { flexibility: [60, 100], communication: [45, 100] } },
    },
    {
      key: "the_misread_one",
      name: "The Misread One",
      descriptionTemplate:
        "Your responses suggest there may be a real gap between how you feel internally and how you tend to come across to others — and that gap may matter more to you than you let on.",
      matchingRule: { dimensionRanges: { communication: [0, 45], validation: [55, 100] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your social pattern is:",
    insightIntro:
      "Your responses suggest a specific gap — or lack of one — between how you feel in social settings and how you actually come across to the people in them.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you show up socially.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "social.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "social.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "social.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "social.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "social.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "social.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "social.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "social.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "social.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "social.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "communication",
      condition: { dimensionRanges: { communication: [0, 50] } },
      weight: 1,
      bridgeCopy: "There's a specific reason that gap exists — want to see what your communication DNA has to do with it?",
    },
    {
      assessmentSlug: "hidden-self",
      condition: { dimensionRanges: { validation: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "How much a room's approval matters to you often connects to what you keep hidden — curious to explore that?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
