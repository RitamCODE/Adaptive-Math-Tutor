"""The `decide_engagement` node: streak/xp/frustration bookkeeping.

CLAUDE.md doesn't specify an algorithm here — this is a deliberately simple,
deterministic policy (no LLM; this is not one of the four narrative
touchpoints).
"""

from backend.models.state import EngagementState, SessionState

XP_PER_CORRECT = 10
FRUSTRATION_STREAK = 3  # N consecutive same-skill misses before flagging frustration


def decide_engagement(state: SessionState) -> EngagementState:
    prev = state.engagement
    response = state.last_response

    if response is None or state.current_problem is None:
        return prev

    if response.correct:
        return EngagementState(streak=prev.streak + 1, xp=prev.xp + XP_PER_CORRECT, frustration_signal=False)

    # Only counts misses that matched a known bug rule (grade_and_diagnose_node
    # only logs a Misconception on a rule match) — a wrong answer with no
    # matching rule doesn't add to the trailing-miss count.
    skill = state.current_problem.skill_tag
    trailing_misses = 0
    for m in reversed(state.misconception_log):
        if m.skill != skill:
            break
        trailing_misses += 1

    return EngagementState(streak=0, xp=prev.xp, frustration_signal=trailing_misses >= FRUSTRATION_STREAK)
