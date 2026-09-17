// Deterministic four-branch per-problem praise selector (CLAUDE.md copy limits:
// "not an LLM call"). Checked in priority order — effort beats strategy beats
// speed beats the named-skill default — since a struggled-then-succeeded
// answer is a stronger signal to acknowledge than a fast, confident one.

import { SKILL_DISPLAY_NAMES } from "../constants";

const MAX_PRAISE_WORDS = 4;

/**
 * Trim to the CLAUDE.md cap for a correct answer.
 *
 * This is a last-resort guard for the one branch whose text isn't a literal
 * (the skill display name). Every literal below is authored to fit, because
 * truncation here is destructive: it cuts on a word boundary with no ellipsis,
 * so an over-long literal ships as a sentence fragment rather than as anything
 * a reader would recognise as clipped. "Nice use of the tool!" is five words
 * and reached students as "Nice use of the". The dev warning exists so the
 * next one is loud instead of mysterious.
 */
export function capWords(text, maxWords = MAX_PRAISE_WORDS) {
  const words = text.trim().split(/\s+/);
  if (words.length <= maxWords) return text;
  if (import.meta.env?.DEV) {
    console.warn(
      `[praise] "${text}" is ${words.length} words, over the ${maxWords}-word cap — ` +
        `it will render as "${words.slice(0, maxWords).join(" ")}". Shorten the copy.`
    );
  }
  return words.slice(0, maxWords).join(" ");
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
    return capWords("Nice work with tools!");
  }
  if (mastery > 0.7 && priorAvgTimeSec != null && timeTakenSec < priorAvgTimeSec) {
    return capWords("Faster than your usual!");
  }
  return capWords(SKILL_DISPLAY_NAMES[skillTag] ?? "Correct!");
}
