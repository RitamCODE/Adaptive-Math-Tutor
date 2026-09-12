import pytest

from backend.models.state import Problem
from backend.nodes.diagnosis import grade_and_diagnose
from backend.skills._arithmetic import has_any_borrow, has_any_carry
from backend.skills.addition_carry import detect_no_carry
from backend.skills.subtraction_borrow import (
    detect_no_borrow_smaller_from_larger,
    detect_off_by_ten_in_borrow,
    detect_reversed_operands,
)

ADDITION_PROBLEM = Problem(
    question="47 + 38",
    correct_answer=85,
    skill_tag="addition_carry",
    difficulty=0.5,
)

SUBTRACTION_PROBLEM = Problem(
    question="72 - 48",
    correct_answer=24,
    skill_tag="subtraction_borrow",
    difficulty=0.5,
)


def test_addition_problem_requires_carry():
    assert has_any_carry(47, 38)


def test_detect_no_carry_fires_on_digitwise_mod_ten_sum():
    # units: 7+8=15 -> 5 (truncated); tens: 4+3=7 -> buggy answer 75
    assert detect_no_carry(ADDITION_PROBLEM, 75) is True
    assert detect_no_carry(ADDITION_PROBLEM, 85) is False


def test_grade_and_diagnose_addition_correct():
    result = grade_and_diagnose(ADDITION_PROBLEM, 85, attempt=1)
    assert result.correct is True
    assert result.bug_type is None


def test_grade_and_diagnose_addition_no_carry_bug():
    result = grade_and_diagnose(ADDITION_PROBLEM, 75, attempt=1)
    assert result.correct is False
    assert result.bug_type == "no_carry"


def test_subtraction_problem_requires_borrow():
    assert has_any_borrow(72, 48)


def test_detect_reversed_operands():
    assert detect_reversed_operands(SUBTRACTION_PROBLEM, -24) is True
    assert detect_reversed_operands(SUBTRACTION_PROBLEM, 24) is False


def test_detect_no_borrow_smaller_from_larger():
    # units: |2-8|=6; tens: |7-4|=3 -> buggy answer 36
    assert detect_no_borrow_smaller_from_larger(SUBTRACTION_PROBLEM, 36) is True
    assert detect_no_borrow_smaller_from_larger(SUBTRACTION_PROBLEM, 24) is False


def test_detect_off_by_ten_in_borrow():
    assert detect_off_by_ten_in_borrow(SUBTRACTION_PROBLEM, 34) is True
    assert detect_off_by_ten_in_borrow(SUBTRACTION_PROBLEM, 14) is True
    assert detect_off_by_ten_in_borrow(SUBTRACTION_PROBLEM, 24) is False


def test_grade_and_diagnose_subtraction_correct():
    result = grade_and_diagnose(SUBTRACTION_PROBLEM, 24, attempt=1)
    assert result.correct is True
    assert result.bug_type is None


def test_grade_and_diagnose_subtraction_reversed_operands():
    result = grade_and_diagnose(SUBTRACTION_PROBLEM, -24, attempt=1)
    assert result.correct is False
    assert result.bug_type == "reversed_operands"


def test_grade_and_diagnose_subtraction_no_borrow_bug():
    result = grade_and_diagnose(SUBTRACTION_PROBLEM, 36, attempt=1)
    assert result.correct is False
    assert result.bug_type == "no_borrow_smaller_from_larger"


def test_grade_and_diagnose_subtraction_off_by_ten_bug():
    result = grade_and_diagnose(SUBTRACTION_PROBLEM, 34, attempt=1)
    assert result.correct is False
    assert result.bug_type == "off_by_ten_in_borrow"


def test_grade_and_diagnose_unmatched_wrong_answer_is_unclassified():
    result = grade_and_diagnose(SUBTRACTION_PROBLEM, 999, attempt=1)
    assert result.correct is False
    assert result.bug_type == "unclassified"
    assert result.hint is not None


def test_grade_and_diagnose_unknown_skill_raises():
    bad_problem = Problem(question="1 + 1", correct_answer=2, skill_tag="multiplication_basic", difficulty=0.5)
    with pytest.raises(ValueError):
        grade_and_diagnose(bad_problem, 3, attempt=1)


def test_grade_and_diagnose_reveals_answer_only_on_attempt_three():
    attempt_1 = grade_and_diagnose(ADDITION_PROBLEM, 75, attempt=1)
    attempt_2 = grade_and_diagnose(ADDITION_PROBLEM, 75, attempt=2)
    attempt_3 = grade_and_diagnose(ADDITION_PROBLEM, 75, attempt=3)
    assert attempt_1.reveal_answer is False
    assert attempt_1.visual is None
    assert attempt_2.reveal_answer is False
    assert attempt_2.visual is not None
    assert attempt_3.reveal_answer is True
