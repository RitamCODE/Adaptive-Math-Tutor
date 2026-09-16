# Adaptive Math Tutor — Backend

A deterministic LangGraph state machine (curriculum, problem generation, grading, mastery tracking) wrapped in a thin FastAPI layer for the browser frontend in `../frontend`. Per the project's hard constraints (see root `CLAUDE.md`), grading, mastery updates, and curriculum selection are pure functions with no LLM involved anywhere in that path — the only LLM calls in this backend are four narrative touchpoints, isolated in `llm/narrative.py`. This file documents how the pieces actually fit together; `CLAUDE.md` remains the source of truth for scope and constraints.

## Directory map

```
backend/
  graph.py                the LangGraph StateGraph: wires the nodes below into one turn cycle
  api.py                  FastAPI app — the only HTTP-facing layer, talks to the compiled graph
  models/
    state.py               SessionState, Problem, LastResponse, Misconception, EngagementState,
                            DiagnosisResult, Remediation
    bkt.py                 BKTParams, MASTERY_THRESHOLD, update_mastery()
  nodes/
    curriculum.py           select_next_skill()
    problem_gen.py           generate_problem() — dispatches to skills/*.py
    diagnosis.py             grade_and_diagnose() — dispatches to each skill's BUG_RULES,
                             then cross_cutting.BUG_RULES, then looks up copy in content/misconceptions.json
    engagement.py            decide_engagement() — xp/streak/frustration/fatigue
    remediation.py           build_remediation() — projects a DiagnosisResult into the HTTP-facing Remediation shape
  skills/
    skill_graph.py           SkillGraph + DEFAULT_SKILL_GRAPH (the prerequisite DAG)
    _arithmetic.py           shared pure helpers used by every skill module
    addition_no_carry.py     template generator (no bug rules)
    addition_carry.py        template generator + 5 bug rules
    subtraction_no_borrow.py template generator (no bug rules)
    subtraction_borrow.py    template generator + 5 bug rules
    cross_cutting.py         skill-agnostic rules checked after a skill's own: digit_reversal, place_value_confusion
  content/
    misconceptions.json      hint + visual copy per bug_type — "detectors are code, copy is data"
  logging/
    events.py                SQLite event log, one row per submission (signal-bearing or not)
  llm/
    narrative.py             the four LLM touchpoints — the only file allowed to reference an LLM client
  tests/                    one file per module, see "Tests" below
```

## How a turn flows

The frontend never talks to individual nodes — it calls `POST /sessions/{id}/answer`, and `api.py` runs the compiled graph (`graph.app`, built by `build_graph()` in `graph.py`) via `graph.invoke()`, threading `SessionState` through in memory (no LangGraph checkpointer is configured — persistence is the caller's job, and here the caller is `api.py`'s in-memory session dict).

This is real conditional branching, not a linear pipeline (revision-plan Part 5 — "making the graph earn its place"):

```
Curriculum ──► Problem Gen ──► [student answers] ──► Diagnosis
                    ▲                                    │
                    │                         ┌──────────┼──────────┐
                    │                     correct    wrong, any    fatigue
                    │                         │       attempt        stop
                    │                         ▼          │            │
                    │                   update_mastery    │            │
                    │                         │           ▼            ▼
                    │                         │     Remediation   end_session
                    │                         │     (hint/visual/      │
                    │                         │      reveal_answer)    │
                    │                         ▼           │            │
                    │                  decide_engagement ◄┘            │
                    │                         │                        │
                    │           ┌─────────────┼─────────────┐          │
                    │      attempt < 3    attempt >= 3   mastered      │
                    │           │              │        (>= 0.8)       │
                    │           ▼              ▼             │         │
                    └── retry_problem    demote_skill   Curriculum ────┘
                        (same problem)   (prerequisite)  (advance_skill)
```

Inside the graph:

