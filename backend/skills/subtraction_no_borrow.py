"""Subtraction with no borrowing — prerequisite skill for `subtraction_borrow`.

No bug-rule detectors: CLAUDE.md only specifies misconception rules for
addition_carry and subtraction_borrow. Wrong answers on this skill are just
graded correct/incorrect.
"""

import random

from backend.models.state import Problem
from backend.skills._arithmetic import bucket, default_rng, format_question, has_any_borrow, random_n_digit
from backend.skills._difficulty_ladder import pick_combo

SKILL_TAG = "subtraction_no_borrow"
BUG_RULES: list[tuple[str, object]] = []

_WIDTH_BY_BUCKET = {"easy": 1, "medium": 2, "hard": 3}
_MAX_ATTEMPTS = 200


def generate(difficulty: float, rng: random.Random | None = None, combo_hint: dict | None = None) -> Problem:
    rng = rng or default_rng
    width = _WIDTH_BY_BUCKET[bucket(difficulty)]
    if width == 1 and combo_hint is not None:
        a, b = pick_combo(SKILL_TAG, combo_hint.get("seen", []), combo_hint.get("want_trivial"), rng)
        return Problem(question=format_question(a, "-", b), correct_answer=a - b, skill_tag=SKILL_TAG, difficulty=difficulty)
    for _ in range(_MAX_ATTEMPTS):
        a = random_n_digit(rng, width)
        b = random_n_digit(rng, width)
        if a < b:
            a, b = b, a
        if not has_any_borrow(a, b, width):
            return Problem(
                question=format_question(a, "-", b),
                correct_answer=a - b,
                skill_tag=SKILL_TAG,
                difficulty=difficulty,
            )
    raise RuntimeError(f"{SKILL_TAG}: failed to generate a no-borrow problem at difficulty={difficulty}")
