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
