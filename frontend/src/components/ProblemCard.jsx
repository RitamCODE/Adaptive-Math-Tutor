import { useState } from "react";

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

export default function ProblemCard({ problem, onSubmit, loading, flashState }) {
  const [answer, setAnswer] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    if (answer.trim() === "") return;
    onSubmit(Number(answer));
    setAnswer("");
  }

  return (
    <form
      className={`problem-card${flashState ? ` problem-card-${flashState}` : ""}`}
      onSubmit={handleSubmit}
    >
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
      <input
        type="number"
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        placeholder="?"
        autoFocus
        disabled={loading}
      />
      <button type="submit" disabled={loading || answer.trim() === ""}>
        Submit
      </button>
    </form>
  );
}
