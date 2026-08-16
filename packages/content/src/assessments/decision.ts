import type { AssessmentConfig } from "@inner/assessment-engine";

/** "Your Decision DNA" — /decision. See docs/ARCHITECTURE.md §3. */
export const decisionAssessment: AssessmentConfig = {
  slug: "decision",
  name: "Your Decision DNA",
  category: "self",
  description: "A short, adaptive conversation about how you actually decide, once it counts.",
  hook: "How you decide says more about you than what you decide.",
  targetAudience: "Adults curious about their own patterns of risk, certainty, and commitment.",
  status: "published",
  version: 1,
  minQuestions: 6,
  recommendedQuestions: 9,
  maxQuestions: 12,

  dimensions: [
    { key: "risk", weight: 1 },
    { key: "control", weight: 1 },
    { key: "flexibility", weight: 1 },
    { key: "curiosity", weight: 1 },
    { key: "security", weight: 1 },
    { key: "independence", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  questionBank: {
    core: [
      {
        key: "big_decision_style",
        type: "single_select",
        isCore: true,
        prompt: "When facing a big decision, you typically...",
        options: [
          { key: "decide_quickly", label: "Decide quickly and adjust later", dimensionContributions: { risk: 2 } },
          { key: "research_exhaustively", label: "Research exhaustively first", dimensionContributions: { security: 2, control: 1 } },
          { key: "ask_others", label: "Ask others for input", dimensionContributions: { independence: -1 } },
          { key: "wait_and_see", label: "Wait and see what happens", dimensionContributions: { control: -2, flexibility: 1 } },
        ],
      },
      {
        key: "regret_tolerance",
        type: "single_select",
        isCore: true,
        prompt: "How do you feel about decisions that don't work out?",
        options: [
          { key: "own_it_move_on", label: "I own it and move on", dimensionContributions: { risk: 1, security: 1 } },
          { key: "replay_it", label: "I replay it a lot", dimensionContributions: { security: -2 } },
          { key: "learn_from_it", label: "I look for what I can learn", dimensionContributions: { flexibility: 2 } },
          { key: "external_reasons", label: "I look for what went wrong externally", dimensionContributions: { control: 1 } },
        ],
      },
      {
        key: "certainty_scale",
        type: "scale",
        isCore: true,
        prompt: "How much certainty do you need before committing to something big?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "changing_your_mind",
        type: "single_select",
        isCore: true,
        prompt: "Once you've decided something, changing your mind...",
        options: [
          { key: "easily_new_info", label: "Happens easily if new information comes in", dimensionContributions: { flexibility: 2 } },
          { key: "admitting_failure", label: "Feels like admitting failure", dimensionContributions: { control: 1, security: -1 } },
          { key: "rare_commit_hard", label: "Is rare — I commit hard", dimensionContributions: { control: 2 } },
          { key: "more_than_id_like", label: "Happens more than I'd like", dimensionContributions: { flexibility: 1, security: -1 } },
        ],
      },
      {
        key: "risk_vs_safety",
        type: "single_select",
        isCore: true,
        prompt: "Given a choice between a safe, known option and a risky, exciting one, you lean...",
        options: [
          { key: "risky_most", label: "Risky, most of the time", dimensionContributions: { risk: 2, curiosity: 1 } },
          { key: "safe_most", label: "Safe, most of the time", dimensionContributions: { risk: -2, security: 1 } },
          { key: "depends_stake", label: "It depends on what's at stake", dimensionContributions: { flexibility: 1 } },
          { key: "get_stuck", label: "I get stuck between them", dimensionContributions: { control: -1 } },
        ],
      },
      {
        key: "decision_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a big decision you made that surprised people. What made you go that way?",
        dynamicFollowupCandidates: ["what_made_you_go_that_way", "would_you_decide_same_again"],
      },
      {
        key: "deciding_for_others",
        type: "single_select",
        isCore: true,
        prompt: "Making a decision that affects someone else feels...",
        options: [
          { key: "no_different", label: "No different than deciding for myself", dimensionContributions: { independence: 2, control: 1 } },
          { key: "heavier", label: "Heavier — I factor them in a lot", dimensionContributions: { independence: -2 } },
          { key: "together", label: "Something I try to make together", dimensionContributions: { independence: -1, flexibility: 1 } },
          { key: "avoid_deciding_for", label: "Something I try to avoid", dimensionContributions: { control: -2 } },
        ],
      },
      {
        key: "gut_vs_logic",
        type: "single_select",
        isCore: true,
        prompt: "When it comes down to it, you trust...",
        options: [
          { key: "gut_mostly", label: "My gut, mostly", dimensionContributions: { risk: 1, curiosity: 1 } },
          { key: "logic_mostly", label: "Logic and evidence, mostly", dimensionContributions: { security: 1, control: 1 } },
          { key: "lean_gut", label: "A mix, but I lean gut", dimensionContributions: { risk: 1 } },
          { key: "lean_logic", label: "A mix, but I lean logic", dimensionContributions: { control: 1 } },
        ],
      },
    ],
    adaptivePool: [
      {
        key: "what_made_you_go_that_way",
        type: "single_select",
        isCore: false,
        prompt: "What actually made you go that way?",
        options: [
          { key: "gut_feeling", label: "A gut feeling I trusted", dimensionContributions: { risk: 2 } },
          { key: "new_info", label: "New information that changed things", dimensionContributions: { flexibility: 1 } },
          { key: "done_waiting", label: "I was done waiting", dimensionContributions: { control: 1 } },
          { key: "still_not_sure", label: "Honestly, I'm still not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "would_you_decide_same_again",
        type: "single_select",
        isCore: false,
        prompt: "Knowing what you know now, would you decide the same way again?",
        options: [
          { key: "yes_without_hesitation", label: "Yes, without hesitation", dimensionContributions: { security: 1 } },
          { key: "yes_but_close", label: "Yes, but it was close", dimensionContributions: {} },
          { key: "no_differently", label: "No, I'd do it differently", dimensionContributions: { flexibility: 1 } },
          { key: "still_dont_know", label: "I still don't know", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "admitting_failure_signal",
      trigger: { questionKey: "changing_your_mind", op: "answered_option", optionKey: "admitting_failure" },
      action: { type: "ask_followup", followupQuestionKey: "would_you_decide_same_again" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "decision_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
  ],

  profiles: [
    {
      key: "the_quick_committer",
      name: "The Quick Committer",
      descriptionTemplate:
        "Your responses suggest you decide fast and commit hard, trusting that you can adjust course later if needed. This can be a real advantage in moving situations forward — occasionally at the cost of information you might have gathered with more patience.",
      matchingRule: { dimensionRanges: { risk: [60, 100], control: [45, 100] } },
    },
    {
      key: "the_researcher",
      name: "The Researcher",
      descriptionTemplate:
        "Your responses suggest you want real certainty before committing to something big, and tend to gather information methodically rather than go on instinct. This reduces regret, though it may sometimes cost you speed.",
      matchingRule: { dimensionRanges: { security: [60, 100], control: [55, 100] } },
    },
    {
      key: "the_flexible_reviser",
      name: "The Flexible Reviser",
      descriptionTemplate:
        "Your responses suggest you hold your decisions loosely, willing to revise course when new information arrives rather than treating a decision as final the moment it's made.",
      matchingRule: { dimensionRanges: { flexibility: [60, 100], control: [0, 50] } },
    },
    {
      key: "the_relational_decider",
      name: "The Relational Decider",
      descriptionTemplate:
        "Your responses suggest you factor other people into your decisions more than most, sometimes weighing their needs before your own. One pattern worth noticing: this can make your own preferences harder to locate when it's just you.",
      matchingRule: { dimensionRanges: { independence: [0, 45], flexibility: [40, 100] } },
    },
  ],

  freeResultTemplate: {
    headline: "Your decision-making pattern is:",
    insightIntro:
      "Your responses suggest a specific pattern in how you weigh risk, certainty, and other people once a real decision is on the table.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you make decisions.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "decision.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "decision.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "decision.how_you_connect" },
    { key: "what_you_need", title: "What You May Need", promptRef: "decision.what_you_need" },
    { key: "how_you_react", title: "How You May React", promptRef: "decision.how_you_react" },
    { key: "strengths", title: "Your Strengths", promptRef: "decision.strengths" },
    { key: "friction_points", title: "Potential Friction Points", promptRef: "decision.friction_points" },
    { key: "perception", title: "What Others May Perceive", promptRef: "decision.perception" },
    { key: "reflection", title: "Reflection Questions", promptRef: "decision.reflection" },
    { key: "conclusion", title: "Your Personalized Conclusion", promptRef: "decision.conclusion" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "hidden-self",
      condition: { dimensionRanges: { control: [55, 100] } },
      weight: 1,
      bridgeCopy: "How tightly you hold onto control in decisions often connects to what you keep hidden — curious to see that link?",
    },
    {
      assessmentSlug: "connection",
      condition: { dimensionRanges: { risk: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "That same appetite for risk tends to show up in who you're drawn to — want to see how?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
