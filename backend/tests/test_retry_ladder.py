"""The three-attempt retry ladder (revision-plan 1.2) and its termination hooks (1.3).

Uses `_mid_skill_state` rather than the bootstrap-and-play-60-turns pattern in
test_graph.py, because the bootstrap skill (addition_no_carry) has no
prerequisite and can't exercise demotion. addition_carry's prerequisite is
addition_no_carry, so starting there exercises the full ladder.
"""

from backend.graph import app
from backend.models.state import EngagementState, LastResponse, Problem, SessionState
from backend.nodes.diagnosis import grade_and_diagnose


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _mid_skill_state() -> SessionState:
    problem = Problem(
        problem_id="p_test", question="47 + 38", correct_answer=85,
        skill_tag="addition_carry", difficulty=0.3,
    )
    return SessionState(
        student_id="s1", session_id="sess1",
        skill_mastery={"addition_no_carry": 0.5, "addition_carry": 0.3},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[],
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        problems_completed=0, quest_length=10, next_action="new_problem",
    )


def _submit(state: SessionState, answer: int | None, time_taken_sec: float = 5.0) -> SessionState:
    state = state.model_copy(
        update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=time_taken_sec)}
    )
    return _invoke(state)


def test_attempt_1_wrong_keeps_same_problem_no_reveal():
    state = _mid_skill_state()
    wrong_answer = state.current_problem.correct_answer + 1

    result = _submit(state, wrong_answer)

    assert result.current_problem.problem_id == "p_test"
    assert result.attempt_number == 2
    assert len(result.attempt_history) == 1
    assert result.attempt_history[0][0] == wrong_answer
    assert result.next_action == "retry_problem"

    diagnosis = grade_and_diagnose(state.current_problem, wrong_answer, attempt=1)
    assert diagnosis.reveal_answer is False
    assert diagnosis.hint is not None
    assert diagnosis.attempts_remaining == 2
    assert diagnosis.visual is None


def test_attempt_2_wrong_still_same_problem_with_visual_signal():
    state = _mid_skill_state()
    wrong_answer = state.current_problem.correct_answer + 1
    state = _submit(state, wrong_answer)

    result = _submit(state, wrong_answer)

    assert result.current_problem.problem_id == "p_test"
    assert result.attempt_number == 3
    assert len(result.attempt_history) == 2
    assert result.next_action == "retry_problem"

    diagnosis = grade_and_diagnose(state.current_problem, wrong_answer, attempt=2)
    assert diagnosis.reveal_answer is False
    assert diagnosis.visual is not None


def test_attempt_3_wrong_reveals_answer_and_demotes_skill():
    state = _mid_skill_state()
    wrong_answer = state.current_problem.correct_answer + 1
    original_problem_id = state.current_problem.problem_id
    state = _submit(state, wrong_answer)
    state = _submit(state, wrong_answer)

    diagnosis = grade_and_diagnose(state.current_problem, wrong_answer, attempt=3)
    assert diagnosis.reveal_answer is True

    result = _submit(state, wrong_answer)

    assert result.current_problem.skill_tag == "addition_no_carry"
    assert result.current_problem.problem_id != original_problem_id
    assert result.attempt_number == 1
    assert result.attempt_history == []
    assert result.next_action == "demote_skill"
    assert result.problems_completed == 1


def test_correct_answer_resets_attempt_ladder():
    state = _mid_skill_state()
    correct_answer = state.current_problem.correct_answer

    state = state.model_copy(
        update={"last_response": LastResponse(answer=correct_answer, correct=False, time_taken_sec=5.0)}
    )
    result = _invoke(state)

    assert result.attempt_number == 1
    assert result.attempt_history == []
    assert result.next_action in {"new_problem", "advance_skill"}
    assert result.problems_completed == 1


def test_blank_answer_does_not_consume_attempt_or_update_bkt():
    state = _mid_skill_state()

    result = _submit(state, None, time_taken_sec=0.3)

    assert result.attempt_number == 1
    assert result.attempt_history == []
    assert result.skill_mastery["addition_carry"] == 0.3
    assert result.next_action == "retry_problem"
    assert result.engagement.consecutive_wrong == 0


def test_digit_reversal_wrong_answer_consumes_attempt_but_not_mastery():
    state = _mid_skill_state()
    reversed_answer = int(str(state.current_problem.correct_answer)[::-1])  # 85 -> 58

    diagnosis = grade_and_diagnose(state.current_problem, reversed_answer, attempt=1)
    assert diagnosis.bug_type == "digit_reversal"

    result = _submit(state, reversed_answer)

    assert result.attempt_number == 2
    assert result.next_action == "retry_problem"
    assert result.skill_mastery["addition_carry"] == 0.3


