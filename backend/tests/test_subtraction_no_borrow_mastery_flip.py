"""Same bug class as test_addition_no_carry_mastery_flip.py, found in the
`borrowing` demo seed: `_SEED_PROFILES["borrowing"]` used to bake prerequisite
mastery values for a role that needs to survive a wrong answer during a
demotion/resurface window (backend/skills/skill_graph.py's prerequisite
chain: subtraction_borrow -> subtraction_no_borrow -> addition_carry ->
addition_no_carry) at 0.95/0.9 -- not fixed points of update_mastery, unlike
addition_no_carry's existing 1.0.

Reported symptom: an unexpected "Quest complete" screen while working on
subtraction_borrow. Mechanism: fail subtraction_borrow 3x -> demote_skill_node
drops you into its prerequisite, subtraction_no_borrow. With the old 0.9
seed value, one more wrong, signal-bearing answer there both (a) dropped
subtraction_no_borrow's mastery under 0.8, zeroing its run, and (b) was also
the session's 4th consecutive wrong answer overall (3 on subtraction_borrow +
1 on subtraction_no_borrow), tripping the engagement fatigue stop and ending
the session outright -- exactly what an unexpected Quest complete screen
while on subtraction_borrow would look like.

Fix applied: both values changed to 1.0, matching addition_no_carry's
existing convention. `_VulnerableMastery`-style tests below document the
mechanism as a regression guard; `LiveSeed`-style tests prove the actual fix
holds.
"""

from backend.api import _SEED_PROFILES
from backend.graph import app
from backend.models.bkt import BKTParams, MASTERY_THRESHOLD, is_mastered
from backend.models.bkt import update_mastery as bkt_update_mastery
from backend.models.state import LastResponse, SessionState
from backend.nodes.problem_gen import generate_problem


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _submit(state: SessionState, answer: int | None, time_taken_sec: float = 5.0) -> SessionState:
    state = state.model_copy(
        update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=time_taken_sec)}
    )
    return _invoke(state)


def _demote_from(state: SessionState, skill: str) -> SessionState:
    """3 wrong answers on the current `skill` problem -> demote_skill_node
    fires on the 3rd, switching current_problem to its prerequisite."""
    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)
    return state


# --- mechanism regression: same vulnerability class as addition_no_carry ---


def test_mastery_0_9_and_0_95_are_not_fixed_points():
    """Both baked borrowing-seed values are unsafe, unlike 1.0."""
    for starting in (0.9, 0.95):
        mastery = {"skill": starting}
        mastery = bkt_update_mastery(mastery, "skill", False, BKTParams())
        assert mastery["skill"] < MASTERY_THRESHOLD, (
            f"{starting} should not survive a single wrong answer, got {mastery['skill']}"
        )


# --- live seed regression: the actual borrowing profile ---


def _borrowing_seed_state() -> SessionState:
    profile = _SEED_PROFILES["borrowing"]
    problem = generate_problem("subtraction_borrow", 0.3)
    return SessionState(
        student_id="s1", session_id="sess1",
        current_problem=problem, attempt_number=1, attempt_history=[], last_response=None,
        skill_mastery=profile["skill_mastery"],
        mastery_run=profile["mastery_run"],
        misconception_log=profile["misconception_log"],
        engagement=profile["engagement"],
        digit_level=profile.get("digit_level", {}),
        problems_completed=profile["problems_completed"],
        quest_length=profile["quest_length"],
        next_action="new_problem",
    )


def test_live_seed_starts_mastered():
    state = _borrowing_seed_state()
    assert is_mastered("subtraction_no_borrow", state)
    assert is_mastered("addition_carry", state)


def test_live_seed_demotion_alone_does_not_touch_prerequisite_mastery():
    state = _demote_from(_borrowing_seed_state(), "subtraction_borrow")

    assert state.current_problem.skill_tag == "subtraction_no_borrow"
    assert state.next_action == "demote_skill"
    assert state.pending_resurface == "subtraction_borrow"
    assert is_mastered("subtraction_no_borrow", state)


def test_live_seed_wrong_answer_on_demoted_skill_no_longer_flips_mastery():
    """The regression test for the reported bug: with the fixed seed, the
    exact sequence that used to un-master subtraction_no_borrow (and end the
    session outright as the session's 4th consecutive wrong overall) now
    leaves it mastered and the session still in progress."""
    state = _demote_from(_borrowing_seed_state(), "subtraction_borrow")
    assert is_mastered("subtraction_no_borrow", state)

    wrong_answer = state.current_problem.correct_answer + 1
    result = _submit(state, wrong_answer)

    print(
        "\n[borrowing seed] after 1 wrong on demoted subtraction_no_borrow: "
        f"mastery={result.skill_mastery['subtraction_no_borrow']!r} "
        f"run={result.mastery_run['subtraction_no_borrow']!r} "
        f"is_mastered={is_mastered('subtraction_no_borrow', result)!r} "
        f"next_action={result.next_action!r} "
        f"consecutive_wrong={result.engagement.consecutive_wrong!r}"
    )

    assert is_mastered("subtraction_no_borrow", result)
    # Still 4 consecutive wrong overall -- this fix doesn't change the
    # fatigue-stop mechanic, only whether it coincides with an incorrect
    # un-mastering of the skill that was demoted into.
    assert result.engagement.consecutive_wrong == 4
    assert result.next_action == "end_session"
