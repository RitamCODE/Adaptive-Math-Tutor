"""The `decide_engagement` node: streak/xp/frustration/fatigue bookkeeping.

CLAUDE.md doesn't specify an algorithm here — this is a deliberately simple,
deterministic policy (no LLM; this is not one of the four narrative
touchpoints).
"""

from backend.models.state import EngagementState, SessionState

XP_PER_CORRECT = 10
FRUSTRATION_THRESHOLD = 3  # consecutive signal-bearing wrong answers before flagging frustration


def decide_engagement(state: SessionState) -> EngagementState:
    prev = state.engagement
    response = state.last_response

    if response is None or state.current_problem is None:
        return prev

    if response.correct:
        return EngagementState(
            streak=prev.streak + 1, xp=prev.xp + XP_PER_CORRECT,
            frustration_signal=False, consecutive_wrong=0,
        )

    consecutive_wrong = prev.consecutive_wrong + 1
    return EngagementState(
        streak=0, xp=prev.xp,
        frustration_signal=consecutive_wrong >= FRUSTRATION_THRESHOLD,
        consecutive_wrong=consecutive_wrong,
    )
