import type { AssessmentConfig } from "@inner/assessment-engine";

/**
 * "How Do You Love?" — /love. The reference implementation every other
 * experience's config should follow. See docs/ARCHITECTURE.md §3.
 *
 * 10 dimensions, a 45-question bank (12 core + 33 adaptive-pool, including
 * 2 open_text), and enough adaptive rules + tension pairs that a real
 * session normally lands between minQuestions and recommendedQuestions,
 * only reaching further when the information-value engine (see
 * packages/assessment-engine/src/adaptiveRules.ts) genuinely finds more
 * worth asking.
 */
export const loveAssessment: AssessmentConfig = {
  slug: "love",
  name: "How Do You Love?",
  category: "relationships",
  description:
    "A short, adaptive conversation about how you connect, protect yourself, and show up when things get close.",
  hook: "There's a pattern in how you love — most people have never seen it written down.",
  targetAudience: "Adults curious about their own relationship patterns.",
  status: "published",
  version: 1,
  minQuestions: 12,
  recommendedQuestions: 15,
  maxQuestions: 18,

  dimensions: [
    { key: "connection", weight: 1 },
    { key: "independence", weight: 1 },
    { key: "trust", weight: 1 },
    { key: "vulnerability", weight: 1 },
    { key: "emotional_openness", weight: 1 },
    { key: "validation", weight: 1 },
    { key: "security", weight: 1 },
    { key: "conflict", weight: 1 },
    { key: "affection_expression", weight: 1 },
    { key: "distance_response", weight: 1 },
  ],

  scoringModel: {
    normalization: "min-max",
    aiInfluenceCap: 0.15,
  },

  tensionPairs: [
    {
      key: "connection_independence",
      label: "wanting real closeness and strongly protecting your independence",
      dimensionA: "connection",
      thresholdA: 65,
      dimensionB: "independence",
      thresholdB: 65,
    },
    {
      key: "trust_low_vulnerability",
      label: "trusting fairly easily while still keeping your guard up emotionally",
      dimensionA: "trust",
      thresholdA: 65,
      dimensionB: "vulnerability",
      thresholdB: 35,
      directionB: "lte",
    },
    {
      key: "openness_independence",
      label: "being emotionally open while still needing a lot of control over your own space",
      dimensionA: "emotional_openness",
      thresholdA: 65,
      dimensionB: "independence",
      thresholdB: 65,
    },
    {
      key: "independence_low_distance_tolerance",
      label: "valuing independence while having a low tolerance for someone else's distance",
      dimensionA: "independence",
      thresholdA: 65,
      dimensionB: "distance_response",
      thresholdB: 35,
      directionB: "lte",
    },
  ],

  questionBank: {
    core: [
      {
        key: "attraction_first_feeling",
        type: "single_select",
        isCore: true,
        prompt: "When you start becoming interested in someone, what feels most natural to you?",
        options: [
          { key: "want_more_time", label: "I want to spend more time with them", dimensionContributions: { connection: 2, affection_expression: 1 } },
          { key: "keep_routine", label: "I like them but maintain my normal routine", dimensionContributions: { independence: 2 } },
          { key: "observe_first", label: "I observe carefully before opening up", dimensionContributions: { vulnerability: -2, trust: -1 } },
          { key: "keep_private", label: "I tend to keep my feelings private", dimensionContributions: { emotional_openness: -2, affection_expression: -1 } },
        ],
      },
      {
        key: "closeness_definition",
        type: "single_select",
        isCore: true,
        prompt: "When you imagine being truly close to someone, what matters most?",
        options: [
          { key: "emotionally_safe", label: "Feeling emotionally safe", dimensionContributions: { security: 2 } },
          { key: "fully_myself", label: "Being fully myself without editing", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "wont_leave", label: "Knowing they won't leave", dimensionContributions: { trust: -1, validation: 1 } },
          { key: "own_space", label: "Having space to be independent too", dimensionContributions: { independence: 2 } },
        ],
      },
      {
        key: "closeness_reaction",
        type: "single_select",
        isCore: true,
        prompt: "How do you usually react when someone becomes emotionally distant?",
        options: [
          { key: "move_closer", label: "I try to reconnect", dimensionContributions: { connection: 2, distance_response: -2 } },
          { key: "give_space", label: "I give them space", dimensionContributions: { independence: 2, distance_response: 1 } },
          { key: "pretend_fine", label: "I pretend it doesn't bother me", dimensionContributions: { vulnerability: -2, distance_response: 2 } },
          { key: "become_uncertain", label: "I start wondering what changed", dimensionContributions: { security: -2, validation: 1 } },
        ],
      },
      {
        key: "independence_scale",
        type: "scale",
        isCore: true,
        prompt: "In a typical week, how much time completely to yourself do you need to feel like yourself?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
      {
        key: "trust_default",
        type: "single_select",
        isCore: true,
        prompt: "When someone new shows real interest in you, your first instinct is...",
        options: [
          { key: "lean_in", label: "I lean in with curiosity", dimensionContributions: { trust: 2 } },
          { key: "wait_observe", label: "I wait and observe before opening up", dimensionContributions: { trust: -1, vulnerability: -1 } },
          { key: "skeptical", label: "I look for reasons it might not be genuine", dimensionContributions: { trust: -2 } },
          { key: "flattered_cautious", label: "I feel flattered but cautious", dimensionContributions: { validation: 1, trust: -1 } },
        ],
      },
      {
        key: "vulnerability_default",
        type: "single_select",
        isCore: true,
        prompt: "When something is bothering you, how likely are you to tell the person involved?",
        options: [
          { key: "tell_directly", label: "Very likely — I'll bring it up myself", dimensionContributions: { vulnerability: 2, emotional_openness: 2 } },
          { key: "tell_if_asked", label: "Only if they ask", dimensionContributions: { vulnerability: 1 } },
          { key: "process_alone", label: "I'd rather work through it on my own first", dimensionContributions: { independence: 1, vulnerability: -1 } },
          { key: "rarely_tell", label: "Rarely — I keep most of it to myself", dimensionContributions: { vulnerability: -2, emotional_openness: -2 } },
        ],
      },
      {
        key: "affection_natural_style",
        type: "single_select",
        isCore: true,
        prompt: "How do you most naturally show someone you care?",
        options: [
          { key: "say_it", label: "I tell them directly", dimensionContributions: { affection_expression: 2, emotional_openness: 2 } },
          { key: "show_through_actions", label: "Through small, consistent actions", dimensionContributions: { affection_expression: 1, security: 1 } },
          { key: "quality_time", label: "By making time for them", dimensionContributions: { connection: 2, affection_expression: 1 } },
          { key: "dont_show_much", label: "Honestly, I don't show it much either way", dimensionContributions: { affection_expression: -2 } },
        ],
      },
      {
        key: "asking_for_needs",
        type: "single_select",
        isCore: true,
        prompt: "When you need something from someone close to you, you tend to...",
        options: [
          { key: "ask_directly", label: "Ask directly", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "hint_and_hope", label: "Hint and hope they notice", dimensionContributions: { validation: 2, emotional_openness: -1 } },
          { key: "handle_myself", label: "Handle it myself instead", dimensionContributions: { independence: 2, vulnerability: -1 } },
          { key: "avoid_asking", label: "Avoid bringing it up at all", dimensionContributions: { conflict: 1, emotional_openness: -2 } },
        ],
      },
      {
        key: "after_argument",
        type: "single_select",
        isCore: true,
        prompt: "After a disagreement with someone close to you, what do you usually want first?",
        options: [
          { key: "reconnect", label: "To reconnect quickly", dimensionContributions: { connection: 2, conflict: -1 } },
          { key: "time_apart", label: "Some time apart to process", dimensionContributions: { independence: 2, conflict: 1 } },
          { key: "reassurance", label: "Reassurance that we're okay", dimensionContributions: { validation: 2, security: 1 } },
          { key: "understand", label: "To understand exactly what went wrong", dimensionContributions: { trust: 1, emotional_openness: 1 } },
        ],
      },
      {
        key: "reassurance_need",
        type: "scale",
        isCore: true,
        prompt: "How often do you find yourself needing reassurance that someone still wants you around?",
        scaleMax: 5,
        scaleDimension: "validation",
      },
      {
        key: "new_relationship_pace",
        type: "single_select",
        isCore: true,
        prompt: "When something new starts moving quickly, you feel...",
        options: [
          { key: "excited", label: "Excited — I like where this is going", dimensionContributions: { connection: 1, security: -1 } },
          { key: "cautious", label: "Cautious — I'd rather slow down", dimensionContributions: { security: 2, trust: -1 } },
          { key: "excited_nervous", label: "Both excited and nervous", dimensionContributions: { validation: 1 } },
          { key: "red_flags", label: "I start looking for red flags", dimensionContributions: { trust: -2 } },
        ],
      },
      {
        key: "closeness_dependency",
        type: "open_text",
        isCore: true,
        prompt: "Describe a situation where you wanted to get closer to someone but decided to hold yourself back.",
        // Question AI may pick at most one of these — never a question outside this list (§4/§5).
        dynamicFollowupCandidates: ["what_would_help", "what_pattern_notice"],
      },
      {
        key: "uncertainty_response",
        type: "open_text",
        isCore: true,
        prompt: "When you feel emotionally uncertain about someone, what do you usually do?",
        dynamicFollowupCandidates: ["uncertainty_next_step", "uncertainty_familiar_pattern"],
      },
    ],
    adaptivePool: [
      // --- retained from the original branching set ---
      {
        key: "protect_what",
        type: "single_select",
        isCore: false,
        prompt: "When you start pulling away, what are you usually trying to protect?",
        options: [
          { key: "my_independence", label: "My independence", dimensionContributions: { independence: 2 } },
          { key: "my_emotions", label: "My emotions", dimensionContributions: { vulnerability: -1, security: -1 } },
          { key: "my_control", label: "My sense of control", dimensionContributions: { independence: 1 } },
          { key: "from_rejection", label: "Myself from rejection", dimensionContributions: { validation: 1, security: -2 } },
          { key: "not_sure", label: "I'm not sure", dimensionContributions: {} },
          { key: "something_else", label: "Something else", dimensionContributions: {} },
        ],
      },
      {
        key: "independence_after_connection",
        type: "single_select",
        isCore: false,
        prompt: "After a period of really close connection, what usually happens for you?",
        options: [
          { key: "want_more", label: "I want even more closeness", dimensionContributions: { connection: 2 } },
          { key: "need_space", label: "I start needing space", dimensionContributions: { independence: 2, distance_response: 1 } },
          { key: "steady", label: "I feel steady either way", dimensionContributions: { security: 2 } },
          { key: "worry", label: "I start worrying it won't last", dimensionContributions: { validation: 1, security: -1 } },
        ],
      },
      {
        key: "trust_when_hurt",
        type: "single_select",
        isCore: false,
        prompt: "If someone you trusted let you down, what would rebuild your trust fastest?",
        options: [
          { key: "consistency", label: "Consistent follow-through over time", dimensionContributions: { trust: 2, security: 1 } },
          { key: "honest_conversation", label: "An honest, vulnerable conversation", dimensionContributions: { vulnerability: 2, trust: 1 } },
          { key: "proof_actions", label: "Them proving it through actions, not words", dimensionContributions: { trust: 1, independence: 1 } },
          { key: "not_sure_trust", label: "I'm not sure I'd fully trust again", dimensionContributions: { trust: -2 } },
        ],
      },
      {
        key: "what_would_help",
        type: "single_select",
        isCore: false,
        prompt: "What do you think would help you stay close instead of pulling away?",
        options: [
          { key: "clear_reassurance", label: "Clear, low-pressure reassurance", dimensionContributions: { security: 2, validation: 1 } },
          { key: "naming_it", label: "Being able to name what I'm feeling out loud", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "slower_pace", label: "Simply moving at a slower pace", dimensionContributions: { independence: 1, security: 1 } },
          { key: "not_sure_help", label: "I'm honestly not sure", dimensionContributions: {} },
        ],
      },
      {
        key: "what_pattern_notice",
        type: "single_select",
        isCore: false,
        prompt: "Looking back, is this a pattern you recognize in other relationships too?",
        options: [
          { key: "yes_often", label: "Yes, it comes up often", dimensionContributions: { independence: 1, security: -1 } },
          { key: "yes_sometimes", label: "Sometimes, depending on the person", dimensionContributions: {} },
          { key: "no_specific", label: "No, this felt specific to that situation", dimensionContributions: { security: 1 } },
          { key: "never_noticed", label: "I've never really looked for a pattern", dimensionContributions: {} },
        ],
      },
      {
        key: "uncertainty_next_step",
        type: "single_select",
        isCore: false,
        prompt: "What would help most, the next time you feel this uncertain?",
        options: [
          { key: "clear_communication", label: "A clear, direct conversation", dimensionContributions: { vulnerability: 1, emotional_openness: 1 } },
          { key: "time_alone", label: "Time alone to think it through", dimensionContributions: { independence: 2 } },
          { key: "reassurance_from_other", label: "Reassurance from the other person", dimensionContributions: { validation: 2 } },
          { key: "wait_it_out", label: "Nothing — I'd rather just wait it out", dimensionContributions: { security: 1, independence: 1 } },
        ],
      },
      {
        key: "uncertainty_familiar_pattern",
        type: "single_select",
        isCore: false,
        prompt: "Does this feeling come up with most people you get close to, or just some?",
        options: [
          { key: "most_people", label: "Most people", dimensionContributions: { independence: 1, security: -1 } },
          { key: "certain_situations", label: "Only in certain situations", dimensionContributions: {} },
          { key: "unusual", label: "Rarely — this was unusual for me", dimensionContributions: { security: 1 } },
          { key: "never_thought_about", label: "I've never really thought about it", dimensionContributions: {} },
        ],
      },
      // --- attraction ---
      {
        key: "attraction_first_pull",
        type: "single_select",
        isCore: false,
        prompt: "What draws you in first when you're getting to know someone?",
        options: [
          { key: "emotional_depth", label: "Emotional depth", dimensionContributions: { vulnerability: 2, emotional_openness: 1 } },
          { key: "consistency", label: "Consistency", dimensionContributions: { security: 2 } },
          { key: "chemistry", label: "Chemistry and excitement", dimensionContributions: { connection: 1, security: -1 } },
          { key: "mystery", label: "A bit of mystery I want to figure out", dimensionContributions: { independence: 1, trust: -1 } },
        ],
      },
      {
        key: "attraction_move_first",
        type: "single_select",
        isCore: false,
        prompt: "Early on, do you tend to move toward someone or wait for them to move toward you?",
        options: [
          { key: "move_first", label: "I move first", dimensionContributions: { connection: 2, emotional_openness: 1 } },
          { key: "wait_and_see", label: "I wait and see", dimensionContributions: { independence: 1, trust: -1 } },
          { key: "depends_person", label: "Depends entirely on the person", dimensionContributions: {} },
          { key: "hold_back_until_sure", label: "I hold back until I'm sure", dimensionContributions: { vulnerability: -2, security: 1 } },
        ],
      },
      // --- closeness ---
      {
        key: "closeness_daily_feel",
        type: "single_select",
        isCore: false,
        prompt: "What does \"being close\" to someone actually feel like for you, day to day?",
        options: [
          { key: "easy_togetherness", label: "Easy, low-effort togetherness", dimensionContributions: { connection: 2, security: 1 } },
          { key: "deep_sharing", label: "Deep, intense emotional sharing", dimensionContributions: { vulnerability: 2, emotional_openness: 2 } },
          { key: "own_life", label: "Knowing I still have my own life", dimensionContributions: { independence: 2 } },
          { key: "knowing_where_i_stand", label: "Knowing exactly where I stand", dimensionContributions: { validation: 1, security: 1 } },
        ],
      },
      {
        key: "closeness_daily_details",
        type: "scale",
        isCore: false,
        prompt: "How much do you like knowing the small details of your partner's day?",
        scaleMax: 5,
        scaleDimension: "connection",
      },
      // --- emotional distance ---
      {
        key: "distance_slow_reply",
        type: "single_select",
        isCore: false,
        prompt: "If someone you're close to suddenly takes longer to reply than usual, what's your gut read?",
        options: [
          { key: "no_big_deal", label: "They're busy — no big deal", dimensionContributions: { security: 2, distance_response: -1 } },
          { key: "replaying_conversation", label: "I start replaying our last conversation", dimensionContributions: { validation: 1, security: -2 } },
          { key: "match_their_space", label: "I give them the same amount of space back", dimensionContributions: { independence: 2, distance_response: 2 } },
          { key: "reach_out", label: "I reach out to check in", dimensionContributions: { connection: 2, distance_response: -2 } },
        ],
      },
      {
        key: "distance_first_move",
        type: "single_select",
        isCore: false,
        prompt: "When you sense distance growing between you and someone, what do you do first?",
        options: [
          { key: "name_it", label: "Name it directly", dimensionContributions: { vulnerability: 2, emotional_openness: 2, distance_response: -2 } },
          { key: "match_distance", label: "Quietly match their distance", dimensionContributions: { independence: 1, distance_response: 2 } },
          { key: "get_busy", label: "Get busy with other things", dimensionContributions: { distance_response: 2, independence: 1 } },
          { key: "wait_for_them", label: "Wait for them to come back around", dimensionContributions: { validation: 1, distance_response: 1 } },
        ],
      },
      // --- independence ---
      {
        key: "independence_partner_time",
        type: "single_select",
        isCore: false,
        prompt: "How do you feel about a partner who wants to spend most of their free time with you?",
        options: [
          { key: "comforting", label: "Comforting", dimensionContributions: { connection: 2, independence: -1 } },
          { key: "suffocating", label: "A bit suffocating", dimensionContributions: { independence: 3, connection: -2 } },
          { key: "depends_day", label: "Depends on the day", dimensionContributions: {} },
          { key: "fine_with_own_time", label: "Fine, as long as I still get my own time", dimensionContributions: { independence: 1, connection: 1 } },
        ],
      },
      {
        key: "independence_big_decisions",
        type: "single_select",
        isCore: false,
        prompt: "Do you tend to make big life decisions with a partner, or on your own first?",
        options: [
          { key: "together_start", label: "Together, from the start", dimensionContributions: { connection: 2, independence: -1 } },
          { key: "decide_then_loop_in", label: "I decide, then loop them in", dimensionContributions: { independence: 2 } },
          { key: "fully_together", label: "Fully together, always", dimensionContributions: { connection: 2, independence: -2 } },
          { key: "settle_before_discussing", label: "I don't like discussing big decisions until they're settled", dimensionContributions: { independence: 3, vulnerability: -1 } },
        ],
      },
      // --- trust ---
      {
        key: "trust_how_earned",
        type: "single_select",
        isCore: false,
        prompt: "How do you typically decide if you can trust someone?",
        options: [
          { key: "time_and_consistency", label: "Time and consistency", dimensionContributions: { trust: 1, security: 1 } },
          { key: "decide_quickly", label: "Pretty quickly, then I look for reasons to change my mind", dimensionContributions: { trust: -1 } },
          { key: "ask_directly", label: "I ask directly", dimensionContributions: { vulnerability: 1, trust: 1 } },
          { key: "watch_others", label: "I watch how they treat other people", dimensionContributions: { trust: 1 } },
        ],
      },
      // --- vulnerability ---
      {
        key: "vulnerability_crying_comfort",
        type: "scale",
        isCore: false,
        prompt: "How comfortable are you letting someone you're dating see you cry?",
        scaleMax: 5,
        scaleDimension: "vulnerability",
      },
      {
        key: "vulnerability_struggle_instinct",
        type: "single_select",
        isCore: false,
        prompt: "When you're struggling, what's more true for you?",
        options: [
          { key: "want_them_to_notice", label: "I want someone to notice without me having to say it", dimensionContributions: { validation: 2, vulnerability: -1 } },
          { key: "tell_if_asked_struggle", label: "I'll tell them directly if asked", dimensionContributions: { vulnerability: 1 } },
          { key: "process_alone_struggle", label: "I keep it to myself until I've processed it alone", dimensionContributions: { independence: 2, vulnerability: -2 } },
          { key: "bring_up_myself", label: "I bring it up myself, unprompted", dimensionContributions: { vulnerability: 2, emotional_openness: 2 } },
        ],
      },
      // --- affection ---
      {
        key: "affection_words_or_actions",
        type: "single_select",
        isCore: false,
        prompt: "Which feels more like \"you\" — saying how you feel, or showing it through actions?",
        options: [
          { key: "saying_it", label: "Saying it", dimensionContributions: { emotional_openness: 2, affection_expression: 2 } },
          { key: "showing_actions", label: "Showing it through what I do", dimensionContributions: { affection_expression: 1, emotional_openness: -1 } },
          { key: "both_moments", label: "Both, depending on the moment", dimensionContributions: { affection_expression: 1 } },
          { key: "neither_natural", label: "Neither comes naturally to me", dimensionContributions: { affection_expression: -2, vulnerability: -1 } },
        ],
      },
      {
        key: "affection_say_first",
        type: "single_select",
        isCore: false,
        prompt: "How do you feel about being the one to say \"I care about you\" first?",
        options: [
          { key: "comfortable_saying", label: "Comfortable — I'll say it when I mean it", dimensionContributions: { affection_expression: 2, vulnerability: 1 } },
          { key: "rather_wait", label: "I'd rather wait for the other person", dimensionContributions: { affection_expression: -2, security: -1 } },
          { key: "show_instead", label: "I show it instead of saying it", dimensionContributions: { affection_expression: 1, emotional_openness: -1 } },
          { key: "makes_nervous", label: "It makes me nervous either way", dimensionContributions: { affection_expression: -2, vulnerability: -1 } },
        ],
      },
      // --- communication ---
      {
        key: "communication_upset_instinct",
        type: "single_select",
        isCore: false,
        prompt: "When you're upset with someone, what's closest to your instinct?",
        options: [
          { key: "say_something_soon", label: "Say something as soon as I notice", dimensionContributions: { emotional_openness: 2, conflict: -1 } },
          { key: "cool_down_first", label: "Wait until I've cooled down", dimensionContributions: { conflict: 1 } },
          { key: "hope_they_notice", label: "Hope they notice without me saying anything", dimensionContributions: { validation: 2, emotional_openness: -2 } },
          { key: "avoid_it", label: "Avoid bringing it up at all", dimensionContributions: { conflict: 2, emotional_openness: -2 } },
        ],
      },
      {
        key: "communication_needs_clarity",
        type: "scale",
        isCore: false,
        prompt: "How clearly do you usually say what you need in a relationship?",
        scaleMax: 5,
        scaleDimension: "emotional_openness",
      },
      // --- conflict ---
      {
        key: "conflict_disagreement_style",
        type: "single_select",
        isCore: false,
        prompt: "During an actual disagreement, what's closest to how you show up?",
        options: [
          { key: "resolve_right_away", label: "I want to resolve it right away", dimensionContributions: { conflict: -1, connection: 1 } },
          { key: "need_space_first", label: "I need space before I can talk about it", dimensionContributions: { conflict: 2, independence: 1 } },
          { key: "get_quiet", label: "I get quiet and pull back", dimensionContributions: { conflict: 2, distance_response: 2 } },
          { key: "say_plainly", label: "I say what I think plainly, even if it's tense", dimensionContributions: { conflict: -2, emotional_openness: 2 } },
        ],
      },
      {
        key: "conflict_small_things",
        type: "single_select",
        isCore: false,
        prompt: "How do you feel about raising something small that's bothering you, before it builds up?",
        options: [
          { key: "say_it_early", label: "I'd rather say it early", dimensionContributions: { conflict: -2, emotional_openness: 1 } },
          { key: "let_it_go", label: "I let small things go, most of the time", dimensionContributions: { conflict: 1 } },
          { key: "only_when_bigger", label: "I only bring things up once they're a bigger deal", dimensionContributions: { conflict: 2 } },
          { key: "mental_list", label: "I keep a mental list and rarely say anything", dimensionContributions: { conflict: 3, vulnerability: -1 } },
        ],
      },
      // --- reassurance ---
      {
        key: "reassurance_forgot_checkin",
        type: "single_select",
        isCore: false,
        prompt: "If a partner forgot to tell you they'd arrived somewhere safely, how would you feel?",
        options: [
          { key: "wouldnt_think_twice", label: "I wouldn't think twice", dimensionContributions: { validation: -1, security: 2 } },
          { key: "little_anxious", label: "A little anxious until I heard from them", dimensionContributions: { validation: 2 } },
          { key: "bother_rest_of_day", label: "It would bother me for the rest of the day", dimensionContributions: { validation: 3, security: -1 } },
          { key: "wish_but_quiet", label: "I'd rather they remembered, but I wouldn't say anything", dimensionContributions: { validation: 2, emotional_openness: -1 } },
        ],
      },
      {
        key: "reassurance_compliments_impact",
        type: "scale",
        isCore: false,
        prompt: "How much do compliments and reassurance from a partner actually change how you feel?",
        scaleMax: 5,
        scaleDimension: "validation",
      },
      // --- uncertainty ---
      {
        key: "uncertainty_where_i_stand",
        type: "single_select",
        isCore: false,
        prompt: "When you don't know where you stand with someone, what do you do?",
        options: [
          { key: "ask_directly_stand", label: "Ask directly", dimensionContributions: { vulnerability: 2, security: 1 } },
          { key: "wait_clear_own", label: "Wait for it to become clear on its own", dimensionContributions: { independence: 1 } },
          { key: "assume_worst", label: "Assume the worst until proven otherwise", dimensionContributions: { validation: 1, security: -2 } },
          { key: "doesnt_bother", label: "It doesn't bother me much either way", dimensionContributions: { security: 2, independence: 1 } },
        ],
      },
      {
        key: "uncertainty_others_feelings",
        type: "single_select",
        isCore: false,
        prompt: "How do you handle not knowing what someone else is feeling?",
        options: [
          { key: "i_ask", label: "I ask", dimensionContributions: { emotional_openness: 2 } },
          { key: "read_between_lines", label: "I read between the lines", dimensionContributions: { trust: -1 } },
          { key: "assume_theyd_tell", label: "I assume they'd tell me if it mattered", dimensionContributions: { trust: 2 } },
          { key: "uneasy_until_known", label: "It makes me uneasy until I know", dimensionContributions: { security: -2, validation: 1 } },
        ],
      },
      // --- commitment ---
      {
        key: "commitment_big_words",
        type: "single_select",
        isCore: false,
        prompt: "How do you feel about using words like \"always\" or \"forever\" early in a relationship?",
        options: [
          { key: "exciting_certainty", label: "Exciting — I like that kind of certainty", dimensionContributions: { validation: 2, security: -1 } },
          { key: "too_soon", label: "Too soon — I'd rather see it play out", dimensionContributions: { independence: 1, trust: -1 } },
          { key: "comforting_if_genuine", label: "Comforting, if it's genuine", dimensionContributions: { security: 2 } },
          { key: "want_to_slow_down", label: "It makes me want to slow down", dimensionContributions: { independence: 2, trust: -1 } },
        ],
      },
      {
        key: "commitment_safety",
        type: "single_select",
        isCore: false,
        prompt: "What makes commitment feel safe to you, rather than restrictive?",
        options: [
          { key: "independence_within_it", label: "Still having independence within it", dimensionContributions: { independence: 2, security: 1 } },
          { key: "consistent_effort", label: "Consistent effort over time", dimensionContributions: { trust: 2, security: 1 } },
          { key: "honesty_about_anything", label: "Knowing we can be honest about anything", dimensionContributions: { vulnerability: 2, trust: 1 } },
          { key: "dont_overthink", label: "Not overthinking it — it either works or it doesn't", dimensionContributions: { security: 2, independence: 1 } },
        ],
      },
      // --- personal boundaries ---
      {
        key: "boundaries_saying_no",
        type: "scale",
        isCore: false,
        prompt: "How easy is it for you to say no to someone you're dating?",
        scaleMax: 5,
        scaleDimension: "independence",
      },
      {
        key: "boundaries_more_time_wanted",
        type: "single_select",
        isCore: false,
        prompt: "When a partner wants more time together than you're ready to give, what's your instinct?",
        options: [
          { key: "say_so_honestly", label: "Say so honestly, even if it's awkward", dimensionContributions: { independence: 2, emotional_openness: 2 } },
          { key: "give_in_for_now", label: "Give in for now to avoid the conversation", dimensionContributions: { independence: -2, conflict: 2 } },
          { key: "create_quiet_distance", label: "Quietly create distance instead of saying anything", dimensionContributions: { independence: 1, distance_response: 2 } },
          { key: "reassess_pace", label: "Reassess whether this is the right pace for me", dimensionContributions: { independence: 2, security: 1 } },
        ],
      },
    ],
  },

  adaptiveRules: [
    {
      key: "ambiguous_closeness_reaction",
      trigger: { questionKey: "closeness_reaction", op: "answered_option", optionKey: "become_uncertain" },
      action: { type: "ask_followup", followupQuestionKey: "protect_what" },
      priority: 10,
    },
    {
      // Question AI resolves this dynamically per-session (packages/ai) and bakes its
      // choice into the recorded answer before this rule ever runs — see §4/§5.
      key: "open_text_dynamic_followup",
      trigger: { questionKey: "closeness_dependency", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "uncertainty_dynamic_followup",
      trigger: { questionKey: "uncertainty_response", op: "has_ai_choice" },
      action: { type: "ask_ai_chosen_followup" },
      priority: 1,
    },
    {
      key: "strong_independence_signal",
      trigger: { questionKey: "independence_scale", dimensionKey: "independence", op: "gte", value: 75 },
      action: { type: "ask_followup", followupQuestionKey: "independence_after_connection" },
      priority: 5,
    },
    {
      key: "low_trust_signal",
      trigger: { questionKey: "trust_default", op: "answered_option", optionKey: "skeptical" },
      action: { type: "ask_followup", followupQuestionKey: "trust_when_hurt" },
      priority: 5,
    },
    {
      key: "avoids_conflict_entirely",
      trigger: { questionKey: "after_argument", op: "answered_option", optionKey: "time_apart" },
      action: { type: "ask_followup", followupQuestionKey: "conflict_disagreement_style" },
      priority: 4,
    },
    {
      key: "low_affection_expression",
      trigger: { questionKey: "affection_natural_style", op: "answered_option", optionKey: "dont_show_much" },
      action: { type: "ask_followup", followupQuestionKey: "affection_say_first" },
      priority: 4,
    },
  ],

  profiles: [
    {
      key: "independent_connector",
      name: "The Independent Connector",
      descriptionTemplate:
        "Your responses suggest you value deep connection while strongly protecting your independence. One pattern in your answers is a tendency to pull back right when things start to feel very close — often as a way of staying yourself inside the relationship, not a sign of losing interest.",
      matchingRule: {
        dimensionRanges: { connection: [60, 100], independence: [60, 100] },
        optionalConditions: { affection_expression: [55, 100] },
      },
      priority: 5,
    },
    {
      key: "deep_connector",
      name: "The Deep Connector",
      descriptionTemplate:
        "Your responses suggest you trust fairly readily and let people see the real, unedited version of you once you're in. Vulnerability doesn't seem to cost you much — if anything, it appears to be how you build closeness in the first place.",
      matchingRule: {
        dimensionRanges: { trust: [60, 100], vulnerability: [60, 100] },
        optionalConditions: { emotional_openness: [60, 100] },
        excludeConditions: { independence: [80, 100] },
      },
      priority: 4,
    },
    {
      key: "selective_heart",
      name: "The Selective Heart",
      descriptionTemplate:
        "Your responses suggest you open up gradually and watch for consistency before fully trusting. This appears less like guardedness for its own sake, and more like a pattern of protecting yourself until safety is well-established — once it is, connection still seems to matter a great deal to you.",
      matchingRule: {
        dimensionRanges: { trust: [0, 50], vulnerability: [0, 55] },
        optionalConditions: { connection: [55, 100] },
      },
      priority: 3,
    },
    {
      key: "secure_explorer",
      name: "The Secure Explorer",
      descriptionTemplate:
        "Your responses suggest a grounded, low-reactivity style paired with real emotional openness — a combination that tends to make new closeness feel more like curiosity than risk. You don't appear to need much reassurance to feel steady.",
      matchingRule: {
        dimensionRanges: { security: [65, 100], emotional_openness: [55, 100] },
        optionalConditions: { independence: [40, 70] },
        excludeConditions: { validation: [70, 100] },
      },
      priority: 4,
    },
    {
      key: "careful_observer",
      name: "The Careful Observer",
      descriptionTemplate:
        "Your responses suggest you watch and assess before you engage, especially when someone starts to pull back. Matching someone else's distance, rather than closing it, seems to be a more natural reflex for you than most.",
      matchingRule: {
        dimensionRanges: { vulnerability: [0, 45], distance_response: [55, 100] },
        optionalConditions: { independence: [55, 100] },
      },
      priority: 3,
    },
    {
      key: "reassurance_seeker",
      name: "The Reassurance Seeker",
      descriptionTemplate:
        "Your responses suggest you invest fully once connection is there, and you tend to look for consistent signs that it's returned. One pattern worth noticing: your sense of security may lean on how reassured you feel, more than on your own steadiness.",
      matchingRule: {
        dimensionRanges: { connection: [55, 100], validation: [60, 100] },
        optionalConditions: { security: [0, 50] },
      },
      priority: 5,
    },
    {
      key: "self_protector",
      name: "The Self-Protector",
      descriptionTemplate:
        "Your responses suggest a strong instinct to keep your emotional footing to yourself, especially early on. Independence appears to function as a kind of insulation — useful for staying steady, though it may sometimes read as more closed-off than intended.",
      matchingRule: {
        dimensionRanges: { independence: [65, 100], vulnerability: [0, 45] },
        optionalConditions: { distance_response: [55, 100] },
        excludeConditions: { connection: [70, 100] },
      },
      priority: 4,
    },
    {
      key: "balanced_connector",
      name: "The Balanced Connector",
      descriptionTemplate:
        "Your responses don't show a strong lean toward one extreme or another — you appear to hold connection and independence, openness and caution, in a fairly even balance. That balance itself is worth noticing: it suggests real flexibility in how you show up for different people and situations.",
      matchingRule: {
        dimensionRanges: { connection: [45, 75], independence: [35, 65] },
        optionalConditions: { security: [50, 100] },
      },
      priority: 0,
    },
  ],

  freeResultTemplate: {
    headline: "Your primary pattern is:",
    insightIntro:
      "Your responses suggest a specific way you balance closeness and self-protection — one that shapes how you show up early in relationships and how you react when things intensify.",
    lockedInsightsLabel: "Your answers also revealed 3 additional patterns in how you love.",
  },

  shareTemplate: {
    shareTitleTemplate: "I discovered my INNER Love Profile:",
    shareTextTemplate: "I discovered my INNER Love Profile: {{profileName}}. Discover yours.",
  },

  premiumReportStructure: [
    { key: "signature", title: "Your INNER Signature", promptRef: "love.signature" },
    { key: "dominant_pattern", title: "Your Dominant Love Pattern", promptRef: "love.dominant_pattern" },
    { key: "how_you_connect", title: "How You Connect", promptRef: "love.how_you_connect" },
    { key: "how_you_handle_closeness", title: "How You Handle Closeness", promptRef: "love.how_you_handle_closeness" },
    { key: "your_independence", title: "Your Independence", promptRef: "love.your_independence" },
    { key: "your_vulnerability", title: "Your Vulnerability", promptRef: "love.your_vulnerability" },
    { key: "trust_and_security", title: "Trust & Security", promptRef: "love.trust_and_security" },
    { key: "distance_response", title: "How You Respond to Distance", promptRef: "love.distance_response" },
    { key: "communication_in_connection", title: "Your Communication in Connection", promptRef: "love.communication_in_connection" },
    { key: "strengths", title: "Your Strengths", promptRef: "love.strengths" },
    { key: "friction_points", title: "Your Potential Friction Points", promptRef: "love.friction_points" },
    { key: "inner_tension", title: "The Tension Inside Your Profile", promptRef: "love.inner_tension" },
    { key: "misunderstood_aspects", title: "What Others May Sometimes Misunderstand About You", promptRef: "love.misunderstood_aspects" },
    { key: "reflection", title: "Your Personal Reflection", promptRef: "love.reflection" },
    { key: "final_note", title: "Final INNER Note", promptRef: "love.final_note" },
  ],

  recommendedNext: [
    {
      assessmentSlug: "intimacy",
      condition: { dimensionRanges: { independence: [55, 100], connection: [55, 100] } },
      weight: 1,
      bridgeCopy:
        "Your answers showed an interesting relationship between independence and connection. Would you like to explore how this pattern appears in intimacy?",
    },
    {
      assessmentSlug: "relationship",
      condition: { dimensionRanges: { security: [0, 50] } },
      weight: 0.8,
      bridgeCopy: "Curious how this pattern plays out over the life of a relationship, not just the beginning?",
    },
  ],

  pricing: {
    individual: { productType: "individual", amountCents: 799, currency: "EUR" },
    deep: { productType: "deep", amountCents: 1299, currency: "EUR" },
  },
};
