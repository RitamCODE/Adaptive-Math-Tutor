import { BUG_TYPE_HINTS, GENERIC_WRONG_ANSWER_HINT } from "../constants";

export default function FeedbackBanner({ feedback, justAdvanced }) {
  if (feedback.correct) {
    return (
      <div className="feedback feedback-correct">
        <div>{feedback.reward_narrative || "Correct!"}</div>
        {justAdvanced && (
          <div>{feedback.mastery_narrative || "Skill mastered — on to the next one!"}</div>
        )}
        {justAdvanced && feedback.boss_battle_narrative && (
          <div>{feedback.boss_battle_narrative}</div>
        )}
      </div>
    );
  }

  const hint = feedback.bug_type
    ? BUG_TYPE_HINTS[feedback.bug_type] || GENERIC_WRONG_ANSWER_HINT
    : GENERIC_WRONG_ANSWER_HINT;

  return (
    <div className="feedback feedback-incorrect">
      Not quite — the answer was {feedback.correct_answer}. {hint}
    </div>
  );
}
