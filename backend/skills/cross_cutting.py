"""Skill-agnostic bug rules, checked after a skill's own BUG_RULES fail to
match (see CLAUDE.md's "Cross-cutting" section). Unlike the per-skill
detectors, these only look at the submitted answer and the correct answer —
they don't need to parse the operands, so they apply to any skill.
"""

from backend.models.state import Problem


def detect_digit_reversal(problem: Problem, answer: int) -> bool:
    """Answer is the digit-reversal of the correct one (51 instead of 15).
    Not an arithmetic error — the caller must not penalize mastery for this."""
    if answer == problem.correct_answer or answer < 0:
        return False
    reversed_answer = int(str(problem.correct_answer)[::-1])
    return answer == reversed_answer


def detect_place_value_confusion(problem: Problem, answer: int) -> bool:
    """Answer is the correct one scaled by an exact power of ten."""
    correct = problem.correct_answer
    if answer == 0 or correct == 0 or answer == correct:
        return False
    for power in (10, 100, 1000):
        if answer == correct * power:
            return True
        if correct % power == 0 and answer == correct // power:
            return True
    return False


BUG_RULES: list[tuple[str, object]] = [
    ("digit_reversal", detect_digit_reversal),
    ("place_value_confusion", detect_place_value_confusion),
]
