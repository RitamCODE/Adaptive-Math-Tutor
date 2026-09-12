const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "back", "0", "submit"];

export default function NumberPad({ value, onChange, onSubmit, disabled }) {
  function pressDigit(digit) {
    if (disabled) return;
    onChange(value + digit);
  }

  function pressBackspace() {
    if (disabled) return;
    onChange(value.slice(0, -1));
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
