import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "Your Hidden Self" — /hidden-self. Careful positioning: patterns someone
 * may not consciously notice, never a claim to reveal the subconscious
 * (docs/ARCHITECTURE.md §3, §4.1). Questions stay indirect and
 * everyday-scenario-based rather than obviously mapping to a dimension.
 */
export const hiddenSelfAssessment: AssessmentConfig = {
  slug: "hidden-self",
  name: "Your Hidden Self",
  category: "self",
  description: "A short, adaptive conversation about patterns you may not consciously notice in yourself.",
  hook: "Everyone has a guard. The interesting part is what's behind it.",
  targetAudience: "Adults curious about patterns in themselves they don't usually stop to examine.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "control", weight: 1 },
    { key: "independence", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "vulnerability", weight: 1 },
    { key: "connection", weight: 1 },
    { key: "risk", weight: 1 },
    { key: "recognition", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "flexibility", weight: 1 },
  ],

  scoringModel: { normalization: "min-max", aiInfluenceCap: 0.15 },

  tensionPairs: [
    {
      key: "independence_high_connection",
      label: "genuinely valuing independence while still quietly wanting to be deeply known by someone",
      dimensionA: "independence",
      thresholdA: 60,
      dimensionB: "connection",
      thresholdB: 55,
    },
    {
      key: "recognition_low_emotional_openness",
      label: "wanting to be recognized for what you do while rarely saying so out loud",
      dimensionA: "recognition",
      thresholdA: 60,
      dimensionB: "emotional_openness",
      thresholdB: 40,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "unexpected_plan_change",
        type: "single_select",
        isCore: true,
        prompt: "Your plans for the day change unexpectedly. What's your first reaction, honestly?",
        options: [
          { key: "go_with_it", label: "I go with it fairly easily", dimensionContributions: { flexibility: 2 } },
          { key: "quietly_annoyed_but_adapt", label: "Quietly annoyed, but I adapt", dimensionContributions: { flexibility: 1, control: 1 } },
          { key: "try_to_salvage_original_plan", label: "I try to salvage the original plan", dimensionContributions: { control: 2, flexibility: -1 } },
          { key: "feel_thrown_off_more_than_expected", label: "I feel more thrown off than I'd expect", dimensionContributions: { flexibility: -2, risk: -1 } },
        ],
      },
      {
        key: "recognition_scale",
        type: "scale",
        isCore: true,
        prompt: "How much does it matter to you that people notice when you've done something well?",
        scaleMax: 5,
        scaleDimension: "recognition",
      },
      {
        key: "solo_project_preference",
        type: "single_select",
        isCore: true,
        prompt: "Given a real choice, would you rather work through something difficult alone or with others?",
        options: [
          { key: "alone_project", label: "Alone", dimensionContributions: { independence: 2 } },
          { key: "with_others_project", label: "With others", dimensionContributions: { connection: 2, independence: -1 } },
          { key: "alone_first_then_share", label: "Alone first, then I bring others in", dimensionContributions: { independence: 1, vulnerability: -1 } },
          { key: "depends_on_the_thing", label: "It genuinely depends on the thing", dimensionContributions: {} },
        ],
      },
      {
        key: "new_opportunity_risk",
        type: "single_select",
        isCore: true,
        prompt: "An interesting but uncertain opportunity comes up out of nowhere. What's your instinct?",
        options: [
          { key: "take_it_opportunity", label: "Take it", dimensionContributions: { risk: 2 } },
          { key: "research_first_opportunity", label: "Research it thoroughly first", dimensionContributions: { risk: -1, control: 1 } },
          { key: "pass_on_it_opportunity", label: "Pass on it", dimensionContributions: { risk: -2 } },
          { key: "ask_others_opportunity", label: "Ask people I trust what they think", dimensionContributions: { connection: 1, validation: 1 } },
        ],
      },
      {
        key: "when_praised_reaction",
        type: "single_select",
        isCore: true,
        prompt: "When someone praises your work in front of others, how do you actually feel?",
        options: [
          { key: "genuinely_pleased", label: "Genuinely pleased", dimensionContributions: { recognition: 2, emotional_openness: 1 } },
          { key: "a_little_uncomfortable", label: "A little uncomfortable", dimensionContributions: { recognition: -1 } },
          { key: "like_it_confirms_something", label: "Like it confirms something I needed to hear", dimensionContributions: { recognition: 2, validation: 1 } },
          { key: "mostly_indifferent", label: "Mostly indifferent, honestly", dimensionContributions: { recognition: -2 } },
        ],
      },
      {
        key: "connection_need_scale",
        type: "scale",
        isCore: true,
        prompt: "How much do you need at least one person in your life who really understands you?",
        scaleMax: 5,
        scaleDimension: "connection",
      },
      {
        key: "difficult_emotion_handling",
        type: "single_select",
        isCore: true,
        prompt: "When you feel something genuinely difficult, what do you tend to do with it?",
        options: [
          { key: "talk_about_it_hidden", label: "Talk about it with someone", dimensionContributions: { emotional_openness: 2 } },
          { key: "think_it_through_alone_hidden", label: "Think it through on my own first", dimensionContributions: { vulnerability: 1, emotional_openness: -1 } },
          { key: "push_it_aside_hidden", label: "Push it aside and keep moving", dimensionContributions: { emotional_openness: -2, control: 1 } },
          { key: "shows_without_choosing_hidden", label: "It shows without me really choosing to show it", dimensionContributions: { emotional_openness: 1, control: -1 } },
        ],
      },
      {
        key: "control_scale_hidden",
        type: "scale",
        isCore: true,
        prompt: "How much do you like having a say in how things get done, even in small situations?",
        scaleMax: 5,
        scaleDimension: "control",
      },
      {
        key: "unfamiliar_situation_response",
        type: "single_select",
        isCore: true,
        prompt: "You're placed in a completely unfamiliar situation with no instructions. What actually happens?",
        options: [
          { key: "figure_it_out_as_i_go", label: "I figure it out as I go", dimensionContributions: { flexibility: 2, risk: 1 } },
          { key: "look_for_structure", label: "I look for any available structure or rules", dimensionContributions: { control: 2, flexibility: -1 } },
          { key: "flicker_of_anxiety_first", label: "I feel a flicker of anxiety before anything else", dimensionContributions: { risk: -2 } },
          { key: "watch_others_first", label: "I watch what others do before acting", dimensionContributions: { connection: -1, control: 1 } },
        ],
      },
      {
        key: "praise_vs_understanding",
        type: "single_select",
        isCore: true,
        prompt: "Which ultimately matters more to you — being praised, or being understood?",
        options: [
          { key: "being_understood", label: "Being understood", dimensionContributions: { connection: 2, recognition: -1 } },
          { key: "being_praised", label: "Being praised", dimensionContributions: { recognition: 2 } },
          { key: "both_equally", label: "Both, about equally", dimensionContributions: {} },
          { key: "neither_much", label: "Honestly, neither much", dimensionContributions: { independence: 1 } },
        ],
      },
      {
        key: "vulnerability_scale_hidden",
        type: "scale",
        isCore: true,
        prompt: "How much of your inner world do the people who know you best actually get to see?",
        scaleMax: 5,
        scaleDimension: "vulnerability",
      },
      {
        key: "achievement_motivation",
        type: "single_select",
        isCore: true,
        prompt: "What motivates you most when you're working toward something genuinely hard?",
        options: [
          { key: "proving_something_to_myself", label: "Proving something to myself", dimensionContributions: { independence: 1, control: 1 } },
          { key: "wanting_others_to_notice", label: "Wanting others to notice", dimensionContributions: { recognition: 2 } },
          { key: "genuine_curiosity_in_the_work", label: "Genuine curiosity about the work itself", dimensionContributions: { risk: 1, flexibility: 1 } },
          { key: "not_disappointing_someone", label: "Not wanting to disappoint someone", dimensionContributions: { validation: 2, connection: 1 } },
        ],
      },
      {
        key: "routine_vs_change",
        type: "single_select",
        isCore: true,
        prompt: "Over a long stretch of time, do you gravitate toward routine or toward change?",
        options: [
          { key: "routine_gravitate", label: "Routine", dimensionContributions: { flexibility: -2, control: 1 } },
          { key: "change_gravitate", label: "Change", dimensionContributions: { flexibility: 2, risk: 1 } },
          { key: "routine_with_occasional_change", label: "Routine, with occasional change", dimensionContributions: {} },
          { key: "depends_on_area_of_life", label: "Depends entirely on the area of life", dimensionContributions: {} },
        ],
      },
      {
        key: "being_wrong_reaction",
        type: "single_select",
        isCore: true,
        prompt: "When you're proven wrong about something you were confident about, what happens internally?",
        options: [
          { key: "i_adjust_pretty_easily", label: "I adjust fairly easily", dimensionContributions: { flexibility: 2, emotional_openness: 1 } },
          { key: "it_stings_more_than_id_like", label: "It stings more than I'd like to admit", dimensionContributions: { validation: 1, control: 1 } },
          { key: "i_defend_my_original_position", label: "I find myself defending my original position", dimensionContributions: { control: 2, flexibility: -2 } },
          { key: "i_go_quiet_about_it", label: "I go quiet about it", dimensionContributions: { emotional_openness: -2, vulnerability: -1 } },
        ],
      },
      {
        key: "hidden_self_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe something about yourself that most people who know you wouldn't guess.",
        dynamicFollowupCandidates: ["hidden_self_why_hidden", "hidden_self_would_share"],
      },
      {
        key: "pattern_open_text",
        type: "open_text",
        isCore: true,
        prompt: "Describe a decision you made that surprised even you.",
        dynamicFollowupCandidates: ["surprise_decision_cause", "surprise_decision_frequency"],
      },
    ],
    adaptivePool: [
      {
        key: "hidden_self_why_hidden",
        type: "single_select",
        isCore: false,
        prompt: "Why do you think that tends to stay mostly hidden?",
        options: [
          { key: "doesnt_come_up_naturally", label: "It just doesn't come up naturally", dimensionContributions: {} },
          { key: "id_rather_keep_it_private", label: "I'd rather keep it private", dimensionContributions: { vulnerability: -1, control: 1 } },
          { key: "worried_how_itd_be_received", label: "I'm not sure how it'd be received", dimensionContributions: { validation: 1, vulnerability: -1 } },
          { key: "never_really_thought_about_it", label: "I've never really thought about why", dimensionContributions: {} },
        ],
      },
      {
        key: "hidden_self_would_share",
        type: "single_select",
        isCore: false,
        prompt: "Would you ever tell the right person, given the chance?",
        options: [
          { key: "yes_with_the_right_person", label: "Yes, with the right person", dimensionContributions: { connection: 1, vulnerability: 1 } },
          { key: "only_if_it_came_up_naturally", label: "Only if it came up naturally", dimensionContributions: {} },
          { key: "probably_not_hidden", label: "Probably not", dimensionContributions: { independence: 1 } },
          { key: "not_sure_would_share", label: "I'm not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "surprise_decision_cause",
        type: "single_select",
        isCore: false,
        prompt: "What do you think actually drove that decision?",
        options: [
          { key: "felt_right_in_the_moment", label: "It just felt right in the moment", dimensionContributions: { risk: 1, flexibility: 1 } },
          { key: "done_overthinking_it", label: "I was done overthinking it", dimensionContributions: { control: -1, risk: 1 } },
          { key: "someone_else_influenced_it", label: "Someone else's perspective influenced me", dimensionContributions: { connection: 1, validation: 1 } },
          { key: "not_sure_what_caused_it", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "surprise_decision_frequency",
        type: "single_select",
        isCore: false,
        prompt: "Does that kind of out-of-character decision happen more than people would guess?",
        options: [
          { key: "happens_more_than_expected", label: "More than people would guess", dimensionContributions: { flexibility: 1, risk: 1 } },
          { key: "that_was_rare_for_me", label: "That was rare for me", dimensionContributions: { control: 1 } },
          { key: "only_in_certain_areas", label: "Only in certain areas of my life", dimensionContributions: {} },
          { key: "never_really_tracked_it", label: "I've never really tracked it", dimensionContributions: {} },
        ],
      },
      {
        key: "plan_change_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What's underneath feeling thrown off by a change like that?",
        options: [
          { key: "i_like_knowing_whats_coming", label: "I like knowing what's coming", dimensionContributions: { control: 1, risk: -1 } },
          { key: "it_disrupts_something_relied_on", label: "It disrupts something I was quietly relying on", dimensionContributions: { flexibility: -1 } },
          { key: "dont_love_surprises_generally", label: "I don't love surprises generally", dimensionContributions: { risk: -2 } },
          { key: "not_sure_thrown_off", label: "I'm not sure, exactly", dimensionContributions: {} },
        ],
      },
      {
        key: "figure_it_out_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What makes stepping into the unknown feel okay for you?",
        options: [
          { key: "trust_myself_to_adapt", label: "I trust myself to adapt", dimensionContributions: { independence: 1, flexibility: 1 } },
          { key: "genuinely_exciting", label: "I find it genuinely exciting", dimensionContributions: { risk: 2 } },
          { key: "dont_see_another_option", label: "Honestly, I don't see another option", dimensionContributions: { control: -1 } },
          { key: "not_sure_makes_it_okay", label: "I'm not sure what makes it okay", dimensionContributions: {} },
        ],
      },
      {
        key: "defend_position_deep_dive",
        type: "single_select",
        isCore: false,
        prompt: "What does being wrong actually feel like, underneath the defending?",
        options: [
          { key: "loss_of_credibility", label: "Like a small loss of credibility", dimensionContributions: { recognition: 1, validation: 1 } },
          { key: "uncomfortable_but_manageable", label: "Uncomfortable, but manageable", dimensionContributions: {} },
          { key: "genuinely_destabilizing", label: "Genuinely destabilizing, if I'm honest", dimensionContributions: { control: 1, flexibility: -1 } },
          { key: "not_sure_feels_like", label: "I'm not sure how to describe it", dimensionContributions: {} },
        ],
      },
      {
        key: "recognition_replay_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you replay a compliment or piece of recognition in your mind afterward?",
        scaleMax: 5,
        scaleDimension: "recognition",
      },
      {
        key: "emotional_openness_private_scale",
        type: "scale",
        isCore: false,
        prompt: "Away from other people entirely, how emotionally expressive are you with yourself?",
        scaleMax: 5,
        scaleDimension: "emotional_openness",
      },
      {
        key: "independence_own_company_scale",
        type: "scale",
        isCore: false,
        prompt: "How much do you genuinely enjoy your own company, without it needing to lead anywhere?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
    ],
  },

  adaptiveRules: [
    {
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "hidden_self_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "pattern_open_text_dynamic_followup",
      trigger: { questionKey: "pattern_open_text", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "plan_change_signal",
      trigger: { questionKey: "unexpected_plan_change", op: "answered_option", optionKey: "feel_thrown_off_more_than_expected" },
      action: { type: "ask_followup", followupQuestionKey: "plan_change_deep_dive" },
      priority: 5,
    },
    {
      key: "figure_it_out_signal",
      trigger: { questionKey: "unfamiliar_situation_response", op: "answered_option", optionKey: "figure_it_out_as_i_go" },
      action: { type: "ask_followup", followupQuestionKey: "figure_it_out_deep_dive" },
      priority: 5,
    },
    {
      key: "defend_signal",
      trigger: { questionKey: "being_wrong_reaction", op: "answered_option", optionKey: "i_defend_my_original_position" },
      action: { type: "ask_followup", followupQuestionKey: "defend_position_deep_dive" },
      priority: 5,
    },
    {
      key: "high_recognition_signal",
      trigger: { questionKey: "recognition_scale", dimensionKey: "recognition", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "recognition_replay_scale" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "controlled_explorer",
      name: "The Controlled Explorer",
      descriptionTemplate:
        "Your responses suggest you're genuinely drawn to new and uncertain situations, but you tend to approach them on your own terms — exploring the unfamiliar while still keeping a real hand on the wheel.",
      matchingRule: {
        dimensionRanges: { control: [60, 100], risk: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "independent_seeker",
      name: "The Independent Seeker",
      descriptionTemplate:
        "Your responses suggest a strong pull toward independence sitting right alongside a real, quieter wish to be deeply known by someone. These two aren't in open conflict for you, but they do appear to shape each other constantly.",
      matchingRule: {
        dimensionRanges: { independence: [65, 100], connection: [50, 100] },
      },
      priority: 5,
    },
    {
      key: "quiet_achiever",
      name: "The Quiet Achiever",
      descriptionTemplate:
        "Your responses suggest recognition genuinely matters to you, even though you rarely say so out loud. You appear to do the work and hope it's noticed, rather than asking directly for it to be.",
      matchingRule: {
        dimensionRanges: { recognition: [60, 100], emotional_openness: [0, 50] },
      },
      priority: 4,
    },
    {
      key: "deep_processor",
      name: "The Deep Processor",
      descriptionTemplate:
        "Your responses suggest you feel things with real depth internally, but you tend to prefer stability and familiar ground over constant change. Processing appears to happen slowly and privately, on your own schedule.",
      matchingRule: {
        dimensionRanges: { vulnerability: [55, 100], flexibility: [0, 45] },
      },
      priority: 4,
    },
    {
      key: "connection_seeker_hidden",
      name: "The Connection Seeker",
      descriptionTemplate:
        "Your responses suggest connection and a need for reassurance tend to move together for you — being understood by someone appears to matter more than almost anything else, and its absence tends to be felt clearly.",
      matchingRule: {
        dimensionRanges: { connection: [65, 100], validation: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "self_protector",
      name: "The Self-Protector",
      descriptionTemplate:
        "Your responses suggest a strong instinct to keep your inner world to yourself, valuing both control and independence as a way of staying steady. This pattern tends to serve you well — the cost may be how much others get to actually see.",
      matchingRule: {
        dimensionRanges: { vulnerability: [0, 40], control: [55, 100], independence: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "adaptive_self",
      name: "The Adaptive Self",
      descriptionTemplate:
        "Your responses suggest you move through change and uncertainty with real ease, adjusting quickly rather than resisting. Flexibility appears to be one of your more consistent, if under-noticed, traits.",
      matchingRule: {
        dimensionRanges: { flexibility: [65, 100], risk: [55, 100] },
      },
      priority: 4,
    },
    {
      key: "reflective_observer",
      name: "The Reflective Observer",
      descriptionTemplate:
        "Your responses suggest you adapt thoughtfully rather than boldly, preferring to understand a situation before acting on it. This pattern shows up quietly — you're less likely to be the one taking the visible risk, and more likely to be the one who sees it clearly first.",
      matchingRule: {
        dimensionRanges: { risk: [0, 45], flexibility: [55, 100] },
        excludeConditions: { recognition: [70, 100] },
      },
      priority: 3,
    },
  ],

  freeResultTemplate: {
    headline: "A pattern you may not have consciously noticed:",
    insightIntro:
      "Your responses suggest a specific pattern that quietly shapes your choices — worth noticing, not something to be judged.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns beneath the surface.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Hidden Self:",
    shareTextTemplate: "I discovered my INNER Hidden Self: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "hidden-self.signature" },
    { key: "dominant_pattern", title: "Your Strongest Hidden Pattern", promptRef: "hidden-self.dominant_pattern" },
    { key: "recurring_tension", title: "A Recurring Tension", promptRef: "hidden-self.recurring_tension" },
    { key: "what_you_may_overlook", title: "What You May Overlook", promptRef: "hidden-self.what_you_may_overlook" },
    { key: "how_it_shows_up", title: "How It Shows Up in Daily Choices", promptRef: "hidden-self.how_it_shows_up" },
    { key: "strengths", title: "Your Strengths", promptRef: "hidden-self.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "hidden-self.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Pattern", promptRef: "hidden-self.inner_tension" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "hidden-self.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "hidden-self.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "love",
      condition: { dimensionRanges: { connection: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "This pattern of independence and connection tends to shape relationships too — want to see how it shows up there?",
    },
    {
      assessmentSlug: "social",
      condition: { dimensionRanges: { recognition: [55, 100] } },
      weight: 0.8,
      bridgeCopy: "Curious whether this need for recognition matches how people actually experience you socially?",
    },
    {
      assessmentSlug: "decision",
      condition: { dimensionRanges: { risk: [0, 50] } },
      weight: 0.6,
      bridgeCopy: "This pattern often shapes how people make decisions under pressure — want to see your Decision DNA?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
