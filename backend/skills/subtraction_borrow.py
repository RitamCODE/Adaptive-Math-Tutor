"""Subtraction with borrowing."""

import random

from backend.models.state import Problem
from backend.skills._arithmetic import (
    bucket,
    default_rng,
    digits,
    format_question,
    has_any_borrow,
    parse_operands,
    random_n_digit,
)

SKILL_TAG = "subtraction_borrow"


def detect_reversed_operands(problem: Problem, answer: int) -> bool:
    """Answer equals b - a instead of a - b."""
    a, _op, b = parse_operands(problem.question)
    reversed_answer = b - a
    return answer == reversed_answer and reversed_answer != problem.correct_answer


def detect_no_borrow_smaller_from_larger(problem: Problem, answer: int) -> bool:
    """Answer matches subtracting digit-wise with abs() on each column
    instead of borrowing from the next place."""
    a, _op, b = parse_operands(problem.question)
    width = max(len(str(a)), len(str(b)))
    buggy_digits = [abs(da - db) for da, db in zip(digits(a, width), digits(b, width))]
    buggy_answer = sum(d * 10**i for i, d in enumerate(buggy_digits))
    return answer == buggy_answer and buggy_answer != problem.correct_answer


def detect_off_by_ten_in_borrow(problem: Problem, answer: int) -> bool:
    """Answer is exactly 10 off from the correct result — a slip in the
    borrowed place (every problem this skill generates requires a borrow)."""
    return abs(answer - problem.correct_answer) == 10


BUG_RULES: list[tuple[str, object]] = [
    ("reversed_operands", detect_reversed_operands),
    ("no_borrow_smaller_from_larger", detect_no_borrow_smaller_from_larger),
    ("off_by_ten_in_borrow", detect_off_by_ten_in_borrow),
]

_WIDTH_BY_BUCKET = {"easy": 2, "medium": 2, "hard": 3}
_MAX_ATTEMPTS = 200


def generate(difficulty: float, rng: random.Random | None = None) -> Problem:
    rng = rng or default_rng
    width = _WIDTH_BY_BUCKET[bucket(difficulty)]
    for _ in range(_MAX_ATTEMPTS):
        a = random_n_digit(rng, width)
        b = random_n_digit(rng, width)
        if a < b:
            a, b = b, a
        if a != b and has_any_borrow(a, b, width):
            return Problem(
                question=format_question(a, "-", b),
                correct_answer=a - b,
                skill_tag=SKILL_TAG,
                difficulty=difficulty,
            )
    raise RuntimeError(f"{SKILL_TAG}: failed to generate a borrowing problem at difficulty={difficulty}")
