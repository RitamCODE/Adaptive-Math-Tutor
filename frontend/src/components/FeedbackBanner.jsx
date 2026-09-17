import { useEffect, useState } from "react";

// The mastery moment's three narrative lines each earn their own step rather
// than stacking as plain text — this order and theme is fixed regardless of
// which lines have actually arrived yet (reward/boss-battle may still be
// null while their LLM call is in flight; mastery always has a fallback).
const MASTERY_STEP = { key: "mastery", className: "feedback-step-mastery", icon: "🏆", label: "Skill mastered" };
const REWARD_STEP = { key: "reward", className: "feedback-step-reward", icon: "⚡", label: "How you did" };
const BOSS_STEP = { key: "boss", className: "feedback-step-boss", icon: "⚔️", label: "Up next" };

function buildSteps(feedback) {
  const steps = [
    { ...MASTERY_STEP, text: feedback.mastery_narrative || "Skill mastered — on to the next one!" },
  ];
  if (feedback.reward_narrative) {
    steps.push({ ...REWARD_STEP, text: feedback.reward_narrative });
  }
  if (feedback.boss_battle_narrative) {
    steps.push({ ...BOSS_STEP, text: feedback.boss_battle_narrative });
  }
  return steps;
}

export default function FeedbackBanner({ feedback, justAdvanced, onNext }) {
  const [stepIndex, setStepIndex] = useState(0);

  // Resets once per mastery moment (a fresh problem_id), not on every
  // narrative hot-swap into the same still-frozen problem.
  useEffect(() => {
    setStepIndex(0);
  }, [feedback.problem_id]);

  if (feedback.correct) {
    if (!justAdvanced) {
      return (
        <div className="feedback feedback-correct">
          <div>{feedback.praise ?? "Correct!"}</div>
        </div>
      );
    }

    const steps = buildSteps(feedback);
    const index = Math.min(stepIndex, steps.length - 1);
    const step = steps[index];
    const isLast = index === steps.length - 1;

    function handleNext() {
      if (isLast) {
        onNext();
      } else {
        setStepIndex(index + 1);
      }
    }

    return (
      <div key={step.key} className={`feedback feedback-step ${step.className}`}>
        <div className="feedback-step-header">
          <span className="feedback-step-icon" aria-hidden="true">
            {step.icon}
          </span>
          <span className="feedback-step-label">{step.label}</span>
        </div>
        <div className="feedback-step-text">{step.text}</div>
        <div className="feedback-step-footer">
          <div className="feedback-step-dots" aria-hidden="true">
            {steps.map((s, i) => (
              <span
                key={s.key}
                className={`feedback-step-dot${i === index ? " feedback-step-dot-active" : ""}`}
              />
            ))}
          </div>
          <button type="button" className="feedback-next-button" onClick={handleNext}>
            Next <span aria-hidden="true">→</span>
          </button>
        </div>
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