1. **Conditional entry** (`route_from_start`): if `state.last_response is None` (a brand-new session, or a request for a new problem with nothing to grade yet), go straight to `generate_problem`. Otherwise an answer is pending grading, so enter at `grade_and_diagnose`.
2. **Grading** (`grade_and_diagnose_node`) calls the pure `grade_and_diagnose()`, stores the full result on `state.last_diagnosis`, and — important — **overwrites** `last_response.correct` with its own verdict rather than trusting whatever the caller submitted. This is why `LastResponse.correct` is documented in `models/state.py` as provisional on input: the grading node is the sole source of truth, and every downstream node only ever sees the corrected value. A blank or sub-2-second "rapid guess" answer (`route_after_diagnosis`) skips straight to `hold_non_signal_node` instead — no attempt consumed, no BKT update, `next_action` just goes back to `retry_problem`.
3. **Remediation** (`route_after_diagnosis`, then `build_remediation_node`): a signal-bearing *wrong* answer routes here before anything else runs. It wraps the pure `build_remediation()` from `remediation.py` around `state.last_diagnosis`, storing the hint/visual/`reveal_answer` payload on `state.remediation`. It runs for every wrong attempt — 1, 2, and 3 alike — because `grade_and_diagnose` already bakes the visual in at attempt ≥ 2 and `reveal_answer=True` at attempt ≥ 3 into the diagnosis; attempt 3's "worked solution" moment is just this node's output with `reveal_answer` set, not a separate path. A correct answer skips straight past it to `update_mastery` — there's nothing to remediate.
4. **Signal-bearing chain** (linear from here): `update_mastery → decide_engagement`.
   - `update_mastery_node` runs the BKT posterior + transit update for the graded skill — except when the just-recorded bug type is `digit_reversal`, which CLAUDE.md requires not be penalized; that case is a no-op here (the retry ladder below still runs normally).
   - `decide_engagement_node` recomputes streak/xp/`frustration_signal`/`consecutive_wrong` from the same event.
