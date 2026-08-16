import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Hidden Self" — /hidden-self. See docs/ARCHITECTURE.md §3. */
export const hiddenSelfAssessment: AssessmentConfig = {
  slug: "hidden-self",
  name: "Your Hidden Self",
  category: "self",
  description: "A short, adaptive conversation about the parts of yourself you manage, edit, or keep out of view.",
  hook: "Almost everyone is carrying a version of themselves no one else has met.",
  targetAudience: "Adults curious about the gap between their private and presented selves.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "vulnerability", weight: 1 },
    { key: "control", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "security", weight: 1 },
    { key: "social_confidence", weight: 1 },
    { key: "emotional_openness", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "part_you_hide",
        type: "single_select",
        isCore: true,
        prompt: "Is there a part of yourself you actively keep from most people?",
        options: [
          { key: "deliberate", label: "Yes, and I'm deliberate about it", dimensionContributions: { control: 2, vulnerability: -1 } },
          { key: "not_a_choice", label: "Yes, but it's not really a choice", dimensionContributions: { vulnerability: -2 } },
          { key: "what_you_see", label: "Not really — what you see is what you get", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "never_thought", label: "I've never thought about it", dimensionContributions: { curiosity: -1 } },
        ],
      },
      {
        key: "persona_vs_private",
        type: "single_select",
        isCore: true,
        prompt: "How different is the \"you\" most people see from the private you?",
        options: [
          { key: "very_different", label: "Very different", dimensionContributions: { vulnerability: -2, control: 1 } },
          { key: "curated_version", label: "Somewhat — a curated version", dimensionContributions: { vulnerability: -1 } },
          { key: "barely_different", label: "Barely different at all", dimensionContributions: { vulnerability: 2 } },
          { key: "depends_setting", label: "Depends heavily on the setting", dimensionContributions: { control: 1 } },
        ],
      },
      {
        key: "hidden_scale",
        type: "scale",
        isCore: true,
        prompt: "How much effort do you put into managing how people perceive you?",
        scaleMax: 5,
        scaleDimension: "control",
      },
      {
        key: "who_knows_the_real_you",
        type: "single_select",
        isCore: true,
        prompt: "How many people do you think actually know the real you?",
        options: [
          { key: "just_me", label: "Just me, honestly", dimensionContributions: { vulnerability: -2, security: -1 } },
          { key: "one_or_two", label: "One or two people", dimensionContributions: { vulnerability: 1 } },
          { key: "close_few", label: "A close few", dimensionContributions: { vulnerability: 1, social_confidence: 1 } },
          { key: "most_who_know_me", label: "Most people who know me well", dimensionContributions: { vulnerability: 2 } },
        ],
      },
      {
        key: "fear_of_being_known",
        type: "single_select",
        isCore: true,
        prompt: "If someone saw the parts of you that you hide, you think they'd...",
        options: [
          { key: "understand", label: "Understand, not judge", dimensionContributions: { security: 2, vulnerability: 1 } },
          { key: "surprised_okay", label: "Be surprised but okay with it", dimensionContributions: { security: 1 } },
          { key: "think_less", label: "Think less of me", dimensionContributions: { security: -2 } },
          { key: "dont_know", label: "I genuinely don't know", dimensionContributions: { curiosity: 1 } },
        ],
      },
      {
        key: "hidden_self_open_text",
        type: "open_text",
        isCore: true,
        prompt:
          "What's something true about you that almost no one knows? You don't have to say what it is — just what it's like to carry it.",
        dynamicFollowupCandidates: ["why_keep_it_hidden", "what_would_change_if_known"],
      },
      {
        key: "alone_vs_with_others",
        type: "single_select",
        isCore: true,
        prompt: "You feel most like yourself...",
        options: [
          { key: "completely_alone", label: "Completely alone", dimensionContributions: { vulnerability: -1, social_confidence: -1 } },
          { key: "one_specific_person", label: "With one specific person", dimensionContributions: { vulnerability: 2 } },
          { key: "safe_group", label: "In a group where I feel safe", dimensionContributions: { security: 1, social_confidence: 1 } },
          { key: "not_sure_self", label: "I'm not sure I know", dimensionContributions: { curiosity: 1 } },
        ],
      },
      {
        key: "secrets_comfort",
        type: "single_select",
        isCore: true,
        prompt: "Keeping a secret, in general, feels...",
        options: [
          { key: "easy_private", label: "Easy — I'm naturally private", dimensionContributions: { control: 2 } },
          { key: "fine_good_reason", label: "Fine if it's for a good reason", dimensionContributions: { control: 1 } },
          { key: "heavy", label: "Heavy — I'd rather not", dimensionContributions: { vulnerability: 1, emotional_openness: 1 } },
          { key: "depends_what", label: "Depends entirely what it is", dimensionContributions: {} },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "why_keep_it_hidden",
        type: "single_select",
        isCore: false,
        prompt: "What's the main reason it stays hidden?",
        options: [
          { key: "fear_judgment", label: "Fear of judgment", dimensionContributions: { security: -2 } },
          { key: "private_not_shameful", label: "It's just private, not shameful", dimensionContributions: { control: 1 } },
          { key: "never_right_moment", label: "I've never found the right moment", dimensionContributions: { vulnerability: -1 } },
          { key: "not_sure_hidden", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "what_would_change_if_known",
        type: "single_select",
        isCore: false,
        prompt: "If it became known, what do you think would actually change?",
        options: [
          { key: "nothing_much", label: "Nothing much", dimensionContributions: { security: 1 } },
          { key: "how_seen", label: "How people see me", dimensionContributions: { security: -1 } },
          { key: "own_relief", label: "My own relief", dimensionContributions: { vulnerability: 2 } },
          { key: "dont_want_think", label: "I don't want to think about it", dimensionContributions: { control: 1 } },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "not_a_choice_signal",
      trigger: { questionKey: "part_you_hide", op: "answered_option", optionKey: "not_a_choice" },
      action: { type: "ask_followup", followupQuestionKey: "why_keep_it_hidden" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "hidden_self_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_open_ledger",
      name: "The Open Ledger",
      descriptionTemplate:
        "Your responses suggest little gap between the private you and the you most people see. You don't appear to spend much effort managing how you're perceived, which tends to read as authenticity to the people around you.",
      matchingRule: { dimensionRanges: { vulnerability: [60, 100], control: [0, 45] } },
    },
    {
      key: "the_curator",
      name: "The Curator",
      descriptionTemplate:
        "Your responses suggest you put real, deliberate effort into how you're perceived — not out of dishonesty, but as a considered choice about what gets shown and when.",
      matchingRule: { dimensionRanges: { control: [60, 100], vulnerability: [0, 55] } },
    },
    {
      key: "the_quiet_keeper",
      name: "The Quiet Keeper",
      descriptionTemplate:
        "Your responses suggest you carry a fair amount privately, without much sense that it would be safe or welcomed if it were known. One pattern worth noticing: this may be less a preference and more a habit that's never really been tested.",
      matchingRule: { dimensionRanges: { vulnerability: [0, 45], security: [0, 45] } },
    },
    {
      key: "the_selectively_known",
      name: "The Selectively Known",
      descriptionTemplate:
        "Your responses suggest you're socially at ease in most settings, while reserving your fuller self for a smaller circle. This appears to be a deliberate, functional split rather than avoidance.",
      matchingRule: { dimensionRanges: { social_confidence: [55, 100], vulnerability: [35, 70] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your hidden-self pattern is:",
    insightIntro:
      "Your responses suggest a specific pattern in how much of yourself you show versus manage — and what tends to drive the difference.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in what you keep hidden and why.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "hidden-self.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "hidden-self.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "hidden-self.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "hidden-self.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "hidden-self.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "hidden-self.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "hidden-self.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "hidden-self.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "hidden-self.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "hidden-self.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "vulnerability",
      condition: { dimensionRanges: { vulnerability: [0, 50] } },
      weight: 1,
      bridgeCopy: "There's a specific pattern behind what you keep hidden — want to look at your vulnerability profile directly?",
    },
    {
      assessmentSlug: "decision",
      condition: { dimensionRanges: { control: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "How much you manage your image often connects to how you make decisions in general — curious to see that pattern?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
