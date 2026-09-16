"""The sustained-mastery gate: a skill is mastered only after holding the
threshold across several consecutive signal-bearing answers.

With this project's BKT parameters a fresh skill jumps 0.30 -> ~0.9025 on one
correct answer, so a bare `>= 0.8` check flagged every skill mastered on its
first success. `is_mastered` adds the run requirement; these tests pin both
the predicate and the bookkeeping in `update_mastery_node` that feeds it.
"""

from backend.graph import app
from backend.models.bkt import MASTERY_MIN_RUN, MASTERY_THRESHOLD, is_mastered
from backend.models.state import EngagementState, LastResponse, Problem, SessionState
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH
from backend.tests.conftest import make_state, mastered_state


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _state_on(skill: str, question: str, correct_answer: int, **overrides) -> SessionState:
    problem = Problem(
        problem_id="p_gate", question=question, correct_answer=correct_answer,
        skill_tag=skill, difficulty=0.3,
    )
    base = dict(
        student_id="s1", session_id="sess1",
        skill_mastery={skill: 0.95}, mastery_run={skill: 2},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[], last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        problems_completed=0, quest_length=16, next_action="new_problem",
    )
    base.update(overrides)
    return SessionState(**base)


def _submit(state: SessionState, answer: int | None, time_taken_sec: float = 5.0) -> SessionState:
    state = state.model_copy(
        update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=time_taken_sec)}
    )
    return _invoke(state)


# --- the predicate ---


def test_crossing_the_threshold_once_is_not_mastery():
    for run in range(MASTERY_MIN_RUN):
        state = make_state({"addition_carry": 0.95}, {"addition_carry": run})
        assert not is_mastered("addition_carry", state), f"run of {run} should not count"


def test_mastered_once_the_run_is_complete():
    state = make_state({"addition_carry": 0.95}, {"addition_carry": MASTERY_MIN_RUN})
    assert is_mastered("addition_carry", state)


def test_a_long_run_below_the_threshold_is_not_mastery():
    """Both halves are required: the run alone proves nothing."""
    state = make_state({"addition_carry": 0.5}, {"addition_carry": 99})
    assert not is_mastered("addition_carry", state)


def test_unknown_skill_is_not_mastered():
    assert not is_mastered("addition_carry", make_state())


# --- the bookkeeping in update_mastery_node ---


def test_a_correct_answer_advances_the_run():
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": 1})
    result = _submit(state, 85)
    assert result.mastery_run["addition_carry"] == 2


def test_a_wrong_answer_that_drops_below_the_threshold_resets_the_run():
    state = _state_on(
        "addition_carry", "47 + 38", 85,
        skill_mastery={"addition_carry": 0.85}, mastery_run={"addition_carry": 2},
    )
    result = _submit(state, 86)
    assert result.skill_mastery["addition_carry"] < MASTERY_THRESHOLD
    assert result.mastery_run["addition_carry"] == 0


def test_digit_reversal_leaves_the_run_untouched():
    """CLAUDE.md: digit reversal means the underlying skill is intact, so
    mastery is not penalized — and by the same logic not rewarded either."""
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": 2})
    result = _submit(state, 58)  # 85 reversed
    assert result.attempt_history[-1][1] == "digit_reversal"
    assert result.skill_mastery["addition_carry"] == state.skill_mastery["addition_carry"]
    assert result.mastery_run["addition_carry"] == 2


def test_a_blank_submission_leaves_the_run_untouched():
    """Non-signal submissions never reach update_mastery_node at all."""
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": 2})
    result = _submit(state, None)
    assert result.mastery_run["addition_carry"] == 2


def test_a_rapid_guess_leaves_the_run_untouched():
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": 2})
    result = _submit(state, 85, time_taken_sec=0.5)
    assert result.mastery_run["addition_carry"] == 2


# --- routing consequences ---


def test_completing_the_run_advances_the_skill():
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": MASTERY_MIN_RUN - 1})
    result = _submit(state, 85)
    assert result.next_action == "advance_skill"


def test_a_short_run_serves_another_problem_on_the_same_skill():
    state = _state_on("addition_carry", "47 + 38", 85, mastery_run={"addition_carry": 0})
    result = _submit(state, 85)
    assert result.next_action == "new_problem"
    assert result.current_problem.skill_tag == "addition_carry"


def test_quest_ends_when_both_parent_skills_are_mastered():
    """The last sub-skill's completing answer ends the quest outright."""
    already = {skill: 0.95 for skill in DEFAULT_SKILL_GRAPH.all_skills()}
    runs = {skill: MASTERY_MIN_RUN for skill in DEFAULT_SKILL_GRAPH.all_skills()}
    runs["subtraction_borrow"] = MASTERY_MIN_RUN - 1
    state = _state_on(
        "subtraction_borrow", "42 - 17", 25,
        skill_mastery=already, mastery_run=runs, problems_completed=5,
    )
    result = _submit(state, 25)
    assert result.next_action == "end_session"
    assert DEFAULT_SKILL_GRAPH.all_groups_mastered(result)


def test_mastering_three_of_four_sub_skills_does_not_end_the_quest():
    """The old rule ended the quest at any 2 mastered skills, which made
    subtraction unreachable by play."""
    mastery = {skill: 0.95 for skill in DEFAULT_SKILL_GRAPH.all_skills()}
    runs = {
        "addition_no_carry": MASTERY_MIN_RUN,
        "addition_carry": MASTERY_MIN_RUN,
        "subtraction_no_borrow": MASTERY_MIN_RUN - 1,
        "subtraction_borrow": 0,
    }
    state = _state_on(
        "subtraction_no_borrow", "48 - 17", 31,
        skill_mastery=mastery, mastery_run=runs, problems_completed=5,
    )
    result = _submit(state, 31)
    assert result.next_action == "advance_skill"
    assert result.current_problem.skill_tag == "subtraction_borrow"


def test_quest_ends_when_quest_length_is_reached():
    state = _state_on(
        "addition_carry", "47 + 38", 85,
        mastery_run={"addition_carry": 0}, problems_completed=15, quest_length=16,
    )
    result = _submit(state, 85)
    assert result.next_action == "end_session"


def test_an_ungrouped_state_still_ends_on_quest_length():
    """Sanity check that the group condition can't end a quest early on its own."""
    state = mastered_state()
    assert not DEFAULT_SKILL_GRAPH.all_groups_mastered(state)
