from backend.models.state import EngagementState, LastResponse, Problem, SessionState
from backend.nodes.engagement import decide_engagement

PROBLEM = Problem(question="47 + 38", correct_answer=85, skill_tag="addition_carry", difficulty=0.5)


def _state(*, last_response, engagement=None, current_problem=PROBLEM) -> SessionState:
    return SessionState(
        student_id="s1",
        session_id="sess1",
        skill_mastery={},
        misconception_log=[],
        current_problem=current_problem,
        last_response=last_response,
        engagement=engagement or EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
    )


def test_correct_answer_increments_streak_and_xp_clears_frustration_and_consecutive_wrong():
    state = _state(
        last_response=LastResponse(answer=85, correct=True, time_taken_sec=3.0),
        engagement=EngagementState(streak=2, xp=20, frustration_signal=True, consecutive_wrong=2),
    )
    result = decide_engagement(state)
    assert result == EngagementState(streak=3, xp=30, frustration_signal=False, consecutive_wrong=0)


def test_incorrect_answer_resets_streak_preserves_xp_increments_consecutive_wrong():
    state = _state(
        last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0),
        engagement=EngagementState(streak=4, xp=40, frustration_signal=False, consecutive_wrong=0),
    )
    result = decide_engagement(state)
    assert result.streak == 0
    assert result.xp == 40
    assert result.consecutive_wrong == 1


def test_frustration_signal_after_three_consecutive_wrong():
    state = _state(
        last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0),
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=2),
    )
    result = decide_engagement(state)
    assert result.consecutive_wrong == 3
    assert result.frustration_signal is True


def test_frustration_signal_false_below_three_consecutive_wrong():
    state = _state(
        last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0),
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=1),
    )
    result = decide_engagement(state)
    assert result.consecutive_wrong == 2
    assert result.frustration_signal is False


def test_no_last_response_returns_engagement_unchanged():
    prev = EngagementState(streak=1, xp=10, frustration_signal=False, consecutive_wrong=0)
    state = _state(last_response=None, engagement=prev)
    assert decide_engagement(state) == prev
