import { useEffect, useRef, useState } from "react";
import NumberPad from "./NumberPad";
import FeedbackBanner from "./FeedbackBanner";
import ColumnArithmetic from "./ColumnArithmetic";
import NumberLine from "./NumberLine";
import TenFrame from "./TenFrame";
import { parseQuestion } from "../lib/arithmetic";

// The two skills whose whole point is regrouping. For these the equation is
// rendered in column form by ColumnArithmetic, which owns both the written
// digits and the blocks beneath them so the two stay aligned; the other two
// skills keep the plain horizontal equation.
const COLUMN_ARITHMETIC_SKILLS = new Set(["addition_carry", "subtraction_borrow"]);
const TEN_FRAME_SKILLS = new Set(["addition_no_carry"]);

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

export default function ProblemCard({
  problem,
  onSubmit,
  onAdvance,
  loading,
  flashState,
  feedback,
  justAdvanced,
  skillProgress,
}) {
  const [answer, setAnswer] = useState("");
  const usedManipulativeRef = useRef(false);

  useEffect(() => {
    usedManipulativeRef.current = false;
  }, [problem.problem_id]);

  function handleSubmit() {
    if (answer.trim() === "") return;
    onSubmit(Number(answer), usedManipulativeRef.current);
    setAnswer("");
  }

  function markManipulativeUsed() {
    usedManipulativeRef.current = true;
  }

  const feedbackForThisProblem = feedback && feedback.problem_id === problem.problem_id ? feedback : null;
  const mastery = skillProgress?.find((entry) => entry.skill === problem.skill_tag)?.mastery ?? 0;
  const showColumnArithmetic = COLUMN_ARITHMETIC_SKILLS.has(problem.skill_tag);
  const showTenFrame = TEN_FRAME_SKILLS.has(problem.skill_tag);
  // Every column but the last always contributes exactly one digit to the
  // written answer — a column that overflows past 9 carries the extra into
  // the next column rather than writing it. Only the last (most significant)
  // column has nowhere further to carry into, so it alone may write two
  // digits (e.g. 97 + 51: ones "8", then tens/hundreds "14" -> "148"). This
  // is how many single-digit columns come before that final one; NumberPad
  // uses it to know when a keystroke starts a new column (prepend) versus
  // continues the final column's own two-digit value (insert after its
  // first digit). Operands, not the hidden answer, decide this, so it's
  // known before the student has answered anything.
  const parsedOperands = parseQuestion(problem.question);
  const columnCount = parsedOperands
    ? Math.max(String(parsedOperands.a).length, String(parsedOperands.b).length)
    : Infinity;

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
      {/* The equation is pinned above the manipulative area and sticks to the
          top of the card, so the numerals never need scrolling to during a
          problem — however tall the blocks grow underneath them. In column
          form the equation and the blocks are one widget precisely so they
          share a grid; elsewhere it is the plain question string. */}
      {showColumnArithmetic ? (
        <ColumnArithmetic
          problem={problem}
          feedback={feedbackForThisProblem}
          mastery={mastery}
          onInteract={markManipulativeUsed}
        />
      ) : (
        <div className="problem-question">{problem.question}</div>
      )}
      <div className="manipulative-canvas">
        {showTenFrame && <TenFrame problem={problem} onInteract={markManipulativeUsed} />}
        <NumberLine
          problem={problem}
          feedback={feedbackForThisProblem}
          mastery={mastery}
          onInteract={markManipulativeUsed}
        />
      </div>
      {feedbackForThisProblem && (
        <FeedbackBanner feedback={feedbackForThisProblem} justAdvanced={justAdvanced} onNext={onAdvance} />
      )}
      <NumberPad
        value={answer}
        onChange={setAnswer}
        onSubmit={handleSubmit}
        disabled={loading}
        columnCount={columnCount}
      />
    </div>
  );
}
