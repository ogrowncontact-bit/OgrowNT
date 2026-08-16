import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Jealousy Profile" — /jealousy. See docs/ARCHITECTURE.md §3. */
export const jealousyAssessment: AssessmentConfig = {
  slug: "jealousy",
  name: "Your Jealousy Profile",
  category: "relationships",
  description: "A short, adaptive conversation about what jealousy actually feels like underneath, for you specifically.",
  hook: "Jealousy rarely means what it looks like from the outside.",
  targetAudience: "Adults curious about their own jealousy patterns without judgment.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "trust", weight: 1 },
    { key: "control", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "security", weight: 1 },
    { key: "risk", weight: 1 },
    { key: "communication", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "jealousy_trigger",
        type: "single_select",
        isCore: true,
        prompt: "What's most likely to trigger a flicker of jealousy for you?",
        options: [
          { key: "getting_close", label: "Them getting close to someone new", dimensionContributions: { trust: -1, security: -1 } },
          { key: "not_knowing", label: "Not knowing where they are", dimensionContributions: { control: 1, security: -1 } },
          { key: "less_priority", label: "Feeling less prioritized", dimensionContributions: { validation: 2 } },
          { key: "not_much", label: "Honestly, not much", dimensionContributions: { trust: 2, security: 1 } },
        ],
      },
      {
        key: "reaction_to_jealousy",
        type: "single_select",
        isCore: true,
        prompt: "When you notice yourself feeling jealous, you tend to...",
        options: [
          { key: "say_it", label: "Say something right away", dimensionContributions: { communication: 2 } },
          { key: "sit_with_it", label: "Sit with it privately first", dimensionContributions: { communication: -1, control: -1 } },
          { key: "seek_reassurance", label: "Look for reassurance", dimensionContributions: { validation: 2 } },
          { key: "talk_out_of_it", label: "Try to talk myself out of it", dimensionContributions: { trust: 1, control: 1 } },
        ],
      },
      {
        key: "checking_behavior_scale",
        type: "scale",
        isCore: true,
        prompt: "How often do you find yourself wanting to check in — messages, socials, whereabouts?",
        scaleMax: 5,
        scaleDimension: "control",
      },
      {
        key: "someone_flirts_with_partner",
        type: "single_select",
        isCore: true,
        prompt: "If someone flirted with your partner in front of you, you'd probably feel...",
        options: [
          { key: "amused", label: "Amused, not threatened", dimensionContributions: { trust: 2, security: 1 } },
          { key: "passing_discomfort", label: "A spike of discomfort that passes", dimensionContributions: { security: -1 } },
          { key: "rattled", label: "Genuinely rattled", dimensionContributions: { security: -2, validation: 1 } },
          { key: "territorial", label: "Protective and a little territorial", dimensionContributions: { control: 2, risk: -1 } },
        ],
      },
      {
        key: "comparison_habit",
        type: "single_select",
        isCore: true,
        prompt: "Do you find yourself comparing yourself to people your partner is close to?",
        options: [
          { key: "rarely", label: "Rarely or never", dimensionContributions: { validation: 2, trust: 1 } },
          { key: "sometimes", label: "Sometimes, if I'm already feeling insecure", dimensionContributions: { validation: -1 } },
          { key: "often", label: "Fairly often", dimensionContributions: { validation: -2, security: -1 } },
          { key: "certain_people", label: "Only with certain people", dimensionContributions: { validation: -1 } },
        ],
      },
      {
        key: "jealousy_openness",
        type: "open_text",
        isCore: true,
        prompt: "Tell us about a time jealousy showed up for you — what did it actually feel like underneath?",
        dynamicFollowupCandidates: ["underneath_the_jealousy", "what_would_reassure"],
      },
      {
        key: "partner_jealous_of_you",
        type: "single_select",
        isCore: true,
        prompt: "When your partner seems jealous, your instinct is to...",
        options: [
          { key: "reassure", label: "Reassure them right away", dimensionContributions: { communication: 2, validation: 1 } },
          { key: "suffocated", label: "Feel a little suffocated", dimensionContributions: { control: -1, risk: 1 } },
          { key: "flattered", label: "Feel flattered", dimensionContributions: { validation: 1 } },
          { key: "frustrated", label: "Get frustrated", dimensionContributions: { communication: -1 } },
        ],
      },
      {
        key: "trust_default_jealousy",
        type: "single_select",
        isCore: true,
        prompt: "Left with no information, your default assumption about a partner's silence is...",
        options: [
          { key: "just_busy", label: "They're just busy", dimensionContributions: { trust: 2 } },
          { key: "probably_fine", label: "Something's probably fine", dimensionContributions: { trust: 1 } },
          { key: "worst_case", label: "I start imagining worst cases", dimensionContributions: { trust: -2, security: -2 } },
          { key: "no_assume", label: "I try not to assume", dimensionContributions: { trust: 1, control: -1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "underneath_the_jealousy",
        type: "single_select",
        isCore: false,
        prompt: "Underneath the jealousy, what does it feel closest to?",
        options: [
          { key: "fear_losing", label: "Fear of losing them", dimensionContributions: { security: -2 } },
          { key: "not_enough", label: "Feeling not enough", dimensionContributions: { validation: -2 } },
          { key: "losing_control", label: "Losing control of the situation", dimensionContributions: { control: -2 } },
          { key: "not_sure_underneath", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "what_would_reassure",
        type: "single_select",
        isCore: false,
        prompt: "What would help most in that moment?",
        options: [
          { key: "direct_reassurance", label: "Clear, direct reassurance", dimensionContributions: { validation: 1, communication: 1 } },
          { key: "space_alone", label: "Space to work through it alone", dimensionContributions: { control: 1 } },
          { key: "concrete_facts", label: "Concrete facts, not just words", dimensionContributions: { trust: -1 } },
          { key: "nothing_helps", label: "Nothing really helps in the moment", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "rattled_signal",
      trigger: { questionKey: "someone_flirts_with_partner", op: "answered_option", optionKey: "rattled" },
      action: { type: "ask_followup", followupQuestionKey: "underneath_the_jealousy" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "jealousy_openness", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_secure_observer",
      name: "The Secure Observer",
      descriptionTemplate:
        "Your responses suggest jealousy rarely takes hold for you — and when it flickers, it tends to pass quickly rather than escalate. This appears to sit on a fairly solid base of trust.",
      matchingRule: { dimensionRanges: { trust: [65, 100], security: [60, 100] } },
    },
    {
      key: "the_quiet_worrier",
      name: "The Quiet Worrier",
      descriptionTemplate:
        "Your responses suggest jealousy tends to show up for you as a need for reassurance rather than confrontation — often worn internally more than expressed outright.",
      matchingRule: { dimensionRanges: { validation: [55, 100], security: [0, 45] } },
    },
    {
      key: "the_direct_namer",
      name: "The Direct Namer",
      descriptionTemplate:
        "Your responses suggest jealousy gets voiced quickly and directly for you rather than left to build — you appear to trust that naming it will actually help, more than most.",
      matchingRule: { dimensionRanges: { communication: [60, 100], trust: [45, 100] } },
    },
    {
      key: "the_watchguard",
      name: "The Watchguard",
      descriptionTemplate:
        "Your responses suggest jealousy shows up as a pull toward monitoring or certainty-seeking, more than open conversation. One pattern worth noticing: this may be less about distrust itself, and more about needing information to feel settled.",
      matchingRule: { dimensionRanges: { control: [55, 100], trust: [0, 45] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your jealousy pattern is:",
    insightIntro:
      "Your responses suggest a specific way jealousy tends to surface for you — and what it's usually really about, underneath the surface reaction.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how jealousy shows up for you.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "jealousy.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "jealousy.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "jealousy.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "jealousy.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "jealousy.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "jealousy.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "jealousy.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "jealousy.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "jealousy.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "jealousy.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { security: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers pointed to security shaping a lot of this pattern — want to see how that same thread shows up in intimacy?",
    },
    {
      assessmentSlug: "hidden-self",
      condition: { dimensionRanges: { control: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "There's often more underneath a need for control than meets the eye — curious what your hidden self might reveal?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
