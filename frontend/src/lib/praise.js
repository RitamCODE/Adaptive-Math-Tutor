// Deterministic four-branch per-problem praise selector (CLAUDE.md copy limits:
// "not an LLM call"). Checked in priority order — effort beats strategy beats
// speed beats the named-skill default — since a struggled-then-succeeded
// answer is a stronger signal to acknowledge than a fast, confident one.

import { SKILL_DISPLAY_NAMES } from "../constants";

const MAX_PRAISE_WORDS = 4;

export function capWords(text, maxWords = MAX_PRAISE_WORDS) {
  const words = text.trim().split(/\s+/);
  return words.length <= maxWords ? text : words.slice(0, maxWords).join(" ");
}

export function selectPraise({
  skillTag,
  mastery,
  attemptNumber,
  timeTakenSec,
  priorAvgTimeSec,
  usedManipulative,
}) {
  if (attemptNumber > 1) {
    return capWords("You stuck with it!");
  }
  if (usedManipulative) {
    return capWords("Nice use of the tool!");
  }
  if (mastery > 0.7 && priorAvgTimeSec != null && timeTakenSec < priorAvgTimeSec) {
    return capWords("Faster than your usual!");
  }
  return capWords(SKILL_DISPLAY_NAMES[skillTag] ?? "Correct!");
}
