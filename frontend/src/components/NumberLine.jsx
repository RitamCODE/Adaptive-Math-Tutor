import { useEffect, useRef, useState } from "react";
import { parseQuestion, toBlocks } from "../lib/arithmetic";

const PLACE_ORDER = ["hundreds", "tens", "ones"];
const PLACE_LABEL = { hundreds: "Hundreds", tens: "Tens", ones: "Ones" };

function HopArrow() {
  return (
    <svg className="hop-arrow-svg" viewBox="0 0 32 32" aria-hidden="true">
      <path className="hop-arrow-path" d="M5 16 H23 M15 8 L24 16 L15 24" />
    </svg>
  );
}

function zeroCounts() {
  return { hundreds: 0, tens: 0, ones: 0 };
}

/**
 * A number-line manipulative for the four `number_line/*` misconceptions
 * (count-on, operator confusion, operand order, digit reversal). Hops are
 * grouped by place value (reusing `toBlocks`, the same helper BundlingSticks
 * uses) so a 3-digit operand still means at most 9 hops per place, not
 * hundreds of individual unit hops.
 */
export default function NumberLine({ problem, feedback }) {
  const parsed = parseQuestion(problem.question);

  const isForcedDiagnostic =
    !!feedback &&
    feedback.correct === false &&
    feedback.attempts_remaining === 1 &&
    typeof feedback.visual === "string" &&
    feedback.visual.startsWith("number_line/");

  const [done, setDone] = useState(zeroCounts);
  const [drag, setDrag] = useState(null);

  const trackRef = useRef(null);
  const ghostRef = useRef(null);

  useEffect(() => {
    setDone(zeroCounts());
    setDrag(null);
  }, [problem.problem_id]);

  if (!isForcedDiagnostic || !parsed) return null;

  const direction = parsed.operator === "-" ? -1 : 1;
  const hopSupply = toBlocks(parsed.b);
  const doneValue = 100 * done.hundreds + 10 * done.tens + done.ones;
  const progressPct = parsed.b === 0 ? 0 : Math.min(100, (doneValue / parsed.b) * 100);
  const currentPosition = parsed.a + direction * doneValue;

  function moveGhost(x, y) {
    if (ghostRef.current) {
      ghostRef.current.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    }
  }

  function isOverTrack(x, y) {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect) return false;
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function handleHopPointerDown(e, place) {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ place, pointerId: e.pointerId });
    moveGhost(e.clientX, e.clientY);
  }

  function handleHopPointerMove(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    moveGhost(e.clientX, e.clientY);
  }

  function handleHopPointerUp(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    if (isOverTrack(e.clientX, e.clientY)) {
      setDone((d) => ({ ...d, [drag.place]: d[drag.place] + 1 }));
    }
    setDrag(null);
  }

  return (
    <div className="number-line">
      <div className="number-line-header">
        <span>🔢 Number line</span>
      </div>

      <div className="number-line-supply">
        {PLACE_ORDER.map((place) => {
          const remaining = hopSupply[place] - done[place];
          if (remaining <= 0) return null;
          return (
            <div className="number-line-pile" key={place}>
              <div className="number-line-pile-label">
                {PLACE_LABEL[place]} hops · {remaining}
              </div>
              <div className="number-line-pile-tokens">
                {Array.from({ length: remaining }).map((_, i) => (
                  <div
                    key={`${place}-${i}`}
                    className={`hop-token hop-token-${place}${
                      drag?.place === place ? " dragging" : ""
                    }`}
                    onPointerDown={(e) => handleHopPointerDown(e, place)}
                    onPointerMove={handleHopPointerMove}
                    onPointerUp={handleHopPointerUp}
                  >
                    <HopArrow />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      <div className="number-line-track" ref={trackRef}>
        <div className="number-line-start-label">{parsed.a}</div>
        <div className="number-line-rail">
          <div
            className={`number-line-marker${direction === -1 ? " number-line-marker-back" : ""}`}
            style={{ left: `${progressPct}%` }}
          />
        </div>
        <div className="number-line-direction" aria-hidden="true">
          {direction === 1 ? "→" : "←"}
        </div>
      </div>

      <div className="number-line-readout">{currentPosition}</div>

      <div ref={ghostRef} className={`token-ghost${drag ? " token-ghost-visible" : ""}`} aria-hidden="true">
        {drag && <HopArrow />}
      </div>
    </div>
  );
}
