import random

from backend.skills._difficulty_ladder import (
    LEVEL_UP_RUN,
    NARROWEST_TIER_SKILLS,
    WIDTH_LADDER,
    advance_digit_level,
    all_combos,
    is_trivial,
    pick_combo,
)


def _advance(skill, correct, combo=None, **state):
    defaults = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
    defaults.update(state)
    return advance_digit_level(
        skill=skill,
        correct=correct,
        combo=combo,
        **defaults,
    )


def test_general_case_levels_up_after_three_correct():
    skill = "addition_carry"  # starts at tier 0 = width 2, not a narrowest-tier skill
    digit_level: dict = {}
    digit_level_run: dict = {}
    for i in range(LEVEL_UP_RUN):
        updates = _advance(skill, True, digit_level=digit_level, digit_level_run=digit_level_run)
        digit_level = updates.get("digit_level", digit_level)
        digit_level_run = updates.get("digit_level_run", digit_level_run)
        if i < LEVEL_UP_RUN - 1:
            assert digit_level.get(skill, 0) == 0
    assert digit_level[skill] == 1


def test_general_case_fewer_than_three_correct_does_not_level_up():
    skill = "addition_carry"
    digit_level: dict = {}
    digit_level_run: dict = {}
    for _ in range(LEVEL_UP_RUN - 1):
        updates = _advance(skill, True, digit_level=digit_level, digit_level_run=digit_level_run)
        digit_level = updates.get("digit_level", digit_level)
        digit_level_run = updates.get("digit_level_run", digit_level_run)
    assert digit_level.get(skill, 0) == 0


def test_general_case_wrong_answer_resets_run():
    skill = "addition_carry"
    digit_level: dict = {}
    digit_level_run: dict = {}
    for correct in [True, True, False, True, True]:
        updates = _advance(skill, correct, digit_level=digit_level, digit_level_run=digit_level_run)
        digit_level = updates.get("digit_level", digit_level)
        digit_level_run = updates.get("digit_level_run", digit_level_run)
    assert digit_level.get(skill, 0) == 0
    # this is a distinct counter from mastery_run entirely
    assert "mastery_run" not in updates


def test_general_case_top_tier_has_no_next_level():
    skill = "addition_carry"
    assert len(WIDTH_LADDER[skill]) == 2
    digit_level = {skill: 1}  # already at the top tier (width 3)
    digit_level_run: dict = {}
    for _ in range(LEVEL_UP_RUN + 2):
        updates = _advance(skill, True, digit_level=digit_level, digit_level_run=digit_level_run)
        digit_level = updates.get("digit_level", digit_level)
        digit_level_run = updates.get("digit_level_run", digit_level_run)
    assert digit_level[skill] == 1  # never raises, never exceeds the top tier


def test_narrowest_tier_base_gate_requires_trivial_then_nontrivial():
    skill = "addition_no_carry"
    trivial = (7, 0)
    non_trivial = (4, 6)
    assert is_trivial(skill, trivial) is True
    assert is_trivial(skill, non_trivial) is False

    state = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
    updates = _advance(skill, True, combo=trivial, **state)
    state["digit_level_run"] = updates["digit_level_run"]
    state["seen_combos"] = updates["seen_combos"]
    assert state["digit_level_run"].get(skill, 0) == 1
    assert "digit_level" not in updates

    updates = _advance(skill, True, combo=non_trivial, **state)
    assert updates["digit_level"][skill] == 1


def test_narrowest_tier_base_gate_counts_any_two_correct_in_a_row():
    # advance_digit_level trusts the caller (generate_problem's combo_hint,
    # via _combo_hint_for) to have actually shaped the pair trivial-then-
    # non-trivial; it only counts correct-in-a-row, so two trivial combos
    # answered correctly back-to-back still reach the NARROW_TIER_BASE_RUN=2 gate.
    skill = "subtraction_no_borrow"
    state = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
    updates = _advance(skill, True, combo=(5, 0), **state)
    state["digit_level_run"] = updates["digit_level_run"]
    state["seen_combos"] = updates["seen_combos"]
    updates = _advance(skill, True, combo=(3, 0), **state)
    assert updates["digit_level"][skill] == 1


def test_narrowest_tier_wrong_answer_resets_run_but_keeps_seen_combos():
    skill = "addition_no_carry"
    state = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
    updates = _advance(skill, True, combo=(7, 0), **state)
    state["digit_level_run"] = updates["digit_level_run"]
    state["seen_combos"] = updates["seen_combos"]
    assert state["digit_level_run"][skill] == 1

    updates = _advance(skill, False, combo=(4, 6), **state)
    assert updates["digit_level_run"][skill] == 0
    assert "seen_combos" not in updates  # unchanged on a wrong answer


def test_addition_carry_and_subtraction_borrow_skip_narrowest_tier_logic():
    for skill in ["addition_carry", "subtraction_borrow"]:
        assert skill not in NARROWEST_TIER_SKILLS
        state = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
        # A combo argument is ignored: only the flat run-length rule applies,
        # even at this skill's own tier 0.
        updates = _advance(skill, True, combo=(1, 2), **state)
        assert "seen_combos" not in updates
        assert updates["digit_level_run"][skill] == 1


def test_seen_combos_avoids_repeats_but_does_not_gate_advancement():
    skill = "addition_no_carry"
    rng = random.Random(42)
    seen: set[tuple[int, int]] = set()
    for _ in range(30):
        combo = pick_combo(skill, seen, None, rng)
        assert combo not in seen
        seen.add(combo)

    # A student can advance via the base gate without exhausting the space.
    state = {"digit_level": {}, "digit_level_run": {}, "seen_combos": {}}
    updates = _advance(skill, True, combo=(7, 0), **state)
    state["digit_level_run"] = updates["digit_level_run"]
    state["seen_combos"] = updates["seen_combos"]
    updates = _advance(skill, True, combo=(4, 6), **state)
    assert updates["digit_level"][skill] == 1


def test_pick_combo_falls_back_when_bucket_exhausted():
    skill = "addition_no_carry"
    rng = random.Random(1)
    trivial_combos = {c for c in all_combos(skill) if is_trivial(skill, c)}
    combo = pick_combo(skill, trivial_combos, True, rng)
    # every trivial combo already seen -> falls back to a non-trivial one
    assert not is_trivial(skill, combo)


def test_pick_combo_falls_back_to_repeats_once_space_exhausted():
    skill = "addition_no_carry"
    rng = random.Random(2)
    everything = set(all_combos(skill))
    combo = pick_combo(skill, everything, None, rng)
    assert combo in everything  # repeats become acceptable, not a crash
