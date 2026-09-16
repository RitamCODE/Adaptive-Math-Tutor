import { useEffect, useRef, useState } from "react";
import { parseQuestion } from "../lib/arithmetic";

const CELL_COUNT = 10;

function Dot() {
  return (
    <svg className="dot-svg" viewBox="0 0 32 32" aria-hidden="true">
      <circle className="dot-circle" cx="16" cy="16" r="13" />
    </svg>
  );
}

/**
 * A single 10-cell ten-frame for `addition_no_carry`, whose "easy" bucket
 * only ever generates single-digit a+b<=9 — exactly what one frame can show.
 *
 * That skill has no bug rules, so no diagnosis ever names a visual for it and
 * nothing can auto-open this frame. It is available on request at any time,
 * and closed until asked for: a manipulative is help a student reaches for or
 * earns with a mistake, never the default surface.
 */
export default function TenFrame({ problem, onInteract }) {
  const parsed = parseQuestion(problem.question);
  const resetKey = problem.problem_id;

  // Closed until the student asks; mastery alone never opens it.
  const [expanded, setExpanded] = useState(false);
  const [filled, setFilled] = useState(0);
  const [drag, setDrag] = useState(null);

  const frameRef = useRef(null);
  const ghostRef = useRef(null);

  useEffect(() => {
    setFilled(0);
    setDrag(null);
    setExpanded(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  const valid = !!parsed && parsed.operator === "+" && parsed.a <= 9 && parsed.b <= 9;

  if (!valid) return null;

  const { a, b } = parsed;
  const remaining = b - filled;

  function moveGhost(x, y) {
    if (ghostRef.current) {
      ghostRef.current.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    }
  }

  function isOverFrame(x, y) {
    const rect = frameRef.current?.getBoundingClientRect();
    if (!rect) return false;
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function handleDotPointerDown(e) {
    if (remaining <= 0) return;
    onInteract?.();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ pointerId: e.pointerId });
    moveGhost(e.clientX, e.clientY);
  }

  function handleDotPointerMove(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    moveGhost(e.clientX, e.clientY);
  }

  function handleDotPointerUp(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    if (isOverFrame(e.clientX, e.clientY)) {
      setFilled((f) => Math.min(b, f + 1));
    }
    setDrag(null);
  }

  return (
    <div className="ten-frame">
      <div className="ten-frame-header">
        <span>🔟 Ten frame</span>
        <button type="button" className="ten-frame-toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Hide frame" : "Show frame"}
        </button>
      </div>

      {expanded && (
        <>
          <div className="ten-frame-grid" ref={frameRef}>
            {Array.from({ length: CELL_COUNT }).map((_, i) => {
              const state = i < a ? "given" : i < a + filled ? "placed" : "empty";
              return (
                <div key={i} className={`ten-frame-cell ten-frame-cell-${state}`}>
                  {state !== "empty" && <Dot />}
                </div>
              );
            })}
          </div>

          {remaining > 0 && (
            <div className="ten-frame-supply">
              <div className="ten-frame-pile-label">Add {remaining} more</div>
              <div className="ten-frame-pile-tokens">
                {Array.from({ length: remaining }).map((_, i) => (
                  <div
                    key={i}
                    className={`dot-token${drag ? " dragging" : ""}`}
                    onPointerDown={handleDotPointerDown}
                    onPointerMove={handleDotPointerMove}
                    onPointerUp={handleDotPointerUp}
                  >
                    <Dot />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div ref={ghostRef} className={`token-ghost${drag ? " token-ghost-visible" : ""}`} aria-hidden="true">
            {drag && <Dot />}
          </div>
        </>
      )}
    </div>
  );
}
