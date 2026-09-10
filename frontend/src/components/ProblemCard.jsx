import { useState } from "react";

export default function ProblemCard({ problem, onSubmit, loading }) {
  const [answer, setAnswer] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    if (answer.trim() === "") return;
    onSubmit(Number(answer));
    setAnswer("");
  }

  return (
    <form className="problem-card" onSubmit={handleSubmit}>
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
