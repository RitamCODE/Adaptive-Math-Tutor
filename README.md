# Adaptive Math Tutor

A K-5 adaptive math learning app built for the Nerdy AI Hackathon (Prompt 01: K-5 Math Game).

The one idea everything else follows from: **grading, mastery tracking, and curriculum selection are a deterministic state machine — an LLM never touches them.** A student's mastery of each skill is tracked with Bayesian Knowledge Tracing, wrong answers are diagnosed against a catalog of known misconception rules (not just marked wrong), and what problem to serve next falls out of that real data. The only four places an LLM is allowed to speak are narrating what already happened — never deciding it. That split is why the codebase is organized the way it is: a pure, fully-tested engine in `backend/`, with exactly one file (`backend/llm/narrative.py`) permitted to import an LLM client.

This file is the map between the pieces. For implementation detail, `backend/README.md` and `frontend/README.md` go much deeper into each half; `CLAUDE.md` is the source-of-truth spec (constraints, data models, algorithms) that both were built against.

## How a turn flows

```
NumberPad → App.jsx ──POST /sessions/{id}/answer──▶ api.py ──graph.invoke()──▶ LangGraph StateGraph
                                                                                      │
                          ┌───────────────────────────────────────────────────────────┘
                          ▼
     grade_and_diagnose ──▶ update_mastery (BKT) ──▶ decide_engagement
                          │
                          ▼ route_after_engagement
     retry_problem  /  new_problem  /  advance_skill  /  demote_skill  /  end_session
                          │
                          ▼
     api.py reshapes SessionState → AnswerResponse ──▶ App.jsx renders the verdict
                                                              │
                                          (separately, fire-and-forget)
                                                              ▼
                                     GET /sessions/{id}/narrative → the 4 LLM touchpoints
```

One submission, traced end to end:

