import pytest

from backend.models.bkt import MASTERY_MIN_RUN
from backend.models.state import EngagementState, SessionState


@pytest.fixture(autouse=True)
def _no_llm_api_key(monkeypatch):
    """Keep the whole suite deterministic and network-free: every narrative
    touchpoint falls back to None unless a test explicitly sets a key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def make_state(mastery: dict[str, float] | None = None, mastery_run: dict[str, int] | None = None, **overrides) -> SessionState:
    """A minimal SessionState for testing anything that reads mastery.

    `is_mastered` needs both the mastery value and the per-skill run of
    consecutive signal-bearing answers that held it at or above threshold,
    so helpers that used to take a bare mastery dict now take a state.
    """
    return SessionState(
        student_id="s",
        session_id="sess",
        skill_mastery=dict(mastery or {}),
        mastery_run=dict(mastery_run or {}),
        misconception_log=[],
        current_problem=None,
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
        **overrides,
    )


def mastered_state(*skills: str, **overrides) -> SessionState:
    """A state in which each named skill passes the sustained-mastery gate."""
    return make_state(
        mastery={skill: 0.95 for skill in skills},
        mastery_run={skill: MASTERY_MIN_RUN for skill in skills},
        **overrides,
    )
