"""Digit-width progression, deliberately independent of BKT mastery.

`P(L)` (backend/models/bkt.py) is a slip/guess-corrected latent estimate: by
design it swings from `p_init` (0.3) to ~0.90 on a single correct answer, per
`is_mastered`'s own docstring. Feeding that value straight into how many
digits a problem has meant a student's very first correct answer on a skill
jumped its problems from 1-digit to 3-digit, skipping 2-digit entirely.

Digit-width here is its own small integer ladder per skill, advanced only by
a sustained run of correct answers at the current width — never by a BKT
jump. It has exactly two jobs: (a) decide when a skill's problems get wider,
and (b), only for the two skills that start at 1-digit, pick which specific
1-digit combination to show next so the narrowest tier neither repeats
combos pointlessly nor drags on forever. It never feeds `is_mastered`, and
BKT mastery never feeds it back. Only plain, deterministic Python — no LLM,
consistent with the project's curriculum/generation hard constraint.
"""

import random

# Index 0 is each skill's narrowest tier. addition_carry/subtraction_borrow
# start at width 2 because a carry/borrow is impossible with single digits
# (their own _WIDTH_BY_BUCKET tables already map "easy" to width 2).
WIDTH_LADDER: dict[str, list[int]] = {
    "addition_no_carry": [1, 2, 3],
    "subtraction_no_borrow": [1, 2, 3],
    "addition_carry": [2, 3],
    "subtraction_borrow": [2, 3],
}

# The only two skills whose tier 0 is 1-digit, so the only two that run the
# escalating-pair logic below. The other two skills use the flat run-length
# rule at every level, including their own tier 0.
NARROWEST_TIER_SKILLS = {"addition_no_carry", "subtraction_no_borrow"}

LEVEL_UP_RUN = 3  # flat gate for width > 1 -> next width: N consecutive correct,
                  # signal-bearing answers. Mirrors MASTERY_MIN_RUN's shape but is a
                  # completely separate counter — this is not mastery.
NARROW_TIER_BASE_RUN = 2  # 1-digit -> 2-digit gate: 2 consecutive correct 1-digit
                          # answers, escalating trivial-then-non-trivial


def all_combos(skill: str) -> list[tuple[int, int]]:
    """Every valid 1-digit (a, b) operand pair for `skill`'s own generation
    constraint: addition_no_carry needs a + b <= 9 (no carry); subtraction_no_borrow
    needs a >= b (matches generate()'s own a < b swap; single digits can't borrow)."""
    if skill == "addition_no_carry":
        return [(a, b) for a in range(10) for b in range(10) if a + b <= 9]
    if skill == "subtraction_no_borrow":
        return [(a, b) for a in range(10) for b in range(10) if a >= b]
    raise ValueError(f"{skill!r} has no 1-digit combo space")


def is_trivial(skill: str, combo: tuple[int, int]) -> bool:
    """A combo where no real computation happens: an operand is 0 for
    addition (e.g. 7 + 0), or the subtrahend is 0 or equals the minuend for
    subtraction (e.g. 7 - 0 or 5 - 5, both answer without borrowing logic)."""
    a, b = combo
    if skill == "addition_no_carry":
        return a == 0 or b == 0
    if skill == "subtraction_no_borrow":
        return b == 0 or a == b
    raise ValueError(f"{skill!r} has no trivial/non-trivial split")


def pick_combo(
    skill: str,
    seen: list | set,
    want_trivial: bool | None,
    rng: random.Random,
) -> tuple[int, int]:
    """Choose an operand pair not in `seen`. Coverage-without-repeats is a
    selection heuristic, not a hard gate: if every combo in the requested
    trivial/non-trivial bucket has been shown, fall back to any unseen combo
    regardless of bucket; if the whole space has been shown, repeats become
    acceptable rather than raising (reachable only after a very long stay at
    the narrowest tier)."""
    seen_set = {tuple(c) for c in seen}
    candidates = [c for c in all_combos(skill) if c not in seen_set]
    if want_trivial is not None:
        bucketed = [c for c in candidates if is_trivial(skill, c) == want_trivial]
        if bucketed:
            candidates = bucketed
    if not candidates:
        candidates = all_combos(skill)
    return rng.choice(candidates)


def advance_digit_level(
    skill: str,
    digit_level: dict[str, int],
    digit_level_run: dict[str, int],
    seen_combos: dict[str, list],
    correct: bool,
    combo: tuple[int, int] | None,
) -> dict:
    """The one function that decides whether `skill`'s digit-width advances.

    Called once per signal-bearing answer (correct or wrong), regardless of
    the `digit_reversal` mastery exception — digit-width tracking is a
    separate axis from BKT mastery, so it is not gated by that check. Returns
    only the state keys that changed, matching the partial-update-dict
    convention `update_mastery_node` already returns for `mastery_run`.
    """
    ladder = WIDTH_LADDER.get(skill)
    if ladder is None:
        return {}

    level = digit_level.get(skill, 0)
    run = digit_level_run.get(skill, 0)

    if not (skill in NARROWEST_TIER_SKILLS and level == 0):
        # General case: flat LEVEL_UP_RUN-in-a-row rule, any width > 1 (or a
        # skill that never has a 1-digit tier at all).
        if not correct:
            return {"digit_level_run": {**digit_level_run, skill: 0}}
        new_run = run + 1
        if new_run >= LEVEL_UP_RUN and level + 1 < len(ladder):
            return {
                "digit_level": {**digit_level, skill: level + 1},
                "digit_level_run": {**digit_level_run, skill: 0},
            }
        return {"digit_level_run": {**digit_level_run, skill: new_run}}

    # Narrowest tier: addition_no_carry / subtraction_no_borrow at digit_level 0.
    seen_set = {tuple(c) for c in seen_combos.get(skill, [])}

    if not correct:
        # The run resets so the escalating pair must be shown fresh, trivial
        # first, again — but seen_combos persists for the rest of the stay at
        # this tier.
        return {"digit_level_run": {**digit_level_run, skill: 0}}

    new_seen_set = set(seen_set)
    if combo is not None:
        new_seen_set.add(combo)
    seen_update = {**seen_combos, skill: [list(c) for c in new_seen_set]}

    # Base gate: 2 consecutive correct 1-digit answers, escalating
    # trivial-then-non-trivial.
    new_run = run + 1
    if new_run >= NARROW_TIER_BASE_RUN and level + 1 < len(ladder):
        return {
            "seen_combos": seen_update,
            "digit_level": {**digit_level, skill: level + 1},
            "digit_level_run": {**digit_level_run, skill: 0},
        }
    return {"seen_combos": seen_update, "digit_level_run": {**digit_level_run, skill: new_run}}