1. The frontend never talks to individual graph nodes — `App.jsx` calls `POST /sessions/{id}/answer`, and `api.py`'s `submit_answer` is the only thing that invokes the compiled graph (`build_graph()` in `backend/graph.py`), threading `SessionState` through in memory (no checkpointer — persistence, such as it is, is the caller's job).
2. Inside the graph, a pending answer enters at `grade_and_diagnose_node`, which calls the pure `grade_and_diagnose()` and **overwrites** `last_response.correct` with its own verdict — this is why `LastResponse.correct` is documented as provisional on input: grading is the sole source of truth, and everything downstream only ever sees the corrected value.
3. `update_mastery_node` runs the BKT posterior + transit update for the graded skill (skipped for `digit_reversal` — CLAUDE.md requires mastery not be penalized for that one). `decide_engagement_node` recomputes streak/xp/frustration from the same event.
4. `route_after_engagement` is where the retry ladder actually lives: 4 consecutive signal-bearing wrong answers anywhere → `end_session`; wrong with attempts left → `retry_problem` (same problem stays on screen); wrong on the third attempt → `demote_skill` (re-serves a problem on the prerequisite); correct and the skill passes the sustained-mastery gate (at or above 0.8 after each of the last 3 signal-bearing answers, not merely crossed once) → `advance_skill`; correct otherwise → `new_problem`; both parent skills mastered, or quest length reached → `end_session`.
5. Every branch terminates at `END`. `api.py` stores whatever `SessionState` comes out and reshapes it into `AnswerResponse` — the client gets a derived `skill_progress` list (each sub-skill's mastery, lock state, `mastered` flag and parent group) plus a `group_progress` aggregate and a per-answer `Feedback` object, and `correct_answer` is withheld from `Feedback` until either the answer is right or attempt 3 is reached (constraint #7). Raw `skill_mastery`/`mastery_run`/`misconception_log` are sent too, but purely so the browser can cache a complete, answer-free session snapshot for refresh and restart recovery.
6. The four LLM narrative calls are deliberately **not** in this graph at all. They're fetched by the frontend from a separate `GET /sessions/{id}/narrative` right after the verdict renders, so no LLM call can ever sit between submit and the verdict (the <150ms latency budget). A blank or sub-2-second "rapid guess" answer routes to `hold_non_signal_node` instead — no attempt consumed, no BKT update, still logged to the event log.

## The four LLM touchpoints (`backend/llm/narrative.py`)

The only file in the backend allowed to import an LLM client — grep-verifiable (`git ls-files 'backend/*.py' | xargs grep -l openai` returns exactly this one file). Every function is fail-open: a missing `OPENAI_API_KEY`, a timeout, or any error collapses to `None`, and callers fall back to plain hardcoded copy.

| Touchpoint | Fires | Depends on |
|---|---|---|
| `flavor_word_problem` | wrapping a freshly generated problem | question, answer, skill, difficulty |
| `mastery_moment_narrative` | once, on `advance_skill` | the mastered skill's misconception log, attempt count |
| `effort_reward_narrative` | every correct answer | attempt count and average time-per-attempt on that skill |
| `boss_battle_narrative` | alongside the mastery moment | the newly entered skill |

The rule that keeps this list at four: an LLM call has to depend on *this student's* specific session data. If the sentence could be written without knowing anything about this particular student, it's decoration and doesn't belong here.

## Project structure

```
backend/
  api.py                  FastAPI app — the only HTTP-facing layer
  graph.py                the LangGraph StateGraph: wires every node into one turn cycle
  models/
    state.py               SessionState, Problem, LastResponse, Misconception,
                            EngagementState, DiagnosisResult, Remediation
    bkt.py                 BKTParams, MASTERY_THRESHOLD (0.8), MASTERY_MIN_RUN (3),
                            update_mastery(), is_mastered()
  nodes/
    curriculum.py           select_next_skill()
    problem_gen.py          generate_problem() — dispatches to skills/*.py
    diagnosis.py            grade_and_diagnose() — dispatches to each skill's BUG_RULES
    engagement.py           decide_engagement() — xp/streak/frustration/fatigue
    remediation.py          build_remediation() — shapes hint/visual for the HTTP response
  skills/
    skill_graph.py           DEFAULT_SKILL_GRAPH, the prerequisite DAG
    _arithmetic.py            shared pure helpers (digit width, carry/borrow detection, formatting)
    addition_no_carry.py / addition_carry.py
    subtraction_no_borrow.py / subtraction_borrow.py
    cross_cutting.py          skill-agnostic rules: digit_reversal, place_value_confusion
  content/
    misconceptions.json      hint + visual copy per bug_type — "detectors are code, copy is data"
  logging/
    events.py                SQLite event log, one row per submission (signal or not)
  llm/
    narrative.py             the four touchpoints above
  tests/                     one file per module, 100+ tests
frontend/
  src/
    App.jsx                  the single state owner
    api.js                   fetch wrappers for the backend endpoints
    constants.js              skill/bug-type tags → display copy
    components/               ProblemCard, NumberPad, FeedbackBanner, SkillTrailMap, StatsBar, Mascot,
                              StudentIdForm, SessionSummary, BundlingSticks, NumberLine, TenFrame
  lib/                        arithmetic.js, remediation.js, praise.js, sound.js
docs/
  revision-plan.md           the original revision plan, kept as a frozen historical record
                              (see docs/DOCS_AUDIT.md); CLAUDE.md is the living source of truth
  CHECKLIST.md                manual, per-item verification checklist for that plan
```

The prerequisite chain is currently a straight line: `addition_no_carry → addition_carry → subtraction_no_borrow → subtraction_borrow`. `select_next_skill()` walks it in topological order and returns the first unlocked, unmastered skill.

Layered on top, the same four skills are grouped into two **parent skills** — Addition (`addition_no_carry`, `addition_carry`) and Subtraction (`subtraction_no_borrow`, `subtraction_borrow`). Each sub-skill keeps its own mastery value and threshold; a parent is mastered only when both of its sub-skills are, and the quest ends when both parents are. Grouping affects aggregation and reporting only — traversal order is unchanged.

## Running it locally

Two servers, run simultaneously in separate terminals — `frontend/src/api.js` hardcodes `http://localhost:8000` and the backend's CORS allowlist only permits `:5173`/`127.0.0.1:5173`.

```bash
# backend, from the repo root
uv run uvicorn backend.api:app --reload --port 8000
```

```bash
# frontend
cd frontend
npm install
npm run dev        # http://localhost:5173
```

An `OPENAI_API_KEY` in a repo-root `.env` is optional — without it, all four narrative touchpoints silently fall back to hardcoded copy instead of failing.

`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT` in the same `.env` are also optional — without them, the app runs identically, just untraced. With them set, each of the four narrative touchpoints (the LLM calls listed above) shows up as a traced run at [smith.langchain.com](https://smith.langchain.com) under the named project.

```bash
uv run pytest       # backend test suite
```

## Current status

**Working**, per `CLAUDE.md`'s task breakdown and verified in `docs/CHECKLIST.md`:
- Skill DAG, deterministic per-skill problem templates, exact BKT mastery tracking
- Full misconception catalog — 13 bug types across addition/subtraction plus the two cross-cutting rules (`digit_reversal`, `place_value_confusion`), hint/visual copy externalized to `content/misconceptions.json`, machine-checked at ≤12 words
- LangGraph routing including the three-attempt retry ladder, prerequisite demotion, and session termination (both parent skills mastered, quest length, or 4 consecutive wrong)
- Sustained-mastery gate: a skill counts as mastered only after holding 0.8 across 3 consecutive signal-bearing answers, so one lucky correct answer no longer completes a skill
- Non-signal handling (blank/rapid-guess answers skip BKT and the attempt counter, but still hit the event log)
- SQLite event log, one row per submission — the substrate the misconception catalog is meant to keep growing from
- The four LLM touchpoints, fail-open, isolated to one file, traced to LangSmith when `LANGSMITH_*` env vars are set
- Latency split: the verdict is a pure ~6-15ms round trip; narrative is fetched separately and never blocks it
- Vite + React frontend end to end: number pad, skill trail map, growth-stage mascot, responsive mobile/tablet/laptop layout
- Three manipulatives (bundling sticks, number line, ten-frame) delivered as remediation rather than default furniture: never shown on attempt 1, always available on request, and CRA-fading off live BKT mastery — below 0.4 a wrong answer opens them pre-loaded with the student's own answer, 0.4–0.7 offers them one tap away, above 0.7 the hint stands alone
- A real end-of-quest report (skills mastered, misconceptions repaired by name, problems solved, elapsed time, "Play again") and three synthesized sound effects
- Seeded demo profiles (`?seed=new|struggling|fluent`) and refresh-mid-session/backend-restart recovery via `localStorage`
- Skill resurfacing: a demoted skill returns once after two correct answers on its prerequisite, per `docs/revision-plan.md` §7.3

**Not yet built** (see `docs/revision-plan.md` Parts 4-7 and the open items in `docs/CHECKLIST.md`):
- The worked-solution animation on the third failed attempt
- Session *state* persistence beyond the process lifetime — the new event log is durable SQLite, but `SessionState` itself still lives in an in-memory dict and is lost on backend restart (the `/restore` endpoint reinstalls mastery/XP/misconceptions from the browser's own cache, but a fresh problem is generated rather than the exact in-flight one)
- The demo video walkthrough (revision-plan Part 8, Day 7)

## Does the adaptive engine actually help? A synthetic-student evaluation

BKT mastery tracking is only worth having if it changes outcomes for real students, not just
its own bookkeeping. `backend/eval/` checks that directly: synthetic students with a hidden
true mastery, slip, guess, and learning rate per skill — sampled independently of the numbers
the engine itself assumes — are driven through the actual compiled graph turn-by-turn (no
mocks, no shortcuts) and compared against a fixed-schedule, fixed-difficulty baseline given the
identical 16-problem budget. Every run is scored two ways: against the engine's own
BKT-confirmed mastery, and against the synthetic student's hidden ground truth, which the
engine never sees.

| Profile | Engine-confirmed, adaptive | Engine-confirmed, baseline | Ground-truth, adaptive | Ground-truth, baseline |
|---|---|---|---|---|
| Struggling | 4% | 2% | 7% | 6% |
| Average | 22% | 13% | 30% | 28% |
| Fluent | 43% | 37% | 56% | 64% |
| Mixed | 24% | 14% | 28% | 31% |

Given the identical practice budget, adaptive pacing shows a real, roughly 9-point edge in how
often the engine's own sustained-evidence gate — not merely crossed once, but held for 3
consecutive answers — can actually *confirm* all four skills mastered, for average- and
mixed-ability populations. On the harder question underneath that — did the student really
learn the material, independent of whether the tracking can prove it — the two conditions come
out statistically indistinguishable at this sample size in every profile, and in 2 of the 16
individual skill comparisons the fixed baseline comes out ahead instead, not adaptive. Full
breakdown, exact test statistics, and the multiple-comparisons caveat behind both of those
claims: [`KNOWN_GAPS.md`](KNOWN_GAPS.md).

## Further reading

- `backend/README.md` — the backend in depth: data models, the BKT formulas, the skill/bug-rule module contract, the HTTP API shape
- `frontend/README.md` — the frontend in depth: component tree, state flow, the backend contract it's coupled to
- `CLAUDE.md` — the full spec: hard constraints, exact algorithms, copy limits, non-goals
- `docs/revision-plan.md` / `docs/CHECKLIST.md` — the active work plan and its manual verification checklist
- `KNOWN_GAPS.md` — the simulated-learner evaluation in full: every profile, every skill, session-length distributions, and the statistics behind the summary above
- `CHANGELOG.md` — what actually landed, session by session
