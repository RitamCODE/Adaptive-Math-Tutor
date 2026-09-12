from backend.graph import app
from backend.models.state import EngagementState, LastResponse, SessionState


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _initial_state() -> SessionState:
    return SessionState(
        student_id="s1",
        session_id="sess1",
        skill_mastery={},
        misconception_log=[],
        current_problem=None,
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
    )


def test_bootstrap_generates_first_problem_for_empty_session():
    result = _invoke(_initial_state())
    assert result.current_problem is not None
    assert result.current_problem.skill_tag == "addition_no_carry"
    assert result.next_action == "new_problem"


def test_wrong_answer_on_attempt_1_keeps_same_problem():
    state = _invoke(_initial_state())
    skill = state.current_problem.skill_tag
    problem_id = state.current_problem.problem_id
    wrong_answer = state.current_problem.correct_answer + 1

    state = state.model_copy(
        update={"last_response": LastResponse(answer=wrong_answer, correct=False, time_taken_sec=5.0)}
    )
    result = _invoke(state)

    assert result.current_problem.skill_tag == skill
    assert result.current_problem.problem_id == problem_id
    assert result.next_action == "retry_problem"
    assert result.attempt_number == 2
    assert result.skill_mastery[skill] < 0.3


def test_scripted_session_runs_through_one_mastery_transition():
    state = _invoke(_initial_state())
    starting_skill = state.current_problem.skill_tag

    for _ in range(60):
        answer = state.current_problem.correct_answer
        state = state.model_copy(update={"last_response": LastResponse(answer=answer, correct=True, time_taken_sec=2.0)})
        state = _invoke(state)
        if state.next_action == "advance_skill":
            break
    else:
        raise AssertionError("session did not advance past the starting skill within 60 turns")

    assert state.current_problem.skill_tag != starting_skill
    assert state.current_problem.skill_tag == "addition_carry"
