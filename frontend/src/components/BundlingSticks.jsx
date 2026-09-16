import { useEffect, useRef, useState } from "react";
import { parseQuestion, toBlocks } from "../lib/arithmetic";
import { playBundleSnap } from "../lib/sound";

const PLACE_ORDER = ["ones", "tens", "hundreds"];
const PLACE_LABEL = { ones: "Ones", tens: "Tens", hundreds: "Hundreds" };
const TOKEN_TYPE_BY_PLACE = { ones: "stick", tens: "bundle", hundreds: "flat" };
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

function TokenIcon({ tokenType }) {
  if (tokenType === "stick") return <Stick />;
  if (tokenType === "bundle") return <Bundle />;
  return <Flat />;
}

function bandFromMastery(mastery) {
  if (mastery < 0.4) return "open";
  if (mastery <= 0.7) return "collapsed";
  return "hidden";
}

function initWorkspace(operation, a) {
  if (operation === "add") {
    return { ones: { loose: 0 }, tens: { loose: 0 }, hundreds: { loose: 0 } };
  }
  const blocks = toBlocks(a);
  return {
    ones: { loose: blocks.ones },
    tens: { loose: blocks.tens },
    hundreds: { loose: blocks.hundreds },
  };
}

function legalDestinations(operation, zone, place, tokenType) {
  if (operation === "add") {
    if (zone === "pileA" || zone === "pileB") return [place];
    return [];
  }
  if (zone !== place) return [];
  const dests = ["trash"];
  const idx = PLACE_ORDER.indexOf(place);
  if (idx > 0 && tokenType !== "stick") {
    dests.push(PLACE_ORDER[idx - 1]);
  }
  return dests;
}

function computeInvite(columns, removeTarget, removed) {
  if (!removeTarget) return null;
  for (const place of PLACE_ORDER) {
    if (removeTarget[place] - removed[place] > columns[place].loose) {
      let idx = PLACE_ORDER.indexOf(place) + 1;
      while (idx < PLACE_ORDER.length && columns[PLACE_ORDER[idx]].loose === 0) idx++;
      if (idx < PLACE_ORDER.length) return { from: PLACE_ORDER[idx], to: PLACE_ORDER[idx - 1] };
      return null;
    }
  }
  return null;
}