5. **Post-engagement routing** (`route_after_engagement`) is where the retry ladder, demotion, and termination all live:
   - 4 consecutive signal-bearing wrong answers anywhere → `end_session` (the fatigue stop, checked first, regardless of this turn's own outcome).
   - Wrong, with attempts remaining (`attempt_number < 3`) → `retry_problem_node`: same problem stays on screen, only the attempt counter increments.
   - Wrong on the third attempt → `demote_skill_node`: re-serves a problem on the skill's prerequisite (or, for a root skill with no prerequisite, falls back to a fresh problem on the same skill).
   - Correct, and `quest_length` reached or 2 skills mastered → `end_session`.
   - Correct, and the graded skill's mastery is now `>= MASTERY_THRESHOLD` (0.8) → `advance_skill_node`, which picks the next skill (`select_next_skill`) and generates its first problem in one node — there's no `SessionState` field to carry a "just-chosen skill" across a separate hop, so selection and generation are fused here.
   - Correct otherwise → `new_problem_node`: another problem on the same skill.
6. Every node above (`generate_problem`, `hold_non_signal`, `new_problem`, `retry_problem`, `demote_skill`, `advance_skill`, `end_session`) terminates at `END`. Whatever `SessionState` comes out is what `api.py` stores back into its session dict and reshapes into the HTTP response — reading `last_diagnosis`/`remediation` straight off it rather than recomputing them.

## Data models (`models/state.py`)

- **`Problem`** — `question` (canonical `"a op b"` string), `correct_answer`, `skill_tag`, `difficulty`.
- **`LastResponse`** — `answer`, `correct`, `time_taken_sec`. `correct` is provisional when a caller submits a new answer (see above) — never trust it downstream of grading.
- **`Misconception`** — `skill`, `bug_type`, `timestamp`; appended to `SessionState.misconception_log` when an answer is wrong and a specific bug rule matched (excluded for `unclassified`, per `grade_and_diagnose_node` in `graph.py`).
- **`EngagementState`** — `streak`, `xp`, `frustration_signal`, `consecutive_wrong` (signal-bearing wrong answers in a row; drives the 4-in-a-row fatigue stop).
- **`SessionState`** — the full turn-to-turn state threaded through the graph: `student_id`, `session_id`, `skill_mastery` (dict of skill → BKT probability), `misconception_log`, `current_problem`, `attempt_number` (1-indexed, resets only on a new problem), `attempt_history` (`(answer, bug_type)` tuples for the current problem), `last_response`, `last_diagnosis` (the `DiagnosisResult` `grade_and_diagnose_node` just produced, `None` before any signal-bearing answer this turn), `remediation` (the `Remediation` `build_remediation_node` just produced, `None` on a correct answer or before grading), `engagement`, `problems_completed`, `quest_length` (default 10), `pending_resurface`/`resurface_progress`/`resurfaced_skills` (skill resurfacing bookkeeping — see below), `next_action`.

`pending_resurface` (the skill a demotion just moved the student off of), `resurface_progress` (correct answers on the prerequisite since that demotion), and `resurfaced_skills` (skills that already used their one resurface chance) implement skill resurfacing (revision-plan §7.3): `demote_skill_node` sets `pending_resurface`, a `resurface_skill_node` brings that skill back once `resurface_progress` reaches 2 — deliberately bypassing the 0.8 mastery-threshold check, since the prerequisite being re-answered correctly twice is itself the signal — and a second attempt-3 failure on the resurfaced skill ends the quest rather than demoting again.
- **`DiagnosisResult`** (also in `models/state.py`) — `correct`, `bug_type | None`, `hint`, `visual`, `attempts_remaining`, `reveal_answer`; what `grade_and_diagnose()` returns.
- **`Remediation`** — `hint`, `visual`, `reveal_answer`; a subset of `DiagnosisResult` projected by `build_remediation()`, and wired into the graph as `build_remediation_node` (see "How a turn flows" above) — a seam for remediation-specific shaping (manipulative payload detail, worked-solution steps) to grow into later without touching the pure grading path.
- **`BKTParams`** (`models/bkt.py`) — `p_init=0.3`, `p_transit=0.15`, `p_slip=0.1`, `p_guess=0.05`.

## Mastery model (BKT) — `models/bkt.py`

`update_mastery(mastery, skill, correct, params)` implements the standard Bayesian Knowledge Tracing update exactly as specified in `CLAUDE.md`: a Bayesian posterior update from the observed correct/incorrect response, followed by the fixed learning-transit step. `MASTERY_THRESHOLD = 0.8` is imported from here by both `graph.py` (routing) and `curriculum.py` (unlock checks) — it's the single definition of "mastered" in the codebase. The function returns a new dict rather than mutating its input.

## Skills: templates + bug rules (`skills/`)

Every skill module exports the same three things, dispatched by tag from `nodes/problem_gen.py` and `nodes/diagnosis.py`:

- `SKILL_TAG: str`
- `generate(difficulty: float, rng: random.Random | None = None) -> Problem`
- `BUG_RULES: list[tuple[str, Callable[[Problem, int], bool]]]` — empty for skills with no documented misconceptions (`addition_no_carry`, `subtraction_no_borrow`).

`_arithmetic.py` holds the shared pure helpers every generator uses: digit-width helpers, `has_any_carry`/`has_any_borrow` (used both to build problems that require carrying/borrowing and to build ones that deliberately don't), `format_question`/`parse_operands` (the canonical `"a op b"` string and its inverse — any future flavor-text wrapper must preserve this round-trip), and `bucket(difficulty)` mapping a float to `easy`/`medium`/`hard` template widths.

`grade_and_diagnose` (`nodes/diagnosis.py`) checks a wrong answer against a skill's `BUG_RULES` **in order**, then against `skills/cross_cutting.py`'s skill-agnostic `BUG_RULES` (`digit_reversal`, `place_value_confusion` — these only look at the answer and the correct answer, not the operands, so they apply to any skill), and returns the first match; no match falls back to `unclassified`. Order encodes priority when more than one rule could theoretically fire:

- `addition_carry.py` (5): `add_concat_no_carry` (the `86 + 94 → 1017` catalog case), `add_carry_wrong_column`, `no_carry` (column overflow truncated mod 10 — kept under its pre-catalog name rather than CLAUDE.md's `add_carry_dropped`, by request), `add_off_by_one`, `add_used_subtraction`.
- `subtraction_borrow.py` (5): `reversed_operands`, `sub_zero_minus_n`, `sub_borrow_across_zero`, `no_borrow_smaller_from_larger` (kept under its pre-catalog name rather than `sub_smaller_from_larger`), `off_by_ten_in_borrow` (kept rather than `sub_borrow_no_decrement`).

The hint text and `visual` payload key for every `bug_type` — including `unclassified`'s procedural nudge, which never reveals the answer — live in `content/misconceptions.json`, not in the skill modules. Detectors are code, copy is data: retuning a hint's wording never touches `diagnosis.py` or the skill files, and every hint is machine-checked at ≤12 words in `tests/test_misconceptions_catalog.py` rather than eyeballed.

The prerequisite DAG lives in `skills/skill_graph.py` as `DEFAULT_SKILL_GRAPH` — currently a strict linear chain:

```
addition_no_carry → addition_carry → subtraction_no_borrow → subtraction_borrow
```

`select_next_skill()` (`nodes/curriculum.py`) walks `topological_order()` and returns the first skill that's unlocked (all prerequisites mastered) and not yet mastered itself; if everything is mastered it falls back to the last skill in order (there's no distinct "curriculum complete" state).

## Event log (`logging/events.py`)

`log_submission(...)` appends one SQLite row per submission to `event_log.db` (repo root) — signal-bearing or not, correct or not, `unclassified` included. It's pure I/O with no bearing on grading/mastery/curriculum, so it's dispatched from `api.py` via `BackgroundTasks` and never sits on the submit-to-verdict critical path. The point of logging `unclassified` rows specifically is that the misconception catalog above is meant to keep growing from real data, not just from `CLAUDE.md`'s starter list.

## LLM touchpoints (`llm/narrative.py`)

The only four LLM calls anywhere in this backend, all fail-open (`None` on a missing API key, timeout, or any error — never raises):

| Function | Fires | Input |
|---|---|---|
| `flavor_word_problem` | optionally, wrapping a freshly generated problem | question, correct answer, skill, difficulty |
| `mastery_moment_narrative` | once, on the `advance_skill` transition | the mastered skill, its misconception log entries, attempt count |
| `effort_reward_narrative` | on every correct answer | skill, attempt count, average time per attempt |
| `boss_battle_narrative` | alongside the mastery moment, for the newly entered skill | the new skill name |

None of these run inside the graph — they're all invoked from `api.py`, *after* `graph.invoke()` returns, using per-session attempt/time tracking (`_ATTEMPTS`) that lives in the API layer, not in `SessionState` (the schema is frozen per `CLAUDE.md` and isn't extended just to carry LLM-input bookkeeping). Isolation is grep-verifiable: `git ls-files 'backend/*.py' | xargs grep -l openai` should only ever return this file.

`narrative.py`'s `_client()` wraps the OpenAI client with `wrap_openai` (the LangSmith SDK helper that instruments a client so every completion call auto-emits a traced run) — necessary because all four touchpoints run from FastAPI background tasks and the `/narrative` endpoint, never inside `graph.app.invoke()`, so LangGraph's own auto-tracing alone would never see them. `flavor_word_problem` additionally enforces the 20-word/one-name/one-object/digits-not-words cap from `CLAUDE.md`'s copy limits in code: it validates the generated text against the cap and regenerates once with a "too long" nudge before falling back to `None` (the plain numeric problem) if it still overruns.

## HTTP API (`api.py`)

| Endpoint | Method | Does |
|---|---|---|
| `/sessions` | POST | start a new session for a `student_id` |
| `/sessions/{id}` | GET | resume an existing session |
| `/sessions/seed/{name}` | POST | install one of the three fixed demo profiles (`new`/`struggling`/`fluent`) without playing through a real session — backs the `?seed=` URL param |
| `/sessions/{id}/restore` | POST | reinstall a session's mastery/XP/misconceptions from the frontend's own cached (correct-answer-free) snapshot after the backend process restarts and loses its in-memory session store |
| `/sessions/{id}/answer` | POST | grade an answer, advance the turn, return the next state |
| `/sessions/{id}/narrative` | GET | fetch the four LLM touchpoints for the most recent answer, once they resolve |
| `/misconceptions` | GET | serve the hint + visual catalog keyed by `bug_type` from `content/misconceptions.json` — used by the end-of-quest report to label repaired misconceptions by name |

`submit_answer` makes zero LLM calls — that's the whole point of splitting `/narrative` out as its own endpoint (CLAUDE.md's <150ms submit-to-verdict budget). The frontend calls it right after rendering the instant verdict and merges the result in whenever it resolves; results are cached per `context_id` so a duplicate fetch (e.g. a retry attempt with no new mastery/reward event) doesn't re-call the LLM.

