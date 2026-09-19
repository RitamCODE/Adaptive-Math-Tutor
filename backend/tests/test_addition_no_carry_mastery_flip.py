"""Repro + regression test for a reported bug: on the `struggling` demo seed,
addition_no_carry showed mastered (checkmark) mid-session, then unmastered on
the same session's end-of-quest screen, without 4 consecutive wrong answers
on that skill.

Root cause: `_SEED_PROFILES["struggling"]` (backend/api.py) used to bake
addition_no_carry at skill_mastery=0.9, mastery_run=3 as literal constants,
rather than values 3 real BKT updates would ever produce. 0.9 is not a fixed
point of update_mastery, so a single wrong answer on the demoted
addition_no_carry problem (during the seed's own documented resurface path:
fail addition_carry 3x -> demoted to addition_no_carry -> answer it twice to
resurface) dropped mastery to ~0.56, well under the 0.8 gate, zeroing the run
in one wrong answer instead of the documented four.

Fix applied: the seed now uses 1.0, matching the `borrowing` and `fluent`
seeds' existing convention for this same prerequisite-mastery role. 1.0 is an
exact fixed point of update_mastery (the (1-p) term zeroes out p_slip/
p_guess), so it survives any number of wrong answers, not just four.

`_VulnerableMastery` group below still exercises the old 0.9 value directly
(not by reading the seed) to document the underlying mechanism as a
regression guard against any future seed reintroducing a non-fixed-point
mastery value for a "should read as already mastered" role. `LiveSeed` below
exercises the actual current `_SEED_PROFILES["struggling"]` values to prove
the real fix holds.
"""

from backend.api import _SEED_PROFILES
from backend.graph import app
from backend.models.bkt import BKTParams, MASTERY_THRESHOLD, is_mastered
from backend.models.bkt import update_mastery as bkt_update_mastery
from backend.models.state import EngagementState, LastResponse, Problem, SessionState


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _submit(state: SessionState, answer: int | None, time_taken_sec: float = 5.0) -> SessionState:
    state = state.model_copy(
        update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=time_taken_sec)}
    )
    return _invoke(state)


def _demote_from_addition_carry(state: SessionState) -> SessionState:
    """3 wrong answers on the current addition_carry problem -> demote_skill_node
    fires on the 3rd, switching current_problem to the prerequisite,
    addition_no_carry."""
    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)
    return state


# --- mechanism regression: 0.9 was never safe for this role, whoever bakes it ---


def _state_seeded_at(addition_no_carry_mastery: float) -> SessionState:
    problem = Problem(
        problem_id="p_seed", question="47 + 38", correct_answer=85,
        skill_tag="addition_carry", difficulty=0.3,
    )
    return SessionState(
        student_id="s1", session_id="sess1",
        skill_mastery={"addition_no_carry": addition_no_carry_mastery, "addition_carry": 0.3},
        mastery_run={"addition_no_carry": 3},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[], last_response=None,
        engagement=EngagementState(streak=0, xp=10, frustration_signal=False, consecutive_wrong=0),
        problems_completed=3, quest_length=16, next_action="new_problem",
    )


def test_mastery_0_9_is_not_a_fixed_point_and_flips_on_one_wrong_answer():
    """Documents the vulnerability class: a mastery_run of 3 paired with a
    mastery value that isn't near-saturated (unlike ~0.999 from 3 real
    correct BKT updates) can flip to unmastered in a single wrong answer,
    not the four CLAUDE.md's sticky-mastery claim describes."""
    state = _demote_from_addition_carry(_state_seeded_at(0.9))
    assert is_mastered("addition_no_carry", state)  # mastered pre-flip, matching the old bug report

    wrong_answer = state.current_problem.correct_answer + 1
    result = _submit(state, wrong_answer)

    assert result.skill_mastery["addition_no_carry"] < MASTERY_THRESHOLD
    assert result.mastery_run["addition_no_carry"] == 0
    assert not is_mastered("addition_no_carry", result)


def test_mastery_1_0_is_a_fixed_point_and_survives_any_number_of_wrong_answers():
    """The value the fix uses. Unlike "just high enough to survive one slip",
    1.0 never moves under update_mastery at all, correct or wrong -- checked
    directly against the formula, since the engine's own 4-consecutive-wrong
    fatigue stop (a session-level concern, unrelated to this skill's mastery)
    would end the session after far fewer than 5 wrong answers if driven
    through the graph."""
    mastery = {"addition_no_carry": 1.0}
    for _ in range(5):
        mastery = bkt_update_mastery(mastery, "addition_no_carry", False, BKTParams())
        assert mastery["addition_no_carry"] == 1.0


# --- live seed regression: the actual struggling profile no longer flips ---


def _struggling_seed_state() -> SessionState:
    profile = _SEED_PROFILES["struggling"]
    problem = Problem(
        problem_id="p_seed", question="47 + 38", correct_answer=85,
        skill_tag="addition_carry", difficulty=0.3,
    )
    return SessionState(
        student_id="s1", session_id="sess1",
        current_problem=problem, attempt_number=1, attempt_history=[], last_response=None,
        skill_mastery=profile["skill_mastery"],
        mastery_run=profile["mastery_run"],
        misconception_log=profile["misconception_log"],
        engagement=profile["engagement"],
        problems_completed=profile["problems_completed"],
        quest_length=profile["quest_length"],
        next_action="new_problem",
    )


def test_live_seed_starts_mastered():
    state = _struggling_seed_state()
    assert is_mastered("addition_no_carry", state)


def test_live_seed_demotion_alone_does_not_touch_addition_no_carry_mastery():
    state = _demote_from_addition_carry(_struggling_seed_state())

    assert state.current_problem.skill_tag == "addition_no_carry"
    assert state.next_action == "demote_skill"
    assert state.pending_resurface == "addition_carry"
    assert is_mastered("addition_no_carry", state)


def test_live_seed_wrong_answer_on_demoted_skill_no_longer_flips_mastery():
    """The regression test for the reported bug: with the fixed seed, the
    exact sequence that used to un-master addition_no_carry in one wrong
    answer (backend/api.py's own documented demo path: fail addition_carry
    3x, then answer the demoted addition_no_carry problem) now leaves it
    mastered, matching CLAUDE.md's sticky-mastery claim."""
    state = _demote_from_addition_carry(_struggling_seed_state())
    assert is_mastered("addition_no_carry", state)

    wrong_answer = state.current_problem.correct_answer + 1
    result = _submit(state, wrong_answer)

    assert is_mastered("addition_no_carry", result)
    # Confirms this is the same code path an end-of-quest summary reads from:
    # is_mastered(...) called live against the post-turn state, exactly like
    # backend/api.py's _skill_progress()/_group_progress().


def test_live_seed_one_correct_answer_on_demoted_skill_stays_mastered():
    state = _demote_from_addition_carry(_struggling_seed_state())
    correct_answer = state.current_problem.correct_answer

    result = _submit(state, correct_answer)

    assert is_mastered("addition_no_carry", result)
