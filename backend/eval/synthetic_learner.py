"""Synthetic-student model: a hidden true knowledge state per skill.

This is deliberately separate from the engine's own BKT estimate
(`SessionState.skill_mastery`). The engine only ever sees answers; it never
sees the ground truth. That's the whole point of the simulation -- to ask
whether the app's practice allocation gets more students to REAL
understanding, not just whether its own BKT estimate agrees with itself.

The hidden dynamics follow the same two-state generative model BKT itself
assumes (`known` / not-known, with slip and guess noise and a one-way
learning transition), but every parameter is sampled independently per
synthetic student and per skill, from a wider and sometimes harsher range
than `backend.models.bkt.BKTParams`' defaults (`p_slip=0.1`, `p_guess=0.05`,
`p_transit=0.15`). That deliberate mismatch matters: a simulation whose
synthetic students always behave exactly like the engine's own assumed
parameters would only prove the engine's math is self-consistent, not that
it tracks real students who slip, guess, or learn at different rates than
assumed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from backend.skills._difficulty_ladder import WIDTH_LADDER
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH

SKILLS: list[str] = DEFAULT_SKILL_GRAPH.all_skills()

# Each skill's own narrowest tier (1-digit for the two non-regrouping skills,
# 2-digit for addition_carry/subtraction_borrow, since a carry or borrow is
# impossible at 1-digit) -- the baseline for "how many digits wider than the
# easiest version of this skill is the problem in front of the student."
_BASE_WIDTH: dict[str, int] = {skill: ladder[0] for skill, ladder in WIDTH_LADDER.items()}


@dataclass(frozen=True)
class SkillTrueParams:
    p_init_true: float  # true P(already knows this skill) at session start
    p_slip_true: float  # true P(wrong answer | knows it), AT the skill's narrowest tier
    p_guess_true: float  # true P(correct answer | doesn't know it)
    p_learn_true: float  # true P(transitions not-knowing -> knowing), per attempt
    width_sensitivity_true: float  # extra slip probability per digit beyond the
                                    # narrowest tier -- carrying/borrowing across more
                                    # columns genuinely gets harder even for a student
                                    # who "knows" the skill, and BKT's own p_slip is a
                                    # single flat number that can't see digit-width at
                                    # all (backend/skills/_difficulty_ladder.py's own
                                    # docstring), so this is a deliberate point of
                                    # model mismatch between the true process and what
                                    # the engine assumes when it reads a slip.


def effective_p_slip(params: SkillTrueParams, skill: str, digit_width: int) -> float:
    """The true P(wrong | knows it) for a specific problem, given how many
    digits wider than the skill's own narrowest tier it is. Pure and
    independently testable so the digit-width effect can be checked exactly,
    not just inferred from noisy simulation output."""
    extra = max(0, digit_width - _BASE_WIDTH.get(skill, digit_width))
    return min(0.95, params.p_slip_true + params.width_sensitivity_true * extra)


@dataclass
class SyntheticLearner:
    """One synthetic student. `known` is the hidden ground truth per skill,
    which flips from False to True over the course of a session as the
    student practices; `true_params` is fixed for the student's lifetime."""

    student_id: str
    true_params: dict[str, SkillTrueParams]
    rng: random.Random
    known: dict[str, bool] = field(default_factory=dict)

    def is_known(self, skill: str) -> bool:
        if skill not in self.known:
            self.known[skill] = self.rng.random() < self.true_params[skill].p_init_true
        return self.known[skill]

    def answer(self, skill: str, correct_answer: int, digit_width: int) -> int:
        """One attempt on `skill`, on a problem `digit_width` digits wide.
        Returns the integer to submit; this is the only channel through
        which the harness's ground truth reaches the engine -- everything
        downstream (grading, BKT, curriculum) sees only this int, exactly as
        it would from a real student's number pad."""
        params = self.true_params[skill]
        known = self.is_known(skill)
        p_correct = (1 - effective_p_slip(params, skill, digit_width)) if known else params.p_guess_true
        correct = self.rng.random() < p_correct

        # One-way learning transition, independent of this attempt's outcome
        # (mirrors the shape of BKT's own P(L_next) update) -- a student can
        # learn from an attempt they slipped on or guessed through.
        if not known and self.rng.random() < params.p_learn_true:
            self.known[skill] = True

        if correct:
            return correct_answer
        return self._plausible_wrong_answer(correct_answer)

    def _plausible_wrong_answer(self, correct_answer: int) -> int:
        """A wrong answer that is deliberately never the digit-reversal of
        the correct one. `digit_reversal` is exempt from the BKT update and
        the mastery-run counter (backend/graph.py's update_mastery_node) --
        a generic "wrong answer" generator that happened to produce
        reversal-shaped answers at some uncontrolled rate would silently
        exempt a chunk of "wrong" trials from any mastery penalty for
        reasons that have nothing to do with the modeled slip rate."""
        reversed_answer = int(str(correct_answer)[::-1])
        for _ in range(10):
            candidate = correct_answer + self.rng.choice([-3, -2, -1, 1, 2, 3])
            if candidate not in (correct_answer, reversed_answer) and candidate >= 0:
                return candidate
        return correct_answer + 5


def _sample_skill_params(rng: random.Random, ability: float) -> SkillTrueParams:
    """`ability` in [0, 1] biases where this student's true params land, but
    slip/guess/learning-rate are still drawn independently per skill -- two
    skills for the same student can look quite different, same as a real
    kid who's fast at addition and shaky on borrowing."""

    def _clamped_gauss(mean: float, sd: float, lo: float, hi: float) -> float:
        return min(hi, max(lo, rng.gauss(mean, sd)))

    return SkillTrueParams(
        p_init_true=_clamped_gauss(0.05 + 0.5 * ability, 0.12, 0.01, 0.95),
        p_slip_true=_clamped_gauss(0.18 - 0.10 * ability, 0.06, 0.0, 0.45),
        p_guess_true=_clamped_gauss(0.06, 0.04, 0.0, 0.3),
        p_learn_true=_clamped_gauss(0.08 + 0.27 * ability, 0.08, 0.01, 0.6),
        # Weaker students degrade more per extra digit, not just start lower.
        width_sensitivity_true=_clamped_gauss(0.09 - 0.05 * ability, 0.03, 0.0, 0.3),
    )


def sample_learner(student_id: str, seed: object, ability: float | None = None) -> SyntheticLearner:
    """Build one synthetic student with its own independent random stream.

    `seed` seeds that stream (any hashable, e.g. an int or f"{run_seed}:{i}")
    so a given seed always reproduces the same student. `ability` in [0, 1]
    is drawn uniformly at random when omitted; pass it explicitly to build a
    population of a known shape (e.g. all near 0, or all near 1, for the
    sanity checks in test_simulate.py)."""
    rng = random.Random(seed)
    ability = rng.random() if ability is None else ability
    true_params = {skill: _sample_skill_params(rng, ability) for skill in SKILLS}
    return SyntheticLearner(student_id=student_id, true_params=true_params, rng=rng)


def sample_population(n: int, seed: int, ability: float | None = None) -> list[SyntheticLearner]:
    return [sample_learner(f"synthetic_{i}", seed=f"{seed}:{i}", ability=ability) for i in range(n)]