Session state (plus the flavor-text cache, attempt tracker, and narrative context/cache) lives in plain in-memory dicts keyed by `session_id` — restarting the process drops every session, and this only works correctly with a single uvicorn worker. This matches `CLAUDE.md`'s "no persistence beyond current session" non-goal; it is not an oversight. (The event log above is the one piece of durable storage in the system, and it's a separate SQLite file, not session state.)

The HTTP response models (`SessionResponse`, `AnswerResponse`, `Feedback`, `SkillProgress`, `ProblemOut`, `NarrativeOut`) are deliberately separate from `SessionState` — the wire format hides things the frontend shouldn't see and derives things it needs that `SessionState` doesn't carry directly:

- `current_problem.correct_answer` is never sent before grading; inside `Feedback` it's still withheld unless the answer was correct or `reveal_answer` is true (attempt 3), per constraint #7.
- `misconception_log` and raw `skill_mastery` never reach the client at all — only the derived `skill_progress` list (`skill`, `mastery`, `unlocked`, `mastered` per skill, computed from `DEFAULT_SKILL_GRAPH`) and, per answer, a single `Feedback` object.

CORS (`CORSMiddleware`) allowlists exactly `http://localhost:5173` and `127.0.0.1:5173` — the Vite dev server's default port.

## How this connects to the frontend

