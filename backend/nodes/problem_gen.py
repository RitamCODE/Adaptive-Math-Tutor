"""The `generate_problem` node: dispatches to the right skill's template generator.

No LLM call here — the optional word-problem-flavor wrapper (LLM touchpoint
#1 in CLAUDE.md) is a separate, later addition that would wrap this node's
plain numeric output, not replace it.
"""

from backend.models.state import Problem
from backend.skills import addition_carry, addition_no_carry, subtraction_borrow, subtraction_no_borrow

_GENERATORS = {
    addition_no_carry.SKILL_TAG: addition_no_carry.generate,
    addition_carry.SKILL_TAG: addition_carry.generate,
    subtraction_no_borrow.SKILL_TAG: subtraction_no_borrow.generate,
    subtraction_borrow.SKILL_TAG: subtraction_borrow.generate,
}


def generate_problem(skill: str, difficulty: float) -> Problem:
    try:
        generator = _GENERATORS[skill]
    except KeyError:
        raise ValueError(f"unknown skill tag: {skill!r} (known: {sorted(_GENERATORS)})") from None
    return generator(difficulty)