def test_four_consecutive_wrong_ends_session():
    state = _mid_skill_state()

    for _ in range(4):
        wrong_answer = state.current_problem.correct_answer + 1
        state = _submit(state, wrong_answer)

    assert state.next_action == "end_session"
    assert state.engagement.consecutive_wrong == 4


def _demoted_state() -> SessionState:
    """A skill demoted to an already-mastered prerequisite (revision-plan 7.3):
    addition_no_carry sits above the 0.8 mastery threshold, exactly the
    realistic case that would resurface after one correct answer instead of
    two without the pending_resurface/resurface_progress bookkeeping."""
    problem = Problem(
        problem_id="p_test", question="47 + 38", correct_answer=85,
        skill_tag="addition_carry", difficulty=0.3,
    )
    state = SessionState(
        student_id="s1", session_id="sess1",
        skill_mastery={"addition_no_carry": 0.85, "addition_carry": 0.3},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[],
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        problems_completed=0, quest_length=10, next_action="new_problem",
    )
    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)
    return state


def test_demotion_sets_pending_resurface():
    state = _demoted_state()

    assert state.current_problem.skill_tag == "addition_no_carry"
    assert state.next_action == "demote_skill"
    assert state.pending_resurface == "addition_carry"
    assert state.resurface_progress == 0
    assert state.resurfaced_skills == []


def test_one_correct_on_prerequisite_does_not_resurface_yet():
    state = _demoted_state()
    correct_answer = state.current_problem.correct_answer

    result = _submit(state, correct_answer)

    assert result.pending_resurface == "addition_carry"
    assert result.resurface_progress == 1
    assert result.current_problem.skill_tag == "addition_no_carry"
    # Without the resurface bookkeeping, addition_no_carry's mastery (already
    # above 0.8) would trip the normal threshold check and this would read
    # "advance_skill" after just one correct answer instead of two.
    assert result.next_action == "new_problem"


def test_second_correct_on_prerequisite_triggers_resurface():
    state = _demoted_state()
    correct_answer = state.current_problem.correct_answer
    state = _submit(state, correct_answer)

    result = _submit(state, state.current_problem.correct_answer)

    assert result.pending_resurface is None
    assert result.resurface_progress == 0
    assert result.resurfaced_skills == ["addition_carry"]
    assert result.current_problem.skill_tag == "addition_carry"
    assert result.next_action == "new_problem"
    assert result.attempt_number == 1
    assert result.attempt_history == []


def test_resurfaced_skill_failing_again_ends_session():
    state = _demoted_state()
    state = _submit(state, state.current_problem.correct_answer)
    state = _submit(state, state.current_problem.correct_answer)
    assert state.current_problem.skill_tag == "addition_carry"

    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)

    assert state.next_action == "end_session"
    assert state.current_problem is None


def test_demote_skill_root_fallback_does_not_set_pending_resurface():
    problem = Problem(
        problem_id="p_root", question="4 + 3", correct_answer=7,
        skill_tag="addition_no_carry", difficulty=0.3,
    )
    state = SessionState(
        student_id="s1", session_id="sess1",
        skill_mastery={"addition_no_carry": 0.3},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[],
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        problems_completed=0, quest_length=10, next_action="new_problem",
    )
    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)

    assert state.pending_resurface is None


def test_second_demotion_does_not_clobber_existing_pending_resurface():
    problem = Problem(
        problem_id="p_test", question="61 - 24", correct_answer=37,
        skill_tag="subtraction_no_borrow", difficulty=0.3,
    )
    state = SessionState(
        student_id="s1", session_id="sess1",
        skill_mastery={"addition_no_carry": 0.9, "addition_carry": 0.3, "subtraction_no_borrow": 0.3},
        misconception_log=[], current_problem=problem,
        attempt_number=1, attempt_history=[],
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        problems_completed=0, quest_length=10, next_action="new_problem",
        pending_resurface="subtraction_borrow", resurface_progress=1,
    )
    wrong_answer = state.current_problem.correct_answer + 1
    for _ in range(3):
        state = _submit(state, wrong_answer)

    assert state.current_problem.skill_tag == "addition_carry"
    assert state.next_action == "demote_skill"
    assert state.pending_resurface == "subtraction_borrow"
    assert state.resurface_progress == 1