export default function BundlingSticks({ problem, feedback, mastery, onInteract }) {
  const parsed = parseQuestion(problem.question);

  const isForcedDiagnostic =
    !!feedback &&
    feedback.correct === false &&
    feedback.attempts_remaining === 1 &&
    typeof feedback.visual === "string" &&
    feedback.visual.startsWith("base10_blocks/");

  const band = bandFromMastery(mastery ?? 0);
  const operation = parsed?.operator === "-" ? "sub" : "add";
  const resetKey = `${problem.problem_id}:${isForcedDiagnostic}`;

  const [expanded, setExpanded] = useState(band === "open");
  const [columns, setColumns] = useState(() => (parsed ? initWorkspace(operation, parsed.a) : null));
  const [pileA, setPileA] = useState(() => (parsed && operation === "add" ? toBlocks(parsed.a) : null));
  const [pileB, setPileB] = useState(() => (parsed && operation === "add" ? toBlocks(parsed.b) : null));
  const [removeTarget, setRemoveTarget] = useState(() =>
    parsed && operation === "sub" ? toBlocks(parsed.b) : null
  );
  const [removed, setRemoved] = useState({ ones: 0, tens: 0, hundreds: 0 });
  const [drag, setDrag] = useState(null);
  const [animInfo, setAnimInfo] = useState(null);
  const [animating, setAnimating] = useState(false);

  const zoneRefs = useRef({});
  const ghostRef = useRef(null);
  const timeoutsRef = useRef([]);

  useEffect(() => {
    if (!parsed) return;
    setColumns(initWorkspace(operation, parsed.a));
    setPileA(operation === "add" ? toBlocks(parsed.a) : null);
    setPileB(operation === "add" ? toBlocks(parsed.b) : null);
    setRemoveTarget(operation === "sub" ? toBlocks(parsed.b) : null);
    setRemoved({ ones: 0, tens: 0, hundreds: 0 });
    setDrag(null);
    setAnimInfo(null);
    setAnimating(false);
    setExpanded(band === "open");
    return () => {
      timeoutsRef.current.forEach(clearTimeout);
      timeoutsRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  useEffect(() => {
    if (isForcedDiagnostic) setExpanded(true);
  }, [isForcedDiagnostic]);

  useEffect(() => {
    if (operation !== "add" || animating || !columns) return;
    const overflowPlace = PLACE_ORDER.find((p, i) => i < PLACE_ORDER.length - 1 && columns[p].loose >= 10);
    if (overflowPlace) runTransition("bundle", overflowPlace);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columns, operation, animating]);

  if (!parsed || !columns) return null;

  function runTransition(direction, place) {
    setAnimating(true);
    setAnimInfo({ direction, place, phase: "glow" });
    const t1 = setTimeout(() => {
      setAnimInfo((info) => (info ? { ...info, phase: "snap" } : info));
      if (direction === "bundle") playBundleSnap();
      const t2 = setTimeout(() => {
        setColumns((cols) => {
          const idx = PLACE_ORDER.indexOf(place);
          const next = { ...cols };
          if (direction === "bundle") {
            const up = PLACE_ORDER[idx + 1];
            next[place] = { loose: next[place].loose - 10 };
            next[up] = { loose: next[up].loose + 1 };
          } else {
            const down = PLACE_ORDER[idx - 1];
            next[place] = { loose: next[place].loose - 1 };
            next[down] = { loose: next[down].loose + 10 };
          }
          return next;
        });
        setAnimInfo(null);
        setAnimating(false);
      }, SNAP_MS);
      timeoutsRef.current.push(t2);
    }, GLOW_MS);
    timeoutsRef.current.push(t1);
  }

  function moveGhost(x, y) {
    if (ghostRef.current) {
      ghostRef.current.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
    }
  }

  function findDropZone(x, y) {
    for (const [zoneName, el] of Object.entries(zoneRefs.current)) {
      if (!el) continue;
      const rect = el.getBoundingClientRect();
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) return zoneName;
    }
    return null;
  }

  function commitDrop(dragInfo, destZone) {
    if (operation === "add") {
      const setPile = dragInfo.zone === "pileA" ? setPileA : setPileB;
      setPile((p) => ({ ...p, [dragInfo.place]: p[dragInfo.place] - 1 }));
      setColumns((cols) => ({
        ...cols,
        [dragInfo.place]: { loose: cols[dragInfo.place].loose + 1 },
      }));
      return;
    }
    if (destZone === "trash") {
      setColumns((cols) => ({ ...cols, [dragInfo.place]: { loose: cols[dragInfo.place].loose - 1 } }));
      setRemoved((r) => ({ ...r, [dragInfo.place]: r[dragInfo.place] + 1 }));
      return;
    }
    runTransition("unbundle", dragInfo.place);
  }

  function handleTokenPointerDown(e, tokenInfo) {
    if (animating) return;
    onInteract?.();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ ...tokenInfo, pointerId: e.pointerId });
    moveGhost(e.clientX, e.clientY);
  }

  function handleTokenPointerMove(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    moveGhost(e.clientX, e.clientY);
  }

  function handleTokenPointerUp(e) {
    if (!drag || e.pointerId !== drag.pointerId) return;
    e.currentTarget.releasePointerCapture(e.pointerId);
    const destZone = findDropZone(e.clientX, e.clientY);
    if (destZone && legalDestinations(operation, drag.zone, drag.place, drag.tokenType).includes(destZone)) {
      commitDrop(drag, destZone);
    }
    setDrag(null);
  }

  function renderTokens(zone, place, count, draggable = true) {
    const tokenType = TOKEN_TYPE_BY_PLACE[place];
    return Array.from({ length: count }).map((_, i) => (
      <div
        key={`${zone}-${place}-${i}`}
        className={`stick-token${draggable ? "" : " stick-token-static"}${
          drag?.zone === zone && drag?.place === place ? " dragging" : ""
        }`}
        onPointerDown={draggable ? (e) => handleTokenPointerDown(e, { zone, place, tokenType }) : undefined}
        onPointerMove={draggable ? handleTokenPointerMove : undefined}
        onPointerUp={draggable ? handleTokenPointerUp : undefined}
      >
        <TokenIcon tokenType={tokenType} />
      </div>
    ));
  }

  const invite = operation === "sub" ? computeInvite(columns, removeTarget, removed) : null;
  const liveTotal = 100 * columns.hundreds.loose + 10 * columns.tens.loose + columns.ones.loose;
  const showToggle = band !== "open";

  return (
    <div className="bundling-sticks">
      <div className="bundling-sticks-header">
        <span>🧮 Base-ten blocks</span>
        {showToggle && (
          <button type="button" className="bundling-sticks-toggle" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Hide blocks" : "Show blocks"}
          </button>
        )}
      </div>

      {expanded && (
        <>
          <div className={`bundling-sticks-canvas${animating ? " animating" : ""}`}>
            {operation === "add" &&
              [
                { label: "First number", zone: "pileA", pile: pileA ?? { hundreds: 0, tens: 0, ones: 0 } },
                { label: "Second number", zone: "pileB", pile: pileB ?? { hundreds: 0, tens: 0, ones: 0 } },
              ].map(({ label, zone, pile }) => (
                <div className="stick-pile" key={zone}>
                  <div className="stick-pile-label">{label}</div>
                  {[...PLACE_ORDER].reverse().map((place) => (
                    <div className="stick-column" key={place}>
                      <div className="stick-column-label">
                        {PLACE_LABEL[place]} · {pile[place]}
                      </div>
                      <div className="stick-column-tokens">{renderTokens(zone, place, pile[place])}</div>
                    </div>
                  ))}
                </div>
              ))}

            <div className="stick-workspace">
              <div className="stick-pile-label">{operation === "add" ? "Combined total" : "What's left"}</div>
              {[...PLACE_ORDER].reverse().map((place) => (
                <div
                  className={`stick-column stick-column-workspace${
                    animInfo?.place === place ? ` stick-column-${animInfo.phase}` : ""
                  }${invite?.from === place ? " bundle-invites-borrow" : ""}`}
                  key={place}
                  ref={(el) => {
                    zoneRefs.current[place] = el;
                  }}
                >
                  <div className="stick-column-label">
                    {PLACE_LABEL[place]} · {columns[place].loose}
                  </div>
                  <div className="stick-column-tokens">
                    {renderTokens(place, place, columns[place].loose, operation === "sub")}
                  </div>
                </div>
              ))}
            </div>

            {operation === "sub" && removeTarget && (
              <div
                className="stick-trash"
                ref={(el) => {
                  zoneRefs.current.trash = el;
                }}
              >
                <div className="stick-pile-label">Take away here</div>
                <div className="stick-trash-remaining">
                  {PLACE_ORDER.filter((p) => removeTarget[p] - removed[p] > 0)
                    .reverse()
                    .map((p) => `${removeTarget[p] - removed[p]} ${PLACE_LABEL[p].toLowerCase()}`)
                    .join(", ") || "Done!"}
                </div>
              </div>
            )}
          </div>

          <div className="bundling-sticks-readout">{liveTotal}</div>

          <div ref={ghostRef} className={`token-ghost${drag ? " token-ghost-visible" : ""}`} aria-hidden="true">
            {drag && <TokenIcon tokenType={drag.tokenType} />}
          </div>
        </>
      )}
    </div>
  );
}
