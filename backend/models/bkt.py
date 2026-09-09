"""Bayesian Knowledge Tracing: mastery parameters and the update rule.

Pure and deterministic per the project's hard constraints — no LLM calls
belong anywhere near mastery math.
"""

from pydantic import BaseModel

MASTERY_THRESHOLD = 0.8


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