See `../frontend/README.md` for the frontend's side of this contract in detail. In short: `frontend/src/api.js` hardcodes `API_BASE = "http://localhost:8000"` and calls exactly the four endpoints above; if either port changes, both this file's CORS allowlist and the frontend's `API_BASE` need updating together. `Feedback.hint` is already display-ready copy (sourced from `content/misconceptions.json`), so a new bug rule needs no frontend change to show its hint. The one raw tag the frontend still translates itself is `skill_tag` — `frontend/src/constants.js`'s `SKILL_DISPLAY_NAMES` maps it to a display name for the skill trail map (an unmapped tag falls back gracefully to the raw string), so adding a fifth skill means adding an entry there too.

## Running it

```bash
# from the repo root
uv run uvicorn backend.api:app --reload --port 8000
```

## Tests (`tests/`)

| File | Covers |
|---|---|
| `test_api.py` | the four HTTP endpoints |
| `test_bkt.py` | `update_mastery()` posterior/transit math |
| `test_bug_rules.py` | every misconception detector firing on a known wrong answer, including the `86 + 94 → 1017` catalog case |
| `test_curriculum.py` | `select_next_skill()` |
| `test_engagement.py` | `decide_engagement()` |
| `test_events.py` | `logging/events.py` — signal/non-signal rows land correctly in the SQLite log |
| `test_graph.py` | a scripted session driving `graph.invoke()` end to end |
| `test_misconceptions_catalog.py` | every `bug_type` in `content/misconceptions.json` has a hint ≤12 words, machine-checked |
| `test_narrative.py` | the four LLM touchpoints' fail-open behavior and isolation |
| `test_problem_gen.py` | per-skill template generators |
| `test_retry_ladder.py` | the 3-attempt retry ladder, prerequisite demotion, and quest/fatigue termination routing |
| `test_skill_graph.py` | the prerequisite DAG (`is_unlocked`, `topological_order`) |
| `conftest.py` | shared fixtures |

```bash
uv run pytest
```

## Extending the system

To add a fifth skill: write a new module in `skills/` exporting `SKILL_TAG`, `generate()`, and `BUG_RULES`; register it in `nodes/problem_gen.py`'s `_GENERATORS` and `nodes/diagnosis.py`'s `_BUG_RULES` dicts; add it (with its prerequisites) to `DEFAULT_SKILL_GRAPH` in `skills/skill_graph.py`; add a hint + `visual` entry per new `bug_type` to `content/misconceptions.json`; and add a display name to `frontend/src/constants.js`'s `SKILL_DISPLAY_NAMES` so the skill trail map renders something other than the raw tag. Nothing in `graph.py`, `models/`, or `nodes/` (other than those two dispatch dicts) needs to change — the graph and the deterministic nodes are skill-agnostic by design.

Any change beyond that — a fifth LLM call, a new dependency, a new node or orchestration layer — needs sign-off first, per `CLAUDE.md`'s hard constraints.
