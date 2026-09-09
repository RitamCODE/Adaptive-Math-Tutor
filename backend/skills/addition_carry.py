"""Addition with carrying."""

import random

from backend.models.state import Problem
from backend.skills._arithmetic import (
    bucket,
    default_rng,
    digits,
    format_question,
    has_any_carry,
    parse_operands,
    random_n_digit,
)

SKILL_TAG = "addition_carry"


def detect_no_carry(problem: Problem, answer: int) -> bool:
    """Answer matches digit-wise addition with each column truncated mod 10
    instead of carrying the overflow into the next place."""
    a, _op, b = parse_operands(problem.question)
    width = max(len(str(a)), len(str(b)))
    buggy_digits = [(da + db) % 10 for da, db in zip(digits(a, width), digits(b, width))]
    buggy_answer = sum(d * 10**i for i, d in enumerate(buggy_digits))
    return answer == buggy_answer and buggy_answer != problem.correct_answer


BUG_RULES: list[tuple[str, object]] = [("no_carry", detect_no_carry)]

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
