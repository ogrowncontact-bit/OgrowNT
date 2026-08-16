import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Communication DNA" — /communication. See docs/ARCHITECTURE.md §3. */
export const communicationAssessment: AssessmentConfig = {
  slug: "communication",
  name: "Your Communication DNA",
  category: "social",
  description: "A short, adaptive conversation about how you actually say what you mean — and what gets in the way.",
  hook: "It's rarely what you meant to say. It's how it landed.",
  targetAudience: "Adults curious about their own communication patterns, especially under pressure.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "communication", weight: 1 },
    { key: "conflict", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "control", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "validation", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "default_communication_style",
        type: "single_select",
        isCore: true,
        prompt: "When something's bothering you, your default is to...",
        options: [
          { key: "plainly_direct", label: "Say it plainly and directly", dimensionContributions: { communication: 2 } },
          { key: "hint", label: "Hint at it and hope they pick up on it", dimensionContributions: { communication: -2 } },
          { key: "wait_calm_moment", label: "Wait for a calm moment to bring it up", dimensionContributions: { communication: 1, flexibility: 1 } },
          { key: "write_first", label: "Write it down before saying it", dimensionContributions: { communication: 1 } },
        ],
      },
      {
        key: "receiving_criticism",
        type: "single_select",
        isCore: true,
        prompt: "Receiving criticism, even gentle, feels...",
        options: [
          { key: "useful", label: "Useful — I want to know", dimensionContributions: { flexibility: 2 } },
          { key: "fine_if_kind", label: "Fine if it's delivered kindly", dimensionContributions: { emotional_openness: 1 } },
          { key: "hard_personally", label: "Hard not to take personally", dimensionContributions: { validation: -2 } },
          { key: "push_back", label: "Something I quietly push back on", dimensionContributions: { control: 1, communication: -1 } },
        ],
      },
      {
        key: "directness_scale",
        type: "scale",
        isCore: true,
        prompt: "How directly do you typically say what you mean, versus softening it?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "silence_in_conversation",
        type: "single_select",
        isCore: true,
        prompt: "A silence in a conversation feels...",
        options: [
          { key: "comfortable", label: "Comfortable", dimensionContributions: { emotional_openness: 1, control: -1 } },
          { key: "want_fill", label: "Something I want to fill", dimensionContributions: { control: 1 } },
          { key: "little_awkward", label: "A little awkward, but okay", dimensionContributions: {} },
          { key: "something_wrong", label: "Like something's wrong", dimensionContributions: { validation: -1 } },
        ],
      },
      {
        key: "text_vs_talk",
        type: "single_select",
        isCore: true,
        prompt: "For a hard conversation, you'd rather...",
        options: [
          { key: "face_to_face", label: "Talk face to face", dimensionContributions: { emotional_openness: 2, communication: 1 } },
          { key: "on_a_call", label: "Talk on a call", dimensionContributions: { emotional_openness: 1 } },
          { key: "text_first", label: "Text it out first", dimensionContributions: { emotional_openness: -1, control: 1 } },
          { key: "avoid", label: "Avoid it as long as possible", dimensionContributions: { communication: -2 } },
        ],
      },
      {
        key: "communication_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a time a conversation went badly because of how something was said, not what was said. What happened?",
        dynamicFollowupCandidates: ["what_would_you_change", "does_this_happen_often"],
      },
      {
        key: "giving_feedback",
        type: "single_select",
        isCore: true,
        prompt: "Giving someone else difficult feedback feels...",
        options: [
          { key: "straightforward", label: "Straightforward — I just say it", dimensionContributions: { communication: 2, control: 1 } },
          { key: "uncomfortable_necessary", label: "Uncomfortable but necessary", dimensionContributions: { communication: 1 } },
          { key: "avoid_soften", label: "Something I avoid or soften heavily", dimensionContributions: { communication: -2, conflict: -1 } },
          { key: "someone_else", label: "I'd rather someone else do it", dimensionContributions: { communication: -2 } },
        ],
      },
      {
        key: "conflict_style_comm",
        type: "single_select",
        isCore: true,
        prompt: "In an actual disagreement, your words tend to get...",
        options: [
          { key: "more_precise", label: "More precise and direct", dimensionContributions: { communication: 2, conflict: 1 } },
          { key: "more_careful", label: "More careful and measured", dimensionContributions: { flexibility: 1 } },
          { key: "harder_to_find", label: "Harder to find", dimensionContributions: { communication: -2 } },
          { key: "more_heated", label: "More heated than intended", dimensionContributions: { conflict: 2, control: -1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "what_would_you_change",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, what would you have said differently?",
        options: [
          { key: "been_more_direct", label: "Been more direct", dimensionContributions: { communication: 1 } },
          { key: "been_softer", label: "Been softer", dimensionContributions: { emotional_openness: 1 } },
          { key: "said_sooner", label: "Said it sooner", dimensionContributions: { control: 1 } },
          { key: "nothing_would_change", label: "Honestly, nothing", dimensionContributions: {} },
        ],
      },
      {
        key: "does_this_happen_often",
        type: "single_select",
        isCore: false,
        prompt: "Does this kind of miscommunication happen to you often?",
        options: [
          { key: "more_than_id_like", label: "More than I'd like", dimensionContributions: { communication: -1 } },
          { key: "rarely_stood_out", label: "Rarely — it stood out", dimensionContributions: {} },
          { key: "specific_people", label: "Mostly with specific people", dimensionContributions: {} },
          { key: "never_noticed_pattern", label: "I've never really noticed a pattern", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "hint_signal",
      trigger: { questionKey: "default_communication_style", op: "answered_option", optionKey: "hint" },
      action: { type: "ask_followup", followupQuestionKey: "does_this_happen_often" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "communication_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_plain_speaker",
      name: "The Plain Speaker",
      descriptionTemplate:
        "Your responses suggest you say what you mean fairly directly, and tend to take feedback in stride rather than defensively. This can make you easy to have a real conversation with — occasionally at the cost of softening things for people who need more cushion.",
      matchingRule: { dimensionRanges: { communication: [60, 100], flexibility: [45, 100] } },
    },
    {
      key: "the_careful_softener",
      name: "The Careful Softener",
      descriptionTemplate:
        "Your responses suggest you tend to time and soften what you say rather than state it plainly, often waiting for the right moment. This appears to come from real care about how things land, more than avoidance.",
      matchingRule: { dimensionRanges: { communication: [0, 50], emotional_openness: [40, 100] } },
    },
    {
      key: "the_withholder",
      name: "The Withholder",
      descriptionTemplate:
        "Your responses suggest you tend to keep a fair amount unsaid, preferring to manage things internally rather than put them into words. One pattern worth noticing: what doesn't get said often doesn't disappear — it tends to surface some other way.",
      matchingRule: { dimensionRanges: { communication: [0, 45], control: [55, 100] } },
    },
    {
      key: "the_heated_communicator",
      name: "The Heated Communicator",
      descriptionTemplate:
        "Your responses suggest your words tend to get more intense once a disagreement is underway, sometimes more than you intend going in. This often comes from caring a lot about the outcome, even when it doesn't read that way in the moment.",
      matchingRule: { dimensionRanges: { conflict: [55, 100], control: [0, 45] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your communication pattern is:",
    insightIntro:
      "Your responses suggest a specific pattern in how you say what you mean — and what tends to happen to your words under pressure.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you communicate.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "communication.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "communication.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "communication.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "communication.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "communication.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "communication.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "communication.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "communication.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "communication.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "communication.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "relationship",
      condition: { dimensionRanges: { conflict: [55, 100] } },
      weight: 1,
      bridgeCopy: "How you communicate under pressure tends to shape a relationship's whole rhythm — want to see that bigger picture?",
    },
    {
      assessmentSlug: "social",
      condition: { dimensionRanges: { communication: [0, 50] } },
      weight: 0.8,
      bridgeCopy: "What doesn't get said often still gets read by other people — curious how you actually come across?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
