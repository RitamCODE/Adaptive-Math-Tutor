import { useState } from "react";
import NumberPad from "./NumberPad";
import FeedbackBanner from "./FeedbackBanner";

const CONFETTI_ANGLES = [
  { angle: -60, color: "coral" },
  { angle: -30, color: "gold" },
  { angle: 0, color: "teal" },
  { angle: 30, color: "coral" },
  { angle: 60, color: "gold" },
  { angle: 120, color: "teal" },
  { angle: 150, color: "coral" },
  { angle: 180, color: "gold" },
];

export default function ProblemCard({ problem, onSubmit, loading, flashState, feedback, justAdvanced }) {
  const [answer, setAnswer] = useState("");

  function handleSubmit() {
    if (answer.trim() === "") return;
    onSubmit(Number(answer));
    setAnswer("");
  }

  const feedbackForThisProblem = feedback && feedback.problem_id === problem.problem_id ? feedback : null;

  return (
    <div className={`problem-card${flashState ? ` problem-card-${flashState}` : ""}`}>
      {flashState === "correct" && (
        <div className="confetti-burst" aria-hidden="true">
          {CONFETTI_ANGLES.map((particle, index) => (
            <span
              key={index}
              className={`confetti-dot confetti-${particle.color}`}
              style={{ "--angle": `${particle.angle}deg` }}
            />
          ))}
        </div>
      )}
      {problem.flavor_text && <div className="problem-flavor-text">{problem.flavor_text}</div>}
      <div className="problem-question">{problem.question}</div>
      {feedbackForThisProblem && (
        <FeedbackBanner feedback={feedbackForThisProblem} justAdvanced={justAdvanced} />
      )}
      <NumberPad value={answer} onChange={setAnswer} onSubmit={handleSubmit} disabled={loading} />
    </div>
  );
}
