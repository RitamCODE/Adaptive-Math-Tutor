from backend.graph import app
from backend.models.state import EngagementState, LastResponse, SessionState
from backend.skills._arithmetic import parse_operands


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

    # build_remediation_node ran inside the graph (revision-plan Part 5):
    # last_diagnosis/remediation are populated without api.py calling the
    # pure functions itself.
    assert result.last_diagnosis is not None
    assert result.last_diagnosis.correct is False
    assert result.remediation is not None
    assert result.remediation.hint is not None
    assert result.remediation.visual is None  # visual only kicks in at attempt >= 2
    assert result.remediation.reveal_answer is False  # only true at attempt >= 3


def test_correct_answer_produces_no_remediation():
    state = _invoke(_initial_state())
    correct_answer = state.current_problem.correct_answer

    state = state.model_copy(
        update={"last_response": LastResponse(answer=correct_answer, correct=False, time_taken_sec=5.0)}
    )
    result = _invoke(state)

    assert result.last_diagnosis is not None
    assert result.last_diagnosis.correct is True
    assert result.remediation is None


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


def _operand_width(question: str) -> int:
    a, _op, b = parse_operands(question)
    return max(len(str(a)), len(str(b)))


def test_digit_width_does_not_jump_straight_to_three_digits_on_first_correct_answer():
    """Regression test for the originally reported bug: BKT mastery jumps
    ~0.3 -> ~0.90 on a single correct answer (see bkt.py's docstring), but
    digit-width must not follow that jump — it advances only on its own
    sustained-run ladder (_difficulty_ladder.py), independent of mastery."""
    state = _invoke(_initial_state())
    assert _operand_width(state.current_problem.question) == 1
    assert state.skill_mastery == {}

    for _ in range(4):
        answer = state.current_problem.correct_answer
        state = state.model_copy(
            update={"last_response": LastResponse(answer=answer, correct=True, time_taken_sec=5.0)}
        )
        state = _invoke(state)
        if state.current_problem is None or state.current_problem.skill_tag != "addition_no_carry":
            break
        # Mastery crosses 0.8 on the very first correct answer (well above
        # MASTERY_THRESHOLD), yet the digit-width ladder must still hold at 1
        # digit until its own base gate (2 escalating correct answers) is met.
        assert state.skill_mastery["addition_no_carry"] >= 0.8
        assert _operand_width(state.current_problem.question) <= 2


def test_digit_width_advances_to_two_digits_after_escalating_pair():
    state = _invoke(_initial_state())
    assert _operand_width(state.current_problem.question) == 1

    for _ in range(2):
        answer = state.current_problem.correct_answer
        state = state.model_copy(
            update={"last_response": LastResponse(answer=answer, correct=True, time_taken_sec=5.0)}
        )
        state = _invoke(state)

    assert state.digit_level["addition_no_carry"] == 1
    assert _operand_width(state.current_problem.question) == 2
