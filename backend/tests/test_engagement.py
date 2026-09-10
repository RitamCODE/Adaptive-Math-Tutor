from datetime import datetime, timezone

from backend.models.state import (
    EngagementState,
    LastResponse,
    Misconception,
    Problem,
    SessionState,
)
from backend.nodes.engagement import decide_engagement

PROBLEM = Problem(question="47 + 38", correct_answer=85, skill_tag="addition_carry", difficulty=0.5)


def _state(*, last_response, misconception_log=None, engagement=None, current_problem=PROBLEM) -> SessionState:
    return SessionState(
        student_id="s1",
        session_id="sess1",
        skill_mastery={},
        misconception_log=misconception_log or [],
        current_problem=current_problem,
        last_response=last_response,
        engagement=engagement or EngagementState(streak=0, xp=0, frustration_signal=False),
        next_action="new_problem",
    )


def test_correct_answer_increments_streak_and_xp_clears_frustration():
    state = _state(
        last_response=LastResponse(answer=85, correct=True, time_taken_sec=3.0),
        engagement=EngagementState(streak=2, xp=20, frustration_signal=True),
    )
    result = decide_engagement(state)
    assert result == EngagementState(streak=3, xp=30, frustration_signal=False)


def test_incorrect_answer_resets_streak_preserves_xp():
    state = _state(
        last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0),
        engagement=EngagementState(streak=4, xp=40, frustration_signal=False),
    )
    result = decide_engagement(state)
    assert result.streak == 0
    assert result.xp == 40


def test_frustration_signal_after_three_consecutive_same_skill_misses():
    # decide_engagement runs after grade_and_diagnose_node has already
    # appended the current miss, so 3 trailing entries (not 2) is the
    # in-pipeline state that should trip the frustration signal.
    log = [
        Misconception(skill="addition_carry", bug_type="no_carry", timestamp=datetime.now(timezone.utc))
        for _ in range(3)
    ]
    state = _state(last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0), misconception_log=log)
    result = decide_engagement(state)
    assert result.frustration_signal is True


def test_frustration_signal_false_when_misses_are_on_different_skills():
    log = [
        Misconception(skill="subtraction_borrow", bug_type="reversed_operands", timestamp=datetime.now(timezone.utc)),
        Misconception(skill="addition_carry", bug_type="no_carry", timestamp=datetime.now(timezone.utc)),
    ]
    state = _state(last_response=LastResponse(answer=75, correct=False, time_taken_sec=3.0), misconception_log=log)
    result = decide_engagement(state)
    assert result.frustration_signal is False


def test_no_last_response_returns_engagement_unchanged():
    prev = EngagementState(streak=1, xp=10, frustration_signal=False)
    state = _state(last_response=None, engagement=prev)
    assert decide_engagement(state) == prev
