import { parseQuestion } from "../lib/arithmetic";
import { digitsOf } from "../lib/columnBoard";

/**
 * The plain-arithmetic equation, stacked in column form like ColumnArithmetic's
 * header — but without the carry/borrow annotation row, the answer row, or the
 * block manipulative underneath, none of which apply to a skill that never
 * regroups. `addition_no_carry`/`subtraction_no_borrow` are defined by never
 * needing a spare carry-out column, so the column count is just the wider
 * operand's digit count.
 */
export default function StackedEquation({ problem }) {
  const parsed = parseQuestion(problem.question);
  if (!parsed) return <div className="problem-question">{problem.question}</div>;

  const operation = parsed.operator === "-" ? "sub" : "add";
  const places = operation === "sub" ? String(parsed.a).length : Math.max(String(parsed.a).length, String(parsed.b).length);
  const da = digitsOf(parsed.a, places);
  const db = digitsOf(parsed.b, places);
  const columnOrder = Array.from({ length: places }, (_, i) => places - 1 - i);

  function operandText(value, digits, i) {
    return i < String(value).length ? String(digits[i]) : "";
  }

  return (
    <div className="column-arithmetic">
      <div className="ca-equation" style={{ "--ca-cols": places }}>
        <div className="ca-sign" />
        {columnOrder.map((i) => (
          <div className="ca-digit" key={`a-${i}`}>
            {operandText(parsed.a, da, i)}
          </div>
        ))}

        <div className="ca-sign">{operation === "sub" ? "−" : "+"}</div>
        {columnOrder.map((i) => (
          <div className="ca-digit" key={`b-${i}`}>
            {operandText(parsed.b, db, i)}
          </div>
        ))}

        <div className="ca-rule" />
      </div>
    </div>
  );
}
