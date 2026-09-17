import { useEffect, useRef, useState } from "react";
import { parseQuestion } from "../lib/arithmetic";
import {
  PLACE_LABEL,
  TOKEN_TYPE,
  bundle,
  computeBorrow,
  digitsOf,
  initBoard,
  placeCount,
  unbundle,
  visiblePlaceCount,
  withAt,
} from "../lib/columnBoard";
import { bandFromMastery, isRemediatingWith } from "../lib/remediation";
import { playBundleSnap } from "../lib/sound";

/**
 * Column arithmetic with base-ten blocks: the written algorithm and the
 * concrete one in a single grid, so what happens to the blocks and what
 * happens to the digits are the same event in the same place.
 *
 * Two grids share one `grid-template-columns`, which is what makes the
 * alignment structural rather than eyeballed: the equation grid (always
 * rendered, sticky, so the numerals never need scrolling to) and the block
 * grid beneath it (rendered when open). Block column k therefore sits
 * directly under digit column k.
 *
 * Work runs right to left from the ones, one active column at a time, and
 * each column's answer digit appears under the rule only when the student
 * has finished that column. Nothing is ever computed on the student's
 * behalf: there is no running total, and a digit the student has not worked
 * for does not exist on screen. (CLAUDE.md's "a manipulative never resolves
 * the answer" carries this per-column exception for the same reason the
 * number line's position readout is exempt — every digit here is caused by
 * the student's own drag.)
 *
 * Regrouping is one mechanic run in two directions. Ten ones bundling into a
 * ten (carrying) and one ten breaking into ten ones (borrowing) are the same
 * `runTransition` with opposite signs, so a child who has watched carrying
 * is watching its inverse when they borrow.
 */

const GLOW_MS = 400;
const SNAP_MS = 250;

function Stick() {
  return (
    <svg className="stick-svg" viewBox="0 0 16 48" aria-hidden="true">
      <rect className="stick-rect" x="3" y="2" width="10" height="44" rx="5" />
    </svg>
  );
}

function Bundle() {
  return (
    <svg className="bundle-svg" viewBox="0 0 56 48" aria-hidden="true">
      {Array.from({ length: 10 }).map((_, i) => (
        <rect key={i} className="bundle-stick-rect" x={2 + i * 5.2} y="2" width="4" height="44" rx="2" />
      ))}
      <rect className="bundle-tie" x="0" y="19" width="56" height="8" rx="3" />
    </svg>
  );
}

function Flat() {
  return (
    <svg className="flat-svg" viewBox="0 0 56 56" aria-hidden="true">
      <rect className="flat-rect" x="2" y="2" width="52" height="52" rx="6" />
      {Array.from({ length: 9 }).map((_, i) => (
        <line key={i} className="flat-line" x1={2 + (i + 1) * 5.2} y1="4" x2={2 + (i + 1) * 5.2} y2="52" />
      ))}
    </svg>
  );
}

function Cube() {
  return (
    <svg className="cube-svg" viewBox="0 0 56 56" aria-hidden="true">
      <rect className="flat-rect" x="10" y="2" width="44" height="44" rx="5" />
      <rect className="flat-rect" x="6" y="6" width="44" height="44" rx="5" />
      <rect className="flat-rect" x="2" y="10" width="44" height="44" rx="5" />
      {Array.from({ length: 8 }).map((_, i) => (
        <line key={i} className="flat-line" x1={2 + (i + 1) * 4.8} y1="12" x2={2 + (i + 1) * 4.8} y2="52" />
      ))}
    </svg>
  );
}

function TokenIcon({ place }) {
  const type = TOKEN_TYPE[place];
  if (type === "stick") return <Stick />;
  if (type === "bundle") return <Bundle />;
  if (type === "flat") return <Flat />;
  return <Cube />;
}

