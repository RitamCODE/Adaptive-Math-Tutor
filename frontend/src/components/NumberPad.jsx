const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "submit"];

export default function NumberPad({ value, onChange, onSubmit, disabled, columnCount = Infinity }) {
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
  function pressDigit(digit) {
    if (disabled) return;
    const length = value.length;
    if (length < columnCount) {
      onChange(digit + value);
      return;
    }
    const index = length - columnCount + 1;
    onChange(value.slice(0, index) + digit + value.slice(index));
  }

  function pressBackspace() {
    if (disabled) return;
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
  }

  function pressSubmit() {
    if (disabled || value.trim() === "") return;
    onSubmit();
  }

  return (
    <div className="number-pad">
      <div className="number-pad-display" aria-live="polite">
        {value || "?"}
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
