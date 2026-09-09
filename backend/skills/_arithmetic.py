"""Shared digit-column arithmetic helpers used by the skill template modules.

Kept separate from any one skill so addition and subtraction templates (and,
later, the bug-rule detectors in the BKT task) apply carry/borrow logic and
difficulty bucketing consistently instead of each re-deriving it.

Every generated problem's `question` is a canonical "<a> <op> <b>" string
(e.g. "47 + 38") with no other formatting — `parse_operands` depends on
that, and so will the bug-rule detectors added in the next task, since
`Problem` has no separate operand fields. Anything that later wraps a
problem in narrative text (the word-problem-flavor LLM touchpoint) must not
overwrite this canonical string, or operand recovery breaks.
"""

import random
import re
from typing import Literal

_QUESTION_RE = re.compile(r"^(\d+)\s*([+-])\s*(\d+)$")

# Shared default RNG so skill `generate()` functions don't each need to stand
# up their own, while still accepting an explicit `rng` for deterministic tests.
default_rng = random.Random()


def digits(n: int, width: int) -> list[int]:
    """Least-significant-digit-first list of `n`'s digits, padded to `width`."""
    return [(n // (10**i)) % 10 for i in range(width)]


def random_n_digit(rng: random.Random, n: int) -> int:
    """A random integer with exactly `n` digits (no leading zero for n >= 2)."""
    if n <= 1:
        return rng.randint(0, 9)
    return rng.randint(10 ** (n - 1), 10**n - 1)


def has_any_carry(a: int, b: int, width: int | None = None) -> bool:
    """True if adding `a` + `b` requires carrying in at least one column."""
    if width is None:
        width = max(len(str(a)), len(str(b)))
    da, db = digits(a, width), digits(b, width)
    carry = 0
    for da_i, db_i in zip(da, db):
        total = da_i + db_i + carry
        if total >= 10:
            return True
        carry = 0
    return False


def has_any_borrow(a: int, b: int, width: int | None = None) -> bool:
    """True if subtracting `a` - `b` (a >= b) requires borrowing in at least one column."""
    if a < b:
        raise ValueError("has_any_borrow expects a >= b")
    if width is None:
        width = max(len(str(a)), len(str(b)))
    da, db = digits(a, width), digits(b, width)
    borrow = 0
    for da_i, db_i in zip(da, db):
        if da_i - borrow < db_i:
            return True
        borrow = 0
    return False


def format_question(a: int, op: Literal["+", "-"], b: int) -> str:
    return f"{a} {op} {b}"


def parse_operands(question: str) -> tuple[int, str, int]:
    """Recover (a, op, b) from a canonical question string. Raises ValueError if malformed."""
    match = _QUESTION_RE.match(question.strip())
    if not match:
        raise ValueError(f"question {question!r} is not in canonical 'a <op> b' form")
    a_str, op, b_str = match.groups()
    return int(a_str), op, int(b_str)


def bucket(difficulty: float) -> Literal["easy", "medium", "hard"]:
    """Shared difficulty thresholds so every skill buckets the same way."""
    if difficulty < 0.4:
        return "easy"
    if difficulty < 0.7:
        return "medium"
    return "hard"