export default function ColumnArithmetic({ problem, feedback, mastery, onInteract }) {
  const parsed = parseQuestion(problem.question);
  const operation = parsed?.operator === "-" ? "sub" : "add";
  const places = parsed ? placeCount(operation, parsed.a, parsed.b) : 1;

  const isRemediating = isRemediatingWith(feedback, "base10_blocks/");
  const band = bandFromMastery(mastery ?? 0);
  // Only the lowest band earns an automatic open, and only while remediating.
  // Nothing opens on attempt 1 at any mastery level.
  const isForcedDiagnostic = isRemediating && band === "open";
  const resetKey = `${problem.problem_id}:${isForcedDiagnostic}`;

  const [expanded, setExpanded] = useState(false);
  const [board, setBoard] = useState(() =>
    initBoard(operation, parsed?.a ?? 0, parsed?.b ?? 0, places, resetKey)
  );
  const [drag, setDrag] = useState(null);
  const [anim, setAnim] = useState(null);
  const [animating, setAnimating] = useState(false);

  const zoneRefs = useRef({});
  const ghostRef = useRef(null);
  const timeoutsRef = useRef([]);

  useEffect(() => {
    setBoard(initBoard(operation, parsed?.a ?? 0, parsed?.b ?? 0, places, resetKey));
    setDrag(null);
    setAnim(null);
    setAnimating(false);
    setExpanded(false);
    zoneRefs.current = {};
    return () => {
      timeoutsRef.current.forEach(clearTimeout);
      timeoutsRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  useEffect(() => {
    if (isForcedDiagnostic) setExpanded(true);
  }, [isForcedDiagnostic]);

  function runTransition(direction, place) {
    setAnimating(true);
    setAnim({ direction, place, phase: "glow" });
    const t1 = setTimeout(() => {
      setAnim((info) => (info ? { ...info, phase: "snap" } : info));
      playBundleSnap();
      const t2 = setTimeout(() => {
        setBoard((b) => (direction === "bundle" ? bundle(b, place) : unbundle(b, place)));
        setAnim(null);
        setAnimating(false);
      }, SNAP_MS);
      timeoutsRef.current.push(t2);
    }, GLOW_MS);
    timeoutsRef.current.push(t1);
  }

  const da = parsed ? digitsOf(parsed.a, places) : [];
  const db = parsed ? digitsOf(parsed.b, places) : [];
  const available = board.regrouped.map((value, i) => value - board.removed[i]);
  const needed = db.map((value, i) => value - board.removed[i]);
  const borrow = operation === "sub" ? computeBorrow(available, needed, board.active, places) : null;

  // Ten loose in a work zone refuse to stay loose: they bundle into one block
  // of the place above. This is the mechanic borrowing runs backwards.
  useEffect(() => {
    if (operation !== "add" || animating || board.key !== resetKey) return;
    const overflow = board.work.findIndex((count, i) => count >= 10 && i < places - 1);
    if (overflow >= 0) runTransition("bundle", overflow);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board, animating, operation, places, resetKey]);

  // A column is finished when its own work is done — every take-away slot
  // filled, or both addend piles emptied with nothing left to carry. Only
  // then does its answer digit exist.
  useEffect(() => {
    if (animating || board.key !== resetKey) return;
    const i = board.active;
    if (i >= places || board.answer[i] !== null) return;
    const finished =
      operation === "sub"
        ? board.removed[i] === db[i]
        : board.poolA[i] === 0 && board.poolB[i] === 0 && board.work[i] < 10;
    if (!finished) return;
    const value = operation === "sub" ? board.regrouped[i] - board.removed[i] : board.work[i];
    setBoard((b) => ({ ...b, answer: withAt(b.answer, i, value), active: i + 1 }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [board, animating, operation, places, resetKey]);

  if (!parsed) return null;

  function legalZone(dragInfo) {
    if (!dragInfo) return null;
    if (operation === "add") {
      return dragInfo.place === board.active ? `work:${board.active}` : null;
    }
    if (borrow && dragInfo.place === borrow.from && dragInfo.kind === "have") {
      return `pad:${borrow.to}`;
    }
    if (dragInfo.kind === "have" && dragInfo.place === board.active && needed[board.active] > 0) {
      return `slots:${board.active}`;
    }
    return null;
  }

  function commitDrop(dragInfo, zone) {
    if (operation === "add") {
      setBoard((b) => ({
        ...b,
        [dragInfo.kind]: withAt(b[dragInfo.kind], dragInfo.place, b[dragInfo.kind][dragInfo.place] - 1),
        work: withAt(b.work, dragInfo.place, b.work[dragInfo.place] + 1),
      }));
      return;
    }
    if (zone.startsWith("pad:")) {
      runTransition("unbundle", dragInfo.place);
      return;
    }
    setBoard((b) => ({ ...b, removed: withAt(b.removed, dragInfo.place, b.removed[dragInfo.place] + 1) }));
  }

  function moveGhost(x, y) {
    if (ghostRef.current) {
      ghostRef.current.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    }
  }

  // Any given drag has exactly one destination it may land in, so rather than
  // asking "which zone is under the pointer" — which a nested zone makes
  // ambiguous, and the borrow pad sits *inside* the take-away tray — ask
  // whether the pointer is inside the one zone this drag is allowed to use.
  function isOverZone(name, x, y) {
    const el = name ? zoneRefs.current[name] : null;
    if (!el || !el.isConnected) return false;
    const rect = el.getBoundingClientRect();
    return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
  }

  function handlePointerDown(e, tokenInfo) {
    if (animating) return;
    onInteract?.();
    // Capture keeps the move/up stream on the token even when the finger
    // leaves it, which is most of a drag. It throws for a pointer id the
    // browser doesn't know, and a failed capture is not a reason to refuse
    // the drag — the events still arrive, just less reliably.
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* no capture available; the drag still works */
    }
    setDrag({ ...tokenInfo, pointerId: e.pointerId });
    moveGhost(e.clientX, e.clientY);
  }

  function handlePointerMove(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    moveGhost(e.clientX, e.clientY);
  }

  function handlePointerUp(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* nothing was captured */
    }
    const target = legalZone(drag);
    if (isOverZone(target, e.clientX, e.clientY)) commitDrop(drag, target);
    setDrag(null);
  }

  // Columns render left to right, highest place first.
  const visiblePlaces = visiblePlaceCount(operation, parsed.a, parsed.b, board);
  const columnOrder = Array.from({ length: visiblePlaces }, (_, i) => visiblePlaces - 1 - i);
  const allResolved = board.answer.every((digit) => digit !== null);

  /** Leading zeros aren't written. A zero is leading only once every higher
   *  place has resolved to zero too, which can't be known until it has. */
  function answerText(i) {
    const digit = board.answer[i];
    if (digit === null) return "";
    if (digit !== 0 || i === 0) return String(digit);
    for (let j = i + 1; j < places; j += 1) {
      if (board.answer[j] === null) return "0";
      if (board.answer[j] !== 0) return "0";
    }
    return "";
  }

  function operandText(value, digits, i) {
    return i < String(value).length ? String(digits[i]) : "";
  }

  function annotationText(i) {
    if (operation === "sub") {
      return board.regrouped[i] !== da[i] ? String(board.regrouped[i]) : "";
    }
    return board.carried[i] ? "1" : "";
  }

  function renderTokens(kind, place, count, draggable) {
    return Array.from({ length: Math.max(count, 0) }).map((_, i) => (
      <div
        key={`${kind}-${place}-${i}`}
        className={`stick-token${draggable ? "" : " stick-token-static"}${
          drag?.kind === kind && drag?.place === place && drag?.index === i ? " dragging" : ""
        }`}
        onPointerDown={draggable ? (e) => handlePointerDown(e, { kind, place, index: i }) : undefined}
        onPointerMove={draggable ? handlePointerMove : undefined}
        onPointerUp={draggable ? handlePointerUp : undefined}
      >
        <TokenIcon place={place} />
      </div>
    ));
  }

  function columnStateClass(i) {
    if (board.answer[i] !== null) return " ca-col-done";
    if (i === board.active) return " ca-col-active";
    if (borrow && i === borrow.from) return " ca-col-lending";
    return " ca-col-waiting";
  }

  const isOffered = isRemediating && band === "offered" && !expanded;
  const gridStyle = { "--ca-cols": visiblePlaces };

  return (
    <div
      className={`column-arithmetic${expanded ? " column-arithmetic-open" : ""}${
        isOffered ? " column-arithmetic-offered" : ""
      }`}
    >
      <div className="ca-equation" style={gridStyle}>
        <div className="ca-sign" />
        {columnOrder.map((i) => (
          <div className="ca-annot" key={`an-${i}`}>
            {annotationText(i)}
          </div>
        ))}

        <div className="ca-sign" />
        {columnOrder.map((i) => (
          <div
            className={`ca-digit${
              operation === "sub" && board.regrouped[i] !== da[i] ? " ca-digit-struck" : ""
            }`}
            key={`a-${i}`}
          >
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

        <div className="ca-sign" />
        {columnOrder.map((i) => (
          <div
            className={`ca-digit ca-answer${board.answer[i] !== null ? " ca-answer-filled" : ""}`}
            key={`ans-${i}`}
          >
            {answerText(i)}
          </div>
        ))}
      </div>

      <div className="ca-toolbar">
        {/* Available at every mastery level and on every attempt, closed until
            the student asks. */}
        <button type="button" className="ca-toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Hide blocks" : isOffered ? "Show me the blocks" : "Show blocks"}
        </button>
        {expanded && (
          <span className="ca-status" role="status">
            {allResolved
              ? "All columns done — now type your answer."
              : borrow
                ? `Not enough in the ${PLACE_LABEL[borrow.to].toLowerCase()}. Break open a ${PLACE_LABEL[
                    borrow.from
                  ]
                    .toLowerCase()
                    .replace(/s$/, "")}.`
                : `Working the ${PLACE_LABEL[board.active]?.toLowerCase() ?? ""} column.`}
          </span>
        )}
      </div>

      {expanded && (
        <>
          <div className={`ca-blocks${animating ? " animating" : ""}`} style={gridStyle}>
            <div className="ca-sign" />
            {columnOrder.map((i) => (
              <div className={`ca-place${columnStateClass(i)}`} key={`lab-${i}`}>
                {PLACE_LABEL[i]}
              </div>
            ))}

            {operation === "sub" ? (
              <>
                <div className="ca-sign ca-row-label">have</div>
                {columnOrder.map((i) => (
                  <div
                    className={`ca-bin ca-bin-have${columnStateClass(i)}${
                      anim?.place === i ? ` ca-${anim.phase}` : ""
                    }${anim?.direction === "unbundle" && anim?.place === i + 1 ? " ca-receiving" : ""}`}
                    key={`have-${i}`}
                  >
                    {renderTokens(
                      "have",
                      i,
                      available[i],
                      !animating && (i === board.active || (borrow && i === borrow.from))
                    )}
                  </div>
                ))}

                <div className="ca-sign ca-row-label">take</div>
                {columnOrder.map((i) => (
                  <div
                    className={`ca-bin ca-bin-take${columnStateClass(i)}`}
                    key={`take-${i}`}
                    ref={(el) => {
                      zoneRefs.current[`slots:${i}`] = el;
                    }}
                  >
                    {borrow && borrow.to === i && (
                      <div
                        className="ca-pad"
                        ref={(el) => {
                          zoneRefs.current[`pad:${i}`] = el;
                        }}
                      >
                        Drop one {PLACE_LABEL[borrow.from].toLowerCase().replace(/s$/, "")} here
                      </div>
                    )}
                    {Array.from({ length: db[i] }).map((_, slot) => (
                      <div
                        key={`slot-${i}-${slot}`}
                        className={`ca-slot${slot < board.removed[i] ? " ca-slot-filled" : ""}`}
                      >
                        {slot < board.removed[i] ? <TokenIcon place={i} /> : null}
                      </div>
                    ))}
                    {db[i] > 0 && (
                      <div className="ca-bin-count">
                        {board.removed[i]} of {db[i]} taken
                      </div>
                    )}
                  </div>
                ))}
              </>
            ) : (
              <>
                <div className="ca-sign ca-row-label">first</div>
                {columnOrder.map((i) => (
                  <div className={`ca-bin ca-bin-have${columnStateClass(i)}`} key={`pa-${i}`}>
                    {renderTokens("poolA", i, board.poolA[i], !animating && i === board.active)}
                  </div>
                ))}

                <div className="ca-sign ca-row-label">second</div>
                {columnOrder.map((i) => (
                  <div className={`ca-bin ca-bin-have${columnStateClass(i)}`} key={`pb-${i}`}>
                    {renderTokens("poolB", i, board.poolB[i], !animating && i === board.active)}
                  </div>
                ))}

                <div className="ca-sign ca-row-label">total</div>
                {columnOrder.map((i) => (
                  <div
                    className={`ca-bin ca-bin-work${columnStateClass(i)}${
                      anim?.place === i ? ` ca-${anim.phase}` : ""
                    }`}
                    key={`work-${i}`}
                    ref={(el) => {
                      zoneRefs.current[`work:${i}`] = el;
                    }}
                  >
                    {board.poolA[i] + board.poolB[i] > 0 && board.work[i] === 0 && i === board.active && (
                      <div className="ca-pad">Drag blocks down here</div>
                    )}
                    {renderTokens("work", i, board.work[i], false)}
                  </div>
                ))}
              </>
            )}
          </div>

          <div ref={ghostRef} className={`token-ghost${drag ? " token-ghost-visible" : ""}`} aria-hidden="true">
            {drag && <TokenIcon place={drag.place} />}
          </div>
        </>
      )}
    </div>
  );
}
