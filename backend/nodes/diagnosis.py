"""The `grade_and_diagnose` node: deterministic grading + misconception detection.

No LLM call here — grading and bug-rule diagnosis must be pure per the
project's hard constraints.

Interim stopgap: hint/visual copy lives in `_HINT_BY_BUG_TYPE` below (ported
from the frontend's old constants.js) until Part 2/3 replaces it with
backend/content/misconceptions.json. This function's contract doesn't change
when that happens.
"""

from backend.models.state import DiagnosisResult, Problem
from backend.skills import addition_carry, addition_no_carry, subtraction_borrow, subtraction_no_borrow

_BUG_RULES = {
    addition_no_carry.SKILL_TAG: addition_no_carry.BUG_RULES,
    addition_carry.SKILL_TAG: addition_carry.BUG_RULES,
    subtraction_no_borrow.SKILL_TAG: subtraction_no_borrow.BUG_RULES,
    subtraction_borrow.SKILL_TAG: subtraction_borrow.BUG_RULES,
}

_HINT_BY_BUG_TYPE = {
    "no_carry": "Remember to carry the extra ten into the next column!",
    "reversed_operands": "Careful — subtract the second number from the first, not the other way around.",
    "no_borrow_smaller_from_larger": (
        "When the top digit is smaller, borrow from the next column instead of just taking the difference."
    ),
    "off_by_ten_in_borrow": "You're close! Double-check the column where you borrowed — it's off by ten.",
    "unclassified": "Let's redo this one column at a time. Start with the ones.",
}


def grade_and_diagnose(problem: Problem, answer: int, attempt: int) -> DiagnosisResult:
    """Grade `answer` against `problem` and diagnose the misconception if wrong.

    Callers are responsible for routing non-signal submissions (blank answers,
    rapid guesses) away before calling this — it always assumes a real,
    signal-bearing attempt.
    """
    attempts_remaining = max(0, 3 - attempt)

    if answer == problem.correct_answer:
        return DiagnosisResult(problem_id=problem.problem_id, correct=True, attempts_remaining=attempts_remaining)

    try:
        bug_rules = _BUG_RULES[problem.skill_tag]
    except KeyError:
        raise ValueError(f"unknown skill tag: {problem.skill_tag!r} (known: {sorted(_BUG_RULES)})") from None

    bug_type = "unclassified"
    for candidate_bug_type, detector in bug_rules:
        if detector(problem, answer):
            bug_type = candidate_bug_type
            break

    reveal_answer = attempt >= 3
    visual = f"base10_blocks/{bug_type}" if attempt >= 2 else None

    return DiagnosisResult(
        problem_id=problem.problem_id,
        correct=False,
        bug_type=bug_type,
        hint=_HINT_BY_BUG_TYPE.get(bug_type),
        visual=visual,
        attempts_remaining=attempts_remaining,
        reveal_answer=reveal_answer,
    )
