/**
 * Which remediation a wrong answer earns, given the student's live BKT
 * mastery on the skill.
 *
 * A manipulative is help that follows an error, never the default surface:
 * nothing opens on attempt 1 at any mastery level, and the opt-in control
 * ("Show blocks" / "Show frame") stays available at all times but closed
 * until the student asks. These bands decide what happens on attempt 2 of a
 * wrong, signal-bearing answer — the fading is in how much scaffolding the
 * error earns, not in what is on screen before one.
 *
 *   "open"      below 0.4 — open the manipulative, pre-loaded with the
 *               student's own wrong answer
 *   "offered"   0.4 to 0.7 — hint text, with the manipulative one tap away
 *   "hint_only" above 0.7 — hint text alone, nothing opens
 *
 * These two numbers are separate from the 0.8 mastery threshold, which
 * governs progression and lives server-side. Do not unify them.
 */
export function bandFromMastery(mastery) {
  if (mastery < 0.4) return "open";
  if (mastery <= 0.7) return "offered";
  return "hint_only";
}

/**
 * Is this feedback the attempt-2 remediation window for a given manipulative
 * family ("base10_blocks/" or "number_line/")?
 *
 * The backend withholds `visual` until attempt 2 (`diagnosis.py`), and
 * `attempts_remaining === 1` is exactly attempt 2 of 3 — so nothing can
 * surface before a mistake, and attempt 3 (which reveals the worked answer)
 * doesn't open a manipulative either. Shared so the widgets can't drift
 * apart on what counts as "remediating".
 */
export function isRemediatingWith(feedback, visualPrefix) {
  return (
    !!feedback &&
    feedback.correct === false &&
    feedback.attempts_remaining === 1 &&
    typeof feedback.visual === "string" &&
    feedback.visual.startsWith(visualPrefix)
  );
}
