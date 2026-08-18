import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "Your Relationship Pattern" — /relationship. Second reference-depth
 * experience after LOVE (docs/ARCHITECTURE.md §3). Where LOVE looks at how
 * someone enters and holds closeness, this looks at the dynamic a
 * relationship settles into once it's underway — security, expectations,
 * conflict, and how those hold up over time.
 */
export const relationshipAssessment: AssessmentConfig = {
  slug: "relationship",
  name: "Your Relationship Pattern",
  category: "relationships",
  description: "A short, adaptive conversation about the dynamic you tend to build once a relationship settles in.",
  hook: "The pattern isn't in any one relationship — it's in the shape they keep taking.",
  targetAudience: "Adults curious about recurring dynamics across their relationships.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "security", weight: 1 },
    { key: "independence", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "conflict", weight: 1 },
    { key: "communication", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "expectations", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "connection_independence",
      label: "wanting real closeness while still holding onto real independence",
      dimensionA: "connection",
      thresholdA: 65,
      dimensionB: "independence",
      thresholdB: 65,
    },
    {
      key: "expectations_low_security",
      label: "holding relationships to a clear standard while still feeling uneasy about where you stand",
      dimensionA: "expectations",
      thresholdA: 65,
      dimensionB: "security",
      thresholdB: 35,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "conflict_response",
        type: "single_select",
        isCore: true,
        prompt: "When a disagreement starts heating up, what do you usually do?",
        options: [
          { key: "push_through", label: "Keep going until it's resolved", dimensionContributions: { conflict: 2, communication: 1 } },
          { key: "need_pause", label: "Need a pause before continuing", dimensionContributions: { conflict: -1, independence: 1 } },
          { key: "smooth_over", label: "Try to smooth it over quickly", dimensionContributions: { conflict: -2, security: 1 } },
          { key: "withdraw", label: "Go quiet and withdraw", dimensionContributions: { conflict: -2, emotional_openness: -2 } },
        ],
      },
      {
        key: "relationship_rhythm",
        type: "single_select",
        isCore: true,
        prompt: "Once a relationship settles in, it tends to feel like...",
        options: [
          { key: "steady", label: "A steady, predictable rhythm", dimensionContributions: { security: 2 } },
          { key: "cycles", label: "Cycles of closeness and distance", dimensionContributions: { connection: 1, security: -1 } },
          { key: "constant_renegotiation", label: "Something we're always renegotiating", dimensionContributions: { expectations: 2, communication: 1 } },
          { key: "whatever_they_need", label: "Whatever the other person needs it to be", dimensionContributions: { independence: -2, connection: 1 } },
        ],
      },
      {
        key: "expectations_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you go into relationships with a clear picture of how things \"should\" unfold?",
        scaleMax: 5,
        scaleDimension: "expectations",
      },
      {
        key: "trust_pace",
        type: "single_select",
        isCore: true,
        prompt: "How quickly do you typically extend real trust to a partner?",
        options: [
          { key: "quickly", label: "Pretty quickly", dimensionContributions: { trust: 2 } },
          { key: "gradually", label: "Gradually, as things go well", dimensionContributions: { trust: 1, expectations: 1 } },
          { key: "only_after_proof", label: "Only after it's been proven", dimensionContributions: { trust: -2, expectations: 1 } },
          { key: "rarely_fully", label: "Rarely fully, if I'm honest", dimensionContributions: { trust: -2, independence: 1 } },
        ],
      },
      {
        key: "decision_making_together",
        type: "single_select",
        isCore: true,
        prompt: "When making a big decision together, you...",
        options: [
          { key: "lead", label: "Want to lead the process", dimensionContributions: { independence: 2 } },
          { key: "follow", label: "Prefer to follow their lead", dimensionContributions: { independence: -2 } },
          { key: "split", label: "Push for a genuine 50/50 split", dimensionContributions: { communication: 2, connection: 1 } },
          { key: "avoid", label: "Avoid deciding as long as possible", dimensionContributions: { conflict: -1, communication: -2 } },
        ],
      },
      {
        key: "security_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you rely on things staying predictable in a relationship to feel secure?",
        scaleMax: 5,
        scaleDimension: "security",
      },
      {
        key: "when_things_change",
        type: "single_select",
        isCore: true,
        prompt: "When a relationship's dynamic shifts unexpectedly, you feel...",
        options: [
          { key: "adaptable", label: "Adaptable — I go with it", dimensionContributions: { security: 1, expectations: -1 } },
          { key: "unsettled", label: "Unsettled until things stabilize", dimensionContributions: { security: -2, expectations: 1 } },
          { key: "want_explanation", label: "Like I need an explanation", dimensionContributions: { communication: 2, trust: -1 } },
          { key: "curious", label: "Curious about where it's going", dimensionContributions: { connection: 1, expectations: -1 } },
        ],
      },
      {
        key: "expressing_needs",
        type: "single_select",
        isCore: true,
        prompt: "When something's bothering you in a relationship, you usually...",
        options: [
          { key: "direct", label: "Say it directly, right away", dimensionContributions: { communication: 2, emotional_openness: 2 } },
          { key: "right_moment", label: "Wait for the right moment", dimensionContributions: { communication: 1 } },
          { key: "hope_notice", label: "Hope they notice on their own", dimensionContributions: { communication: -2, emotional_openness: -1 } },
          { key: "indirect", label: "Bring it up indirectly", dimensionContributions: { communication: -1, conflict: -1 } },
        ],
      },
      {
        key: "emotional_openness_scale",
        type: "scale",
        isCore: true,
        prompt: "How openly do you share what you're actually feeling with a partner, in the moment?",
        scaleMax: 5,
        scaleDimension: "emotional_openness",
      },
      {
        key: "independence_within_relationship",
        type: "single_select",
        isCore: true,
        prompt: "Inside a relationship, how important is it to keep parts of your life separate?",
        options: [
          { key: "very", label: "Very — I need that separation", dimensionContributions: { independence: 2 } },
          { key: "somewhat", label: "Somewhat, alongside real togetherness", dimensionContributions: { independence: 1, connection: 1 } },
          { key: "not_much", label: "Not much — I prefer building most things together", dimensionContributions: { independence: -2, connection: 2 } },
          { key: "depends_relationship", label: "It depends entirely on the relationship", dimensionContributions: {} },
        ],
      },
      {
        key: "what_relationships_owe",
        type: "single_select",
        isCore: true,
        prompt: "What do you believe a real relationship owes you?",
        options: [
          { key: "consistency", label: "Consistency", dimensionContributions: { security: 2, expectations: 1 } },
          { key: "honesty", label: "Honesty, even when it's uncomfortable", dimensionContributions: { trust: 2, communication: 1 } },
          { key: "nothing_fixed", label: "Nothing fixed — it should earn its own shape", dimensionContributions: { expectations: -2, independence: 1 } },
          { key: "effort_matching_mine", label: "Effort that matches mine", dimensionContributions: { expectations: 2, connection: 1 } },
        ],
      },
      {
        key: "handling_uncertainty_status",
        type: "single_select",
        isCore: true,
        prompt: "If you weren't sure where a relationship stood, what would you do?",
        options: [
          { key: "ask_directly", label: "Ask directly", dimensionContributions: { communication: 2, trust: 1 } },
          { key: "wait_for_clarity", label: "Wait for it to become clear on its own", dimensionContributions: { independence: 1, expectations: -1 } },
          { key: "assume_the_worst", label: "Assume the worst until I know otherwise", dimensionContributions: { security: -2, expectations: 1 } },
          { key: "stay_and_watch", label: "Stay close and watch for signals", dimensionContributions: { trust: -1 } },
        ],
      },
      {
        key: "power_balance",
        type: "single_select",
        isCore: true,
        prompt: "In your relationships, you tend to feel...",
        options: [
          { key: "matched", label: "Equally matched", dimensionContributions: { connection: 1, security: 1 } },
          { key: "gives_more", label: "Like the one who gives more", dimensionContributions: { security: -1, expectations: 1 } },
          { key: "holds_more", label: "Like the one who holds more control", dimensionContributions: { independence: 2 } },
          { key: "depends_person", label: "It depends entirely on the person", dimensionContributions: {} },
        ],
      },
      {
        key: "expectations_disappointment",
        type: "single_select",
        isCore: true,
        prompt: "When a relationship doesn't match what you hoped for, what's closest to your reaction?",
        options: [
          { key: "adjust_expectations", label: "I adjust what I expected", dimensionContributions: { expectations: -2, security: 1 } },
          { key: "feel_let_down", label: "I feel genuinely let down", dimensionContributions: { expectations: 2, security: -1 } },
          { key: "talk_about_it", label: "I bring it up and talk it through", dimensionContributions: { communication: 2, trust: 1 } },
          { key: "quietly_disengage", label: "I quietly start to disengage", dimensionContributions: { emotional_openness: -2, conflict: -1 } },
        ],
      },
      {
        key: "long_term_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a relationship pattern you keep noticing in yourself — good or bad.",
        dynamicFollowupCandidates: ["what_triggers_pattern", "how_pattern_started"],
      },
      {
        key: "what_makes_it_last",
        type: "open_text",
        isCore: true,
        prompt: "What has made a relationship feel like it was actually working, for you?",
        dynamicFollowupCandidates: ["lasting_when_hard", "lasting_alone_or_together"],
      },
    ],
    adaptivePool: [
      {
        key: "what_triggers_pattern",
        type: "single_select",
        isCore: false,
        prompt: "What usually triggers that pattern for you?",
        options: [
          { key: "feeling_unheard", label: "Feeling unheard", dimensionContributions: { communication: -1, conflict: 1 } },
          { key: "feeling_controlled", label: "Feeling too controlled", dimensionContributions: { independence: -2 } },
          { key: "uncertain_footing", label: "Feeling uncertain about where things stand", dimensionContributions: { security: -2, expectations: 1 } },
          { key: "not_sure_trigger", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "how_pattern_started",
        type: "single_select",
        isCore: false,
        prompt: "Does this feel like a pattern you learned early on, or something newer?",
        options: [
          { key: "goes_back", label: "It goes way back", dimensionContributions: { security: -1 } },
          { key: "recent", label: "It's shown up more recently", dimensionContributions: { expectations: -1 } },
          { key: "both_pattern", label: "A bit of both", dimensionContributions: {} },
          { key: "never_thought", label: "I've never really thought about it", dimensionContributions: {} },
        ],
      },
      {
        key: "lasting_when_hard",
        type: "single_select",
        isCore: false,
        prompt: "What kept it working when things got genuinely hard?",
        options: [
          { key: "staying_through_conflict", label: "Staying in the room through conflict", dimensionContributions: { conflict: 2, trust: 1 } },
          { key: "giving_each_other_space", label: "Giving each other space when needed", dimensionContributions: { independence: 2 } },
          { key: "clear_communication_lasting", label: "Just talking about it clearly", dimensionContributions: { communication: 2 } },
          { key: "consistency_over_time", label: "Consistency, over a long time", dimensionContributions: { security: 2 } },
        ],
      },
      {
        key: "lasting_alone_or_together",
        type: "single_select",
        isCore: false,
        prompt: "Did that feeling come from something you built together, or something you each brought on your own?",
        options: [
          { key: "built_together", label: "Built together, deliberately", dimensionContributions: { connection: 2 } },
          { key: "each_did_their_part", label: "Each of us did our own part", dimensionContributions: { independence: 1, expectations: 1 } },
          { key: "just_happened", label: "Honestly, it just happened", dimensionContributions: { expectations: -2 } },
          { key: "still_figuring_out", label: "I'm still figuring that out", dimensionContributions: {} },
        ],
      },
      {
        key: "withdraw_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "When you go quiet during conflict, what's usually happening underneath?",
        options: [
          { key: "need_time", label: "I genuinely need time to think", dimensionContributions: { independence: 2, conflict: -1 } },
          { key: "afraid_of_saying_wrong", label: "I'm worried about saying the wrong thing", dimensionContributions: { emotional_openness: -2, security: -1 } },
          { key: "dont_see_point", label: "I don't see the point in continuing", dimensionContributions: { conflict: -2, expectations: -1 } },
          { key: "waiting_them_out", label: "I'm waiting for them to make the first move", dimensionContributions: { communication: -2 } },
        ],
      },
      {
        key: "expectations_origin",
        type: "single_select",
        isCore: false,
        prompt: "Where do you think your picture of how relationships \"should\" go comes from?",
        options: [
          { key: "past_relationships", label: "Past relationships", dimensionContributions: { expectations: 1 } },
          { key: "what_ive_observed", label: "What I've observed around me", dimensionContributions: { expectations: 1 } },
          { key: "what_i_need_to_feel_safe", label: "What I need to feel safe", dimensionContributions: { security: 1, expectations: 1 } },
          { key: "not_sure_origin", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "trust_rebuilding",
        type: "single_select",
        isCore: false,
        prompt: "If trust were broken, what would matter most in rebuilding it?",
        options: [
          { key: "consistent_actions", label: "Consistent actions over time", dimensionContributions: { trust: 2, security: 1 } },
          { key: "honest_conversation_rebuild", label: "One honest, direct conversation", dimensionContributions: { communication: 2, emotional_openness: 1 } },
          { key: "time_and_distance", label: "Time and some distance first", dimensionContributions: { independence: 2 } },
          { key: "not_sure_itd_rebuild", label: "I'm not sure it would fully rebuild", dimensionContributions: { trust: -2 } },
        ],
      },
      {
        key: "checking_in_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you actively check in on how a relationship is going, rather than assuming it's fine?",
        scaleMax: 5,
        scaleDimension: "communication",
      },
      {
        key: "conflict_after_effects",
        type: "single_select",
        isCore: false,
        prompt: "After a conflict resolves, how do you usually feel about the relationship?",
        options: [
          { key: "stronger", label: "Stronger, honestly", dimensionContributions: { conflict: 2, connection: 1 } },
          { key: "relieved_but_wary", label: "Relieved, but a little wary", dimensionContributions: { security: -1 } },
          { key: "same_as_before", label: "About the same as before", dimensionContributions: { security: 1 } },
          { key: "avoid_thinking_about_it", label: "I try not to think about it too much", dimensionContributions: { emotional_openness: -2 } },
        ],
      },
      {
        key: "independence_partner_response",
        type: "single_select",
        isCore: false,
        prompt: "How do you feel when a partner needs a lot of independent time?",
        options: [
          { key: "respect_it", label: "I respect it, without reading into it", dimensionContributions: { independence: 1, trust: 1 } },
          { key: "take_it_personally", label: "I sometimes take it personally", dimensionContributions: { security: -2, expectations: 1 } },
          { key: "match_it", label: "I match it with my own independent time", dimensionContributions: { independence: 2 } },
          { key: "depends_on_context", label: "It depends on the context", dimensionContributions: {} },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "withdraw_signal",
      trigger: { questionKey: "conflict_response", op: "answered_option", optionKey: "withdraw" },
      action: { type: "ask_followup", followupQuestionKey: "withdraw_deep_dive" },
      priority: 8,
    },
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "long_term_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "makes_it_last_dynamic_followup",
      trigger: { questionKey: "what_makes_it_last", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "high_expectations_signal",
      trigger: { questionKey: "expectations_scale", dimensionKey: "expectations", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "expectations_origin" },
      priority: 5,
    },
    {
      key: "low_trust_signal",
      trigger: { questionKey: "trust_pace", op: "answered_option", optionKey: "rarely_fully" },
      action: { type: "ask_followup", followupQuestionKey: "trust_rebuilding" },
      priority: 5,
    },
    {
      key: "power_imbalance_signal",
      trigger: { questionKey: "power_balance", op: "answered_option", optionKey: "holds_more" },
      action: { type: "ask_followup", followupQuestionKey: "independence_partner_response" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "secure_connector",
      name: "The Secure Connector",
      descriptionTemplate:
        "Your responses suggest relationships settle for you into something steady rather than something you have to manage. Security doesn't appear to depend heavily on reassurance — it seems to come from a fairly grounded sense that things are fine until proven otherwise.",
      matchingRule: {
        dimensionRanges: { security: [65, 100], connection: [60, 100] },
        optionalConditions: { expectations: [0, 55] },
      },
      priority: 5,
    },
    {
      key: "independent_partner",
      name: "The Independent Partner",
      descriptionTemplate:
        "Your responses suggest you hold onto a clear sense of self inside a relationship, keeping real parts of your life separate rather than fully merging. This doesn't appear to come at the cost of connection — it looks more like a condition for it to feel sustainable.",
      matchingRule: {
        dimensionRanges: { independence: [65, 100] },
        excludeConditions: { connection: [75, 100] },
      },
      priority: 4,
    },
    {
      key: "careful_investor",
      name: "The Careful Investor",
      descriptionTemplate:
        "Your responses suggest you extend trust slowly and hold relationships to a fairly clear standard before fully investing. Once that standard is met, though, your answers suggest the investment tends to be real and sustained, not half-hearted.",
      matchingRule: {
        dimensionRanges: { trust: [0, 50], expectations: [60, 100] },
        optionalConditions: { communication: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "intense_connector",
      name: "The Intense Connector",
      descriptionTemplate:
        "Your responses suggest you go into relationships wanting depth and holding a fairly specific picture of what that should look like. When reality doesn't match that picture, your answers suggest it registers as a real disappointment, not a minor adjustment.",
      matchingRule: {
        dimensionRanges: { connection: [70, 100], expectations: [65, 100] },
        optionalConditions: { emotional_openness: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "reassurance_seeker",
      name: "The Reassurance Seeker",
      descriptionTemplate:
        "Your responses suggest you invest fully in connection, but your sense of security appears to lean on how sure you feel about where things stand — more than on your own steadiness. Uncertainty about the relationship's status seems to cost you more than it might for others.",
      matchingRule: {
        dimensionRanges: { connection: [55, 100], security: [0, 50] },
        optionalConditions: { expectations: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "self_protector",
      name: "The Self-Protector",
      descriptionTemplate:
        "Your responses suggest a strong instinct to keep your footing to yourself inside a relationship, extending trust cautiously and keeping your own feelings close. Independence appears to function as insulation here — useful for staying steady, though possibly costly to how open the relationship can become.",
      matchingRule: {
        dimensionRanges: { independence: [60, 100], trust: [0, 45], emotional_openness: [0, 45] },
      },
      priority: 4,
    },
    {
      key: "observant_partner",
      name: "The Observant Partner",
      descriptionTemplate:
        "Your responses suggest you don't carry a fixed script for how a relationship should go — you appear to notice what's actually happening and respond to that, rather than measuring it against an ideal. This tends to make you unusually calm about the ordinary shifts a relationship goes through.",
      matchingRule: {
        dimensionRanges: { expectations: [0, 45], communication: [55, 100] },
        optionalConditions: { conflict: [0, 50] },
      },
      priority: 3,
    },
    {
      key: "balanced_partner",
      name: "The Balanced Partner",
      descriptionTemplate:
        "Your responses don't show a strong lean toward one extreme or another — connection and independence, trust and caution, appear fairly evenly held. That balance suggests real adaptability in how you show up across different relationships.",
      matchingRule: {
        dimensionRanges: { connection: [45, 70], independence: [35, 65] },
        optionalConditions: { security: [50, 100] },
      },
      priority: 0,
    },
  ],

  freeResultTemplate: {
    headline: "Your relationship pattern is:",
    insightIntro:
      "Your responses suggest a specific way you handle closeness, conflict, and expectations across relationships — one that likely repeats more than you've consciously noticed.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you do relationships.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Relationship Pattern:",
    shareTextTemplate: "I discovered my INNER Relationship Pattern: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "relationship.signature" },
    { key: "dominant_pattern", title: "Your Dominant Pattern", promptRef: "relationship.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "relationship.how_you_connect" },
    { key: "security_and_expectations", title: "What Security Means to You", promptRef: "relationship.security_and_expectations" },
    { key: "your_independence", title: "Your Independence", promptRef: "relationship.your_independence" },
    { key: "trust_in_relationships", title: "How You Extend Trust", promptRef: "relationship.trust_in_relationships" },
    { key: "communication_and_conflict", title: "Communication & Conflict", promptRef: "relationship.communication_and_conflict" },
    { key: "strengths", title: "Your Strengths", promptRef: "relationship.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "relationship.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "relationship.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "relationship.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "relationship.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "communication",
      condition: { dimensionRanges: { communication: [0, 50] } },
      weight: 1,
      bridgeCopy: "Your answers touched on how directly you communicate inside a relationship — want to see the fuller pattern behind that?",
    },
    {
      assessmentSlug: "love",
      condition: { dimensionRanges: { connection: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "Curious how this pattern shows up right from the beginning, not just once things settle in?",
    },
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { trust: [55, 100] } },
      weight: 0.6,
      bridgeCopy: "Your answers suggest trust comes fairly naturally to you — want to see how that extends into emotional intimacy?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
