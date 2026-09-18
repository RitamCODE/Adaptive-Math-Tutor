# Known gaps

## Simulated-learner evaluation: full results

The summary in `README.md`'s "Does the adaptive engine actually help?" section is a compressed
version of this. Nothing here is cherry-picked or excluded from that summary: two of the
individually-notable per-skill comparisons below favor the fixed baseline, not the adaptive
engine, and they're reported here the same way the favorable ones are. Reproduce all of it with
`uv run python -m backend.eval.simulate --n 200 --seed 0` (deterministic — see "Reproducing
this" below).

**Target**: adaptive problem selection (BKT-gated skill switching plus a digit-width ladder,
`backend/graph.py`) should get more synthetic students to real mastery of all four skills than
a fixed-schedule, fixed-difficulty baseline given the identical 16-problem budget — measured
against the engine's own sustained-evidence BKT gate (`is_mastered()`, `backend/models/bkt.py`)
and, separately, against each synthetic student's hidden ground-truth knowledge state, which
the engine never sees (`backend/eval/synthetic_learner.py`).

**What it actually found**: adaptive pacing raises how often the engine's own BKT gate can
confirm all four skills mastered, for average- and mixed-ability populations — a real, if
statistically modest, effect (see "Statistical notes" below for exactly how modest). It does
**not** raise real, ground-truth mastery by a distinguishable amount in any profile at this
sample size, and on 2 of the 16 individual skill/profile comparisons where ground truth is
individually significant, the fixed baseline is ahead, not adaptive.

### All four skills, per profile

| Profile | Engine-confirmed, adaptive | Engine-confirmed, baseline | Ground-truth, adaptive | Ground-truth, baseline |
|---|---|---|---|---|
| Struggling | 8/200 (4%) | 3/200 (2%) | 13/200 (7%) | 12/200 (6%) |
| Average | 43/200 (22%) | 25/200 (13%) | 59/200 (30%) | 55/200 (28%) |
| Fluent | 86/200 (43%) | 74/200 (37%) | 112/200 (56%) | 128/200 (64%) |
| Mixed | 47/200 (24%) | 28/200 (14%) | 55/200 (28%) | 62/200 (31%) |

### Per-skill ground-truth mastery rate, all four skills

| Profile / Condition | addition_no_carry | addition_carry | subtraction_no_borrow | subtraction_borrow |
|---|---|---|---|---|
| Struggling / Adaptive | 100/200 (50%) | 65/200 (33%) | 53/200 (27%) | 34/200 (17%) |
| Struggling / Baseline | 101/200 (51%) | 67/200 (34%) | 52/200 (26%) | 33/200 (17%) |
| Average / Adaptive | 154/200 (77%) | 120/200 (60%) | 118/200 (59%) | 94/200 (47%) |
| Average / Baseline | 159/200 (80%) | 139/200 (70%)** | 119/200 (60%) | 83/200 (42%) |
| Fluent / Adaptive | 183/200 (92%) | 166/200 (83%) | 168/200 (84%) | 136/200 (68%) |
| Fluent / Baseline | 183/200 (92%) | 173/200 (87%) | 173/200 (87%) | 154/200 (77%)** |
| Mixed / Adaptive | 144/200 (72%) | 121/200 (61%) | 100/200 (50%) | 81/200 (41%) |
| Mixed / Baseline | 142/200 (71%) | 115/200 (58%) | 103/200 (52%) | 84/200 (42%) |

`**` = individually significant at p<0.05 (two-proportion z-test), and both favor the baseline.

### Session-length distribution (turns per session)

| Profile / Condition | min | p25 | median | p75 | max | mean |
|---|---|---|---|---|---|---|
| Struggling / Adaptive | 4 | 4.0 | 7.0 | 15.0 | 27 | 10.1 |
| Struggling / Baseline | 4 | 4.0 | 6.5 | 18.0 | 29 | 11.0 |
| Average / Adaptive | 4 | 5.8 | 14.0 | 21.0 | 31 | 14.1 |
| Average / Baseline | 4 | 8.8 | 19.0 | 22.0 | 28 | 15.8 |
| Fluent / Adaptive | 4 | 13.0 | 17.0 | 21.0 | 29 | 16.2 |
| Fluent / Baseline | 4 | 16.0 | 19.0 | 22.0 | 27 | 17.3 |
| Mixed / Adaptive | 4 | 4.0 | 13.0 | 19.0 | 29 | 12.5 |
| Mixed / Baseline | 4 | 4.0 | 15.0 | 21.0 | 28 | 13.7 |

A fixed session floor of 4 turns in both conditions is the zero-ability/fatigue-stop case
(3 wrong attempts + one demotion-fallback attempt, `backend/graph.py`'s `route_after_engagement`)
— it isn't a coincidence that both conditions share it, since that path is identical code in
both.

### Statistical notes

Two-proportion z-tests, n=200/condition, computed separately from the eval script (not part of
its own output):

| Comparison | adaptive | baseline | p-value | Survives BH-FDR (this 4-test family, α=0.05)? | Survives Bonferroni across all 24 tests run (α=0.00208)? |
|---|---|---|---|---|---|
| All-4 engine-confirmed, struggling | 4.0% | 1.5% | 0.126 | no | no |
| All-4 engine-confirmed, average | 21.5% | 12.5% | 0.017 | **yes** | no |
| All-4 engine-confirmed, fluent | 43.0% | 37.0% | 0.221 | no | no |
| All-4 engine-confirmed, mixed | 23.5% | 14.0% | 0.015 | **yes** | no |
| All-4 ground-truth, struggling | 6.5% | 6.0% | 0.836 | no | no |
| All-4 ground-truth, average | 29.5% | 27.5% | 0.658 | no | no |
| All-4 ground-truth, fluent | 56.0% | 64.0% | 0.102 | no | no |
| All-4 ground-truth, mixed | 27.5% | 31.0% | 0.442 | no | no |
| Per-skill ground-truth, average/addition_carry | 60.0% | 69.5% | 0.047 | n/a (16-test family, not checked) | no |
| Per-skill ground-truth, fluent/subtraction_borrow | 68.0% | 77.0% | 0.044 | n/a (16-test family, not checked) | no |

Plain read of this table: the average/mixed engine-confirmed advantage (roughly 9 percentage
points in both) is real enough to survive a same-family false-discovery-rate correction, but
not a maximally conservative Bonferroni correction across every test this analysis ran (24
total, across both metrics and all skill breakdowns). Nothing else in this evaluation clears
either bar. Take the headline claim in `README.md` as "a real, moderate effect on one specific
metric for two of four profiles" — not as proof the adaptive engine teaches better in some
general sense.

### Known limitations of this evaluation itself

- **Synthetic, not real, students.** The hidden slip/guess/learning-rate model is a
  standard two-state generative process, deliberately sampled from a wider range than the
  engine's own assumed `BKTParams` — but it is still a model, not classroom data.
- **`n=200` per profile is underpowered for the struggling profile specifically**: with only
  3-13 "all four skills" events out of 200 in that profile, small absolute count differences
  swing the percentage a lot and rarely reach significance regardless of the true effect size.
- **The baseline's `PROBLEMS_PER_SKILL=4` is one specific design choice**, not the only
  possible non-adaptive curriculum — a different fixed budget could close or widen either gap
  reported above. See `backend/eval/baseline.py`'s module docstring for why 4 was chosen
  (`quest_length` / 4 skills) and `PINNED_TIER`/`PROBLEMS_PER_SKILL` for how to try others.

### Reproducing this

```bash
uv run python -m backend.eval.simulate --n 200 --seed 0
```

Deterministic: `simulate.py` reseeds both each synthetic learner's own behavior RNG and
`backend.skills._arithmetic.default_rng` (the shared instance the problem generators draw
operands from), so a given `--seed` reproduces the same numbers exactly, including problem
content.
