import random

import pytest

from backend.nodes.problem_gen import generate_problem
from backend.skills import addition_carry, addition_no_carry, subtraction_borrow, subtraction_no_borrow
from backend.skills._arithmetic import has_any_borrow, has_any_carry, parse_operands

DIFFICULTIES = [0.2, 0.5, 0.8]  # easy, medium, hard buckets

_ADDITION_SKILLS = {
    addition_no_carry.SKILL_TAG: (addition_no_carry.generate, False),
    addition_carry.SKILL_TAG: (addition_carry.generate, True),
}
_SUBTRACTION_SKILLS = {
    subtraction_no_borrow.SKILL_TAG: (subtraction_no_borrow.generate, False),
    subtraction_borrow.SKILL_TAG: (subtraction_borrow.generate, True),
}
ALL_SKILLS = {**_ADDITION_SKILLS, **_SUBTRACTION_SKILLS}


@pytest.mark.parametrize("skill_tag", ALL_SKILLS.keys())
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_generate_is_valid_and_auto_gradable_across_many_trials(skill_tag, difficulty):
    generate_fn, expect_carry_or_borrow = ALL_SKILLS[skill_tag]
    rng = random.Random(1234)  # fixed seed for reproducibility across trials

    for _ in range(30):
        problem = generate_fn(difficulty, rng=rng)

        assert problem.skill_tag == skill_tag
        assert problem.difficulty == difficulty

        a, op, b = parse_operands(problem.question)
        assert op in ("+", "-")

        if op == "+":
            assert problem.correct_answer == a + b
            assert has_any_carry(a, b) is expect_carry_or_borrow
        else:
            assert a >= b, "subtraction problems must not go negative"
            assert problem.correct_answer == a - b
            assert has_any_borrow(a, b) is expect_carry_or_borrow


@pytest.mark.parametrize("skill_tag", ALL_SKILLS.keys())
@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_generate_problem_node_dispatches_correctly(skill_tag, difficulty):
    problem = generate_problem(skill_tag, difficulty)
    assert problem.skill_tag == skill_tag
    assert problem.difficulty == difficulty
    a, op, b = parse_operands(problem.question)
    expected = a + b if op == "+" else a - b
    assert problem.correct_answer == expected


def test_generate_problem_rejects_unknown_skill():
    with pytest.raises(ValueError):
        generate_problem("multiplication_basic", 0.5)
