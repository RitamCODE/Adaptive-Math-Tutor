"""Bayesian Knowledge Tracing: mastery parameters and the update rule.

Pure and deterministic per the project's hard constraints — no LLM calls
belong anywhere near mastery math.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:  # avoids a runtime import cycle; only needed for typing
    from backend.models.state import SessionState

MASTERY_THRESHOLD = 0.8
MASTERY_MIN_RUN = 3  # consecutive signal-bearing answers at or above the threshold


class BKTParams(BaseModel):
    p_init: float = 0.3
    p_transit: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.05  # numeric entry, not multiple choice, so guess rate is low


def update_mastery(
    mastery: dict[str, float],
    skill: str,
    correct: bool,
    params: BKTParams,
) -> dict[str, float]:
    """Return a new mastery dict with `skill`'s P(L) updated for one observation."""
    p_l = mastery.get(skill, params.p_init)

    if correct:
        p_l_given_evidence = (p_l * (1 - params.p_slip)) / (
            p_l * (1 - params.p_slip) + (1 - p_l) * params.p_guess
        )
    else:
        p_l_given_evidence = (p_l * params.p_slip) / (
            p_l * params.p_slip + (1 - p_l) * (1 - params.p_guess)
        )

    p_l_next = p_l_given_evidence + (1 - p_l_given_evidence) * params.p_transit

    updated = dict(mastery)
    updated[skill] = p_l_next
    return updated


def is_mastered(skill: str, state: "SessionState") -> bool:
    """The single definition of "mastered" for routing, curriculum and UI.

    Crossing `MASTERY_THRESHOLD` once is not enough. With this project's BKT
    parameters a fresh skill jumps 0.3 -> ~0.90 on one correct answer, so a
    bare threshold check flags every skill mastered on its first success.
    A skill counts as mastered only once it has been at or above the
    threshold after each of the last `MASTERY_MIN_RUN` consecutive
    signal-bearing answers on it; `update_mastery_node` keeps that run in
    `state.mastery_run` and zeroes it on any answer that drops back below.

    Note the run is sticky in one direction by construction: from a
    saturated skill it takes four consecutive wrong answers to fall under
    the threshold, and the fatigue stop ends the session at exactly four,
    so a genuinely mastered skill is not un-mastered mid-session.
    """
    return (
        state.skill_mastery.get(skill, 0.0) >= MASTERY_THRESHOLD
        and state.mastery_run.get(skill, 0) >= MASTERY_MIN_RUN
    )
