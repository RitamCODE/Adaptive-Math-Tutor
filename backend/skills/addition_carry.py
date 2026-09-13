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


def detect_add_concat_no_carry(problem: Problem, answer: int) -> bool:
    """Each column summed correctly (no mod-10 cap), then the per-column sums
    are concatenated as decimal strings in ones-then-tens-then-... order
    instead of being carried and added positionally. 86 + 94 -> ones 6+4=10,
    tens 8+9=17 -> "10"+"17" -> 1017."""
    a, _op, b = parse_operands(problem.question)
    width = max(len(str(a)), len(str(b)))
    column_sums = [da + db for da, db in zip(digits(a, width), digits(b, width))]
    buggy_str = "".join(str(s) for s in column_sums)
    if not buggy_str:
        return False
    buggy_answer = int(buggy_str)
    return answer == buggy_answer and buggy_answer != problem.correct_answer


def detect_no_carry(problem: Problem, answer: int) -> bool:
    """Answer matches digit-wise addition with each column truncated mod 10
    instead of carrying the overflow into the next place."""
    a, _op, b = parse_operands(problem.question)
    width = max(len(str(a)), len(str(b)))
    buggy_digits = [(da + db) % 10 for da, db in zip(digits(a, width), digits(b, width))]
    buggy_answer = sum(d * 10**i for i, d in enumerate(buggy_digits))
    return answer == buggy_answer and buggy_answer != problem.correct_answer


def detect_add_carry_wrong_column(problem: Problem, answer: int) -> bool:
    """The carry out of the ones column gets credited at the ones' place
    value (1) instead of the tens' (10) — the total comes out exactly 9 low.
    Only models the ones-to-tens hop, gated on that column actually
    overflowing."""
    a, _op, b = parse_operands(problem.question)
    if (a % 10 + b % 10) < 10:
        return False
    buggy_answer = problem.correct_answer - 9
    return answer == buggy_answer and buggy_answer != problem.correct_answer


def detect_add_off_by_one(problem: Problem, answer: int) -> bool:
    """Counting-on error: answer is one away from correct."""
    return abs(answer - problem.correct_answer) == 1


def detect_add_used_subtraction(problem: Problem, answer: int) -> bool:
    """Operator misread: answer is |a - b| instead of a + b. abs() because
    the number pad has no minus key, so a negative submission can't happen."""
    a, _op, b = parse_operands(problem.question)
    buggy_answer = abs(a - b)
    return answer == buggy_answer and buggy_answer != problem.correct_answer


BUG_RULES: list[tuple[str, object]] = [
    ("add_concat_no_carry", detect_add_concat_no_carry),
    ("add_carry_wrong_column", detect_add_carry_wrong_column),
    ("no_carry", detect_no_carry),
    ("add_off_by_one", detect_add_off_by_one),
    ("add_used_subtraction", detect_add_used_subtraction),
]

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
