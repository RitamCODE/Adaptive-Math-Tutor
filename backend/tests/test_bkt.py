import pytest

from backend.models.bkt import BKTParams, update_mastery

PARAMS = BKTParams()


def test_correct_update_matches_hand_computed_value():
    result = update_mastery({"addition_carry": 0.3}, "addition_carry", True, PARAMS)
    assert result["addition_carry"] == pytest.approx(0.9024590163934426)


def test_incorrect_update_matches_hand_computed_value():
    result = update_mastery({"addition_carry": 0.3}, "addition_carry", False, PARAMS)
    assert result["addition_carry"] == pytest.approx(0.1866906474820144)


def test_new_skill_starts_from_p_init():
    result = update_mastery({}, "addition_carry", True, PARAMS)
    assert result["addition_carry"] == pytest.approx(0.9024590163934426)


def test_update_does_not_mutate_input_and_preserves_other_skills():
    mastery = {"addition_carry": 0.3, "subtraction_borrow": 0.5}
    result = update_mastery(mastery, "addition_carry", True, PARAMS)

    assert mastery == {"addition_carry": 0.3, "subtraction_borrow": 0.5}
    assert result is not mastery
    assert result["subtraction_borrow"] == 0.5
    assert result["addition_carry"] != 0.3


def test_repeated_correct_answers_increase_mastery_toward_one():
    mastery: dict[str, float] = {}
    values = []
    for _ in range(10):
        mastery = update_mastery(mastery, "addition_carry", True, PARAMS)
        values.append(mastery["addition_carry"])

    assert values == sorted(values)
    assert values[-1] < 1.0
    assert values[-1] > values[0]


def test_repeated_incorrect_answers_stay_bounded_and_converge():
    mastery: dict[str, float] = {"addition_carry": 0.9}
    for _ in range(50):
        mastery = update_mastery(mastery, "addition_carry", False, PARAMS)

    final = mastery["addition_carry"]
    assert 0.0 < final < 1.0

    next_mastery = update_mastery(mastery, "addition_carry", False, PARAMS)
    assert next_mastery["addition_carry"] == pytest.approx(final, abs=1e-6)
