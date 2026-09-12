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

  return (
    <div className="feedback feedback-incorrect">
      <div>⚠ {feedback.hint}</div>
      {feedback.correct_answer != null && <div>The answer was {feedback.correct_answer}.</div>}
    </div>
  );
}
