import { useEffect, useRef, useState } from "react";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "submit"];

export default function NumberPad({
  value,
  onChange,
  onSubmit,
  disabled,
  columnCount = Infinity,
  cursorIndex = null,
  onCursorChange,
}) {
  const digitRefs = useRef([]);
  const [dragPointerId, setDragPointerId] = useState(null);

  // Digits are solved ones-first (then tens, then hundreds, ...), matching
  // column arithmetic's right-to-left order. Every column but the last
  // always contributes exactly one digit — a carry moves the overflow into
  // the next column instead of writing it — so each of those is a fresh
  // digit prepended to the left of what's already there. The last column has
  // nowhere left to carry into, so it alone may need a second digit (e.g.
  // 97 + 51: ones "8" prepends to "8"; the tens/hundreds column's raw value
  // "14" starts the same way — its first digit "1" also prepends, to "18" —
  // but its second digit "4" belongs inside that same column's value, so it
  // lands right after the "1" rather than out in front of it: "148").
  // `columnCount` is how many digits the wider operand has, i.e. how many of
  // those single-digit columns come before the final one.
  //
  // This auto-placement only applies while `cursorIndex` is null, i.e. the
  // student has only ever tapped the on-screen keys. The moment they use a
  // physical keyboard or drag the on-screen cursor, `cursorIndex` becomes a
  // concrete position and every following digit/backspace — tapped or
  // typed — inserts at that position like an ordinary text cursor instead.
  function pressDigit(digit) {
    if (disabled) return;
    if (cursorIndex === null) {
      const length = value.length;
      if (length < columnCount) {
        onChange(digit + value);
        return;
      }
      const index = length - columnCount + 1;
      onChange(value.slice(0, index) + digit + value.slice(index));
      return;
    }
    onChange(value.slice(0, cursorIndex) + digit + value.slice(cursorIndex));
    onCursorChange(cursorIndex + 1);
  }

  function pressBackspace() {
    if (disabled) return;
    if (cursorIndex === null) {
      const length = value.length;
      if (length <= columnCount) {
        // Every digit so far is a column's own first (and so far only) digit,
        // each prepended in turn — the most recent one is still the leftmost.
        onChange(value.slice(1));
        return;
      }
      // We're past the final column's first digit: the most recent keystroke
      // landed right after it, not at the front.
      const index = length - columnCount;
      onChange(value.slice(0, index) + value.slice(index + 1));
      return;
    }
    if (cursorIndex === 0) return;
    onChange(value.slice(0, cursorIndex - 1) + value.slice(cursorIndex));
    onCursorChange(cursorIndex - 1);
  }

  function pressSubmit() {
    if (disabled || value.trim() === "") return;
    onSubmit();
  }

  function moveCursor(delta) {
    if (disabled) return;
    const base = cursorIndex === null ? value.length : cursorIndex;
    onCursorChange(Math.max(0, Math.min(value.length, base + delta)));
  }

  // No on-screen key ever calls onCursorChange itself, so a student who only
  // ever taps the pad can never leave auto-placement mode — the branches
  // above stay provably identical to the pre-keyboard/cursor behavior.
  useEffect(() => {
    function handleKeyDown(e) {
      if (disabled) return;
      if (e.key >= "0" && e.key <= "9") {
        e.preventDefault();
        pressDigit(e.key);
      } else if (e.key === "Backspace") {
        e.preventDefault();
        pressBackspace();
      } else if (e.key === "Enter") {
        e.preventDefault();
        pressSubmit();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        moveCursor(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        moveCursor(1);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled, value, cursorIndex, columnCount]);

  function nearestIndex(clientX) {
    const spans = digitRefs.current;
    for (let i = 0; i < spans.length; i++) {
      const el = spans[i];
      if (!el) continue;
      const rect = el.getBoundingClientRect();
      if (clientX < rect.left + rect.width / 2) return i;
    }
    return spans.length;
  }

  function handleCaretPointerDown(e) {
    if (disabled) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* no capture available; the drag still works */
    }
    setDragPointerId(e.pointerId);
    onCursorChange(nearestIndex(e.clientX));
  }

  function handleCaretPointerMove(e) {
    if (dragPointerId === null || e.pointerId !== dragPointerId) return;
    onCursorChange(nearestIndex(e.clientX));
  }

  function handleCaretPointerUp(e) {
    if (dragPointerId === null || e.pointerId !== dragPointerId) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* nothing was captured */
    }
    setDragPointerId(null);
  }

  const chars = value.split("");
  // While cursorIndex is null the cursor's drag handle still lives at the
  // end of the string — invisible, since no caret is drawn in auto-placement
  // mode — so a drag can be the thing that switches into cursor mode, the
  // same way a keystroke does.
  const effectiveIndex =
    cursorIndex === null ? chars.length : Math.max(0, Math.min(chars.length, cursorIndex));

  digitRefs.current = [];
  const displayItems = [];
  for (let i = 0; i <= chars.length; i++) {
    if (i === effectiveIndex) {
      displayItems.push(
        <span className="number-pad-caret-anchor" key="caret">
          {cursorIndex !== null && <span className="number-pad-caret" />}
          <span
            className="number-pad-caret-handle"
            onPointerDown={handleCaretPointerDown}
            onPointerMove={handleCaretPointerMove}
            onPointerUp={handleCaretPointerUp}
          />
        </span>
      );
    }
    if (i < chars.length) {
      displayItems.push(
        <span className="number-pad-digit" key={`d${i}`} ref={(el) => (digitRefs.current[i] = el)}>
          {chars[i]}
        </span>
      );
    }
  }

  return (
    <div className="number-pad">
      <div
        className={`number-pad-display${dragPointerId !== null ? " number-pad-display-dragging" : ""}`}
        aria-live="polite"
      >
        {value === "" && <span className="number-pad-placeholder">?</span>}
        {displayItems}
      </div>
      <div className="number-pad-grid">
        {KEYS.map((key) => {
          if (key === "back") {
            return (
              <button
                key={key}
                type="button"
                className="number-pad-key number-pad-key-back"
                onClick={pressBackspace}
                disabled={disabled || value === ""}
                aria-label="Backspace"
              >
                ⌫
              </button>
            );
          }
          if (key === "submit") {
            return (
              <button
                key={key}
                type="button"
                className="number-pad-key number-pad-key-submit"
                onClick={pressSubmit}
                disabled={disabled || value.trim() === ""}
              >
                Submit
              </button>
            );
          }
          return (
            <button
              key={key}
              type="button"
              className="number-pad-key"
              onClick={() => pressDigit(key)}
              disabled={disabled}
            >
              {key}
            </button>
          );
        })}
      </div>
    </div>
  );
}
