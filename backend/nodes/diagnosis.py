"""The `grade_and_diagnose` node: deterministic grading + misconception detection.

No LLM call here — grading and bug-rule diagnosis must be pure per the
project's hard constraints.
"""

from backend.models.state import DiagnosisResult, Problem
from backend.skills import addition_carry, addition_no_carry, subtraction_borrow, subtraction_no_borrow

_BUG_RULES = {
    addition_no_carry.SKILL_TAG: addition_no_carry.BUG_RULES,
    addition_carry.SKILL_TAG: addition_carry.BUG_RULES,
    subtraction_no_borrow.SKILL_TAG: subtraction_no_borrow.BUG_RULES,
    subtraction_borrow.SKILL_TAG: subtraction_borrow.BUG_RULES,
}


def grade_and_diagnose(problem: Problem, answer: int) -> DiagnosisResult:
    if answer == problem.correct_answer:
        return DiagnosisResult(correct=True)

    try:
        bug_rules = _BUG_RULES[problem.skill_tag]
    except KeyError:
        raise ValueError(f"unknown skill tag: {problem.skill_tag!r} (known: {sorted(_BUG_RULES)})") from None

    for bug_type, detector in bug_rules:
        if detector(problem, answer):
            return DiagnosisResult(correct=False, bug_type=bug_type)

    return DiagnosisResult(correct=False)
