"""Addition with carrying.

Bug-rule detectors (e.g. `detect_no_carry`) belong to the "BKT + bug rules"
task and will be added to `BUG_RULES` there — this task only builds the
problem template.
"""

import random

from backend.models.state import Problem
from backend.skills._arithmetic import bucket, default_rng, format_question, has_any_carry, random_n_digit

SKILL_TAG = "addition_carry"
BUG_RULES: list[tuple[str, object]] = []

_WIDTH_BY_BUCKET = {"easy": 2, "medium": 2, "hard": 3}
_MAX_ATTEMPTS = 200


def generate(difficulty: float, rng: random.Random | None = None) -> Problem:
    rng = rng or default_rng
    width = _WIDTH_BY_BUCKET[bucket(difficulty)]
    for _ in range(_MAX_ATTEMPTS):
        a = random_n_digit(rng, width)
        b = random_n_digit(rng, width)
        if has_any_carry(a, b, width):
            return Problem(
                question=format_question(a, "+", b),
                correct_answer=a + b,
                skill_tag=SKILL_TAG,
                difficulty=difficulty,
            )
    raise RuntimeError(f"{SKILL_TAG}: failed to generate a carrying problem at difficulty={difficulty}")
