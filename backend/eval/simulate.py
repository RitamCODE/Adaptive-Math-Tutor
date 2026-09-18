"""CLI: run N synthetic students through the real adaptive engine and the
fixed-schedule, fixed-difficulty baseline, and report how many reach real
(hidden ground-truth) mastery on all four skills under each -- broken out by
ability profile, since a single mixed population hides whether an effect is
concentrated in strugglers, average students, or students who barely needed
help either way.

Each student gets the SAME hidden true parameters in both conditions (a
paired comparison, not two independent samples) -- see `run_comparison` --
but each condition runs its own copy of the student with its own independent
random stream from that point on, since a real student's correct/wrong
draws depend on which problems they're actually shown, not just their fixed
underlying ability.

Usage:
    uv run python -m backend.eval.simulate --n 200 --seed 0
"""

from __future__ import annotations

import argparse
import copy
import statistics
from dataclasses import dataclass

from backend.eval.baseline import non_adaptive_condition
from backend.eval.driver import SessionResult, run_session
from backend.eval.synthetic_learner import SKILLS, sample_learner
from backend.skills._arithmetic import default_rng as _problem_rng

# Named ability levels (see synthetic_learner.py's `ability` parameter, in
# [0, 1]) plus "mixed", where each student's ability is drawn uniformly at
# random instead of fixed -- the closest analogue to the frontend's own
# `?seed=` demo profiles (new/struggling/fluent), but as populations rather
# than single fixed students.
PROFILES: dict[str, float | None] = {
    "struggling": 0.15,
    "average": 0.5,
    "fluent": 0.85,
    "mixed": None,
}


@dataclass
class ConditionSummary:
    label: str
    n: int
    all_four_true_mastered: int
    all_four_engine_mastered: int
    turns: list[int]
    per_skill_true_mastered: dict[str, int]
    per_skill_engine_mastered: dict[str, int]

    @property
    def pct_all_four_true(self) -> float:
        return 100 * self.all_four_true_mastered / self.n if self.n else 0.0

    @property
    def pct_all_four_engine(self) -> float:
        return 100 * self.all_four_engine_mastered / self.n if self.n else 0.0


def summarize(label: str, results: list[SessionResult]) -> ConditionSummary:
    n = len(results)
    return ConditionSummary(
        label=label,
        n=n,
        all_four_true_mastered=sum(1 for r in results if all(r.true_mastered.values())),
        all_four_engine_mastered=sum(1 for r in results if all(r.engine_mastered.values())),
        turns=[r.turns for r in results],
        per_skill_true_mastered={skill: sum(1 for r in results if r.true_mastered[skill]) for skill in SKILLS},
        per_skill_engine_mastered={skill: sum(1 for r in results if r.engine_mastered[skill]) for skill in SKILLS},
    )


def _turn_stats(turns: list[int]) -> str:
    if not turns:
        return "n/a"
    quartiles = statistics.quantiles(turns, n=4, method="inclusive") if len(turns) >= 2 else [turns[0]] * 3
    return (
        f"min={min(turns):3d}  p25={quartiles[0]:5.1f}  median={statistics.median(turns):5.1f}  "
        f"p75={quartiles[2]:5.1f}  max={max(turns):3d}  mean={statistics.mean(turns):5.1f}"
    )


def print_summary(s: ConditionSummary) -> None:
    print(f"\n  -- {s.label} (n={s.n}) --")
    print(f"     all 4 skills, TRUE mastery  : {s.all_four_true_mastered:>4d}/{s.n} ({s.pct_all_four_true:.0f}%)")
    print(f"     all 4 skills, engine's BKT  : {s.all_four_engine_mastered:>4d}/{s.n} ({s.pct_all_four_engine:.0f}%)")
    print(f"     turns/session: {_turn_stats(s.turns)}")
    for skill in SKILLS:
        n_true = s.per_skill_true_mastered[skill]
        n_engine = s.per_skill_engine_mastered[skill]
        print(
            f"       {skill:24s} true={n_true:>4d}/{s.n} ({100*n_true/s.n:3.0f}%)"
            f"   engine={n_engine:>4d}/{s.n} ({100*n_engine/s.n:3.0f}%)"
        )


def run_comparison(
    n: int, seed: int, ability: float | None = None
) -> tuple[list[SessionResult], list[SessionResult]]:
    # The skill generators (e.g. addition_no_carry.generate) fall back to a
    # single shared `random.Random()` instance -- backend.skills._arithmetic's
    # `default_rng`, seeded from OS entropy once at import time -- for which
    # operands to show, whenever no seeded rng is passed in; generate_problem
    # never passes one. That instance is NOT the same object Python's global
    # `random.seed()` reseeds, so problem CONTENT (not the learner's own
    # correct/wrong draws, which are seeded independently per learner)
    # would otherwise differ between reruns of the same --seed even if this
    # process also called random.seed(). Reseeding `default_rng` directly is
    # what actually makes a full run reproducible end to end.
    _problem_rng.seed(seed)
    adaptive_results: list[SessionResult] = []
    baseline_results: list[SessionResult] = []
    for i in range(n):
        base_learner = sample_learner(f"synthetic_{i}", seed=f"{seed}:{i}", ability=ability)
        adaptive_results.append(run_session(copy.deepcopy(base_learner)))
        with non_adaptive_condition():
            baseline_results.append(run_session(copy.deepcopy(base_learner)))
    return adaptive_results, baseline_results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=200, help="number of synthetic students PER PROFILE")
    parser.add_argument("--seed", type=int, default=0, help="RNG seed; reruns with the same seed are identical")
    parser.add_argument(
        "--profile", choices=[*PROFILES, "all"], default="all", help="which ability profile(s) to run"
    )
    args = parser.parse_args()

    profiles = PROFILES if args.profile == "all" else {args.profile: PROFILES[args.profile]}

    for profile_name, ability in profiles.items():
        print(f"\n=== profile: {profile_name} (ability={'random' if ability is None else ability}) ===")
        adaptive_results, baseline_results = run_comparison(args.n, args.seed, ability=ability)
        print_summary(summarize("Adaptive (real engine)", adaptive_results))
        print_summary(summarize("Non-adaptive baseline (fixed schedule + fixed difficulty)", baseline_results))


if __name__ == "__main__":
    main()
