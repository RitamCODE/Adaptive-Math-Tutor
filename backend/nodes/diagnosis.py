"""The `grade_and_diagnose` node: deterministic grading + misconception detection.

No LLM call here — grading and bug-rule diagnosis must be pure per the
project's hard constraints.

Hint/visual copy lives in backend/content/misconceptions.json, keyed by
bug_type ("Detectors are code, copy is data" per CLAUDE.md) — adding or
retuning a hint never touches this file.
"""

import json
from pathlib import Path

from backend.models.state import DiagnosisResult, Problem
from backend.skills import addition_carry, addition_no_carry, cross_cutting, subtraction_borrow, subtraction_no_borrow

_BUG_RULES = {
    addition_no_carry.SKILL_TAG: addition_no_carry.BUG_RULES,
    addition_carry.SKILL_TAG: addition_carry.BUG_RULES,
    subtraction_no_borrow.SKILL_TAG: subtraction_no_borrow.BUG_RULES,
    subtraction_borrow.SKILL_TAG: subtraction_borrow.BUG_RULES,
}

_MISCONCEPTIONS_PATH = Path(__file__).resolve().parent.parent / "content" / "misconceptions.json"
_MISCONCEPTIONS: dict[str, dict[str, str]] = json.loads(_MISCONCEPTIONS_PATH.read_text())


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
    for candidate_bug_type, detector in [*bug_rules, *cross_cutting.BUG_RULES]:
        if detector(problem, answer):
            bug_type = candidate_bug_type
            break

    entry = _MISCONCEPTIONS[bug_type]
    reveal_answer = attempt >= 3
    visual = entry["visual"] if attempt >= 2 else None

    return DiagnosisResult(
        problem_id=problem.problem_id,
        correct=False,
        bug_type=bug_type,
        hint=entry["hint"],
        visual=visual,
        attempts_remaining=attempts_remaining,
        reveal_answer=reveal_answer,
    )
