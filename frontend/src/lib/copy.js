/**
 * CLAUDE.md sets a 20-word ceiling on the mastery-moment narrative,
 * "enforced by truncation in code". Nothing enforced it: `narrative.py`
 * counts words for the *word-problem* touchpoint, but only to decide whether
 * to re-prompt, never to cut, and the mastery/reward/boss texts were rendered
 * raw at whatever length the model returned.
 *
 * Cutting mid-clause is worse than not cutting — that is exactly the failure
 * that shipped "Nice use of the" to students (see `capWords` in praise.js).
 * So this trims on *sentence* boundaries: it keeps whole sentences while they
 * fit and returns null when not even the first one does, leaving the caller to
 * fall back to its own short copy rather than render a fragment.
 */
const MAX_NARRATIVE_WORDS = 20;

const SENTENCE_RE = /[^.!?]+[.!?]*/g;

function wordCount(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

export function capSentenceWords(text, maxWords = MAX_NARRATIVE_WORDS) {
  if (typeof text !== "string") return null;
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (wordCount(trimmed) <= maxWords) return trimmed;

  const sentences = trimmed.match(SENTENCE_RE) ?? [];
  const kept = [];
  let total = 0;
  for (const sentence of sentences) {
    const next = total + wordCount(sentence);
    if (next > maxWords) break;
    kept.push(sentence.trim());
    total = next;
  }
  return kept.length > 0 ? kept.join(" ") : null;
}

/** Apply the cap to each narrative field, dropping any that can't fit. */
export function capNarrative(narrative) {
  if (!narrative) return null;
  return {
    mastery_narrative: capSentenceWords(narrative.mastery_narrative),
    reward_narrative: capSentenceWords(narrative.reward_narrative),
    boss_battle_narrative: capSentenceWords(narrative.boss_battle_narrative),
  };
}
