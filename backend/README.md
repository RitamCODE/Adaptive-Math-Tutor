# Adaptive Math Tutor — Backend

A deterministic LangGraph state machine (curriculum, problem generation, grading, mastery tracking) wrapped in a thin FastAPI layer for the browser frontend in `../frontend`. Per the project's hard constraints (see root `CLAUDE.md`), grading, mastery updates, and curriculum selection are pure functions with no LLM involved anywhere in that path — the only LLM calls in this backend are four narrative touchpoints, isolated in `llm/narrative.py`. This file documents how the pieces actually fit together; `CLAUDE.md` remains the source of truth for scope and constraints.

## Directory map

```
backend/
  graph.py                the LangGraph StateGraph: wires the nodes below into one turn cycle
  api.py                  FastAPI app — the only HTTP-facing layer, talks to the compiled graph
  models/
    state.py               SessionState, Problem, LastResponse, Misconception, EngagementState, DiagnosisResult
    bkt.py                 BKTParams, MASTERY_THRESHOLD, update_mastery()
  nodes/
    curriculum.py           select_next_skill()
    problem_gen.py           generate_problem() — dispatches to skills/*.py
    diagnosis.py             grade_and_diagnose() — dispatches to each skill's BUG_RULES
    engagement.py            decide_engagement() — xp/streak/frustration
  skills/
    skill_graph.py           SkillGraph + DEFAULT_SKILL_GRAPH (the prerequisite DAG)
    _arithmetic.py           shared pure helpers used by every skill module
    addition_no_carry.py     template generator (no bug rules)
    addition_carry.py        template generator + the "no_carry" bug rule
    subtraction_no_borrow.py template generator (no bug rules)
    subtraction_borrow.py    template generator + 3 bug rules
  llm/
    narrative.py             the four LLM touchpoints — the only file allowed to reference an LLM client
  tests/                    one file per module, see "Tests" below
```

## How a turn flows

The frontend never talks to individual nodes — it calls `POST /sessions/{id}/answer`, and `api.py` runs the compiled graph (`graph.app`, built by `build_graph()` in `graph.py`) via `graph.invoke()`, threading `SessionState` through in memory (no LangGraph checkpointer is configured — persistence is the caller's job, and here the caller is `api.py`'s in-memory session dict).

Inside the graph:

1. **Conditional entry** (`route_from_start`): if `state.last_response is None` (a brand-new session, or a request for a new problem with nothing to grade yet), go straight to `generate_problem`. Otherwise an answer is pending grading, so enter at `grade_and_diagnose`.
2. **Grading chain** (linear): `grade_and_diagnose → update_mastery → decide_engagement`.
   - `grade_and_diagnose_node` calls the pure `grade_and_diagnose()` and — important — **overwrites** `last_response.correct` with its own verdict rather than trusting whatever the caller submitted. This is why `LastResponse.correct` is documented in `models/state.py` as provisional on input: the grading node is the sole source of truth, and every downstream node (including `update_mastery`) only ever sees the corrected value.
   - `update_mastery_node` runs the BKT update for the just-graded skill.
   - `decide_engagement_node` recomputes xp/streak/frustration from the same event.
3. **Post-engagement routing** (`route_after_engagement`): if the current skill's mastery is now `>= MASTERY_THRESHOLD` (0.8), route to `advance_skill`; otherwise `repeat_skill`.
   - `advance_skill_node` picks the next skill (`select_next_skill`) and generates its first problem in one node — there's no `SessionState` field to carry a "just-chosen skill" across a separate hop, so selection and generation are fused here.
   - `repeat_skill_node` just generates another problem for the same skill.
4. Both branches, and the fresh-session `generate_problem` entry, terminate at `END`. Whatever `SessionState` comes out is what `api.py` stores back into its session dict and reshapes into the HTTP response.

## Data models (`models/state.py`)

- **`Problem`** — `question` (canonical `"a op b"` string), `correct_answer`, `skill_tag`, `difficulty`.
- **`LastResponse`** — `answer`, `correct`, `time_taken_sec`. `correct` is provisional when a caller submits a new answer (see above) — never trust it downstream of grading.
- **`Misconception`** — `skill`, `bug_type`, `timestamp`; appended to `SessionState.misconception_log` only when an answer is wrong *and* a bug rule actually matched.
- **`EngagementState`** — `streak`, `xp`, `frustration_signal`.
- **`SessionState`** — the full turn-to-turn state threaded through the graph: `student_id`, `session_id`, `skill_mastery` (dict of skill → BKT probability), `misconception_log`, `current_problem`, `last_response`, `engagement`, `next_action`.
- **`DiagnosisResult`** (also in `models/state.py`) — `correct`, `bug_type | None`; what `grade_and_diagnose()` returns.
- **`BKTParams`** (`models/bkt.py`) — `p_init=0.3`, `p_transit=0.15`, `p_slip=0.1`, `p_guess=0.05`.

## Mastery model (BKT) — `models/bkt.py`

`update_mastery(mastery, skill, correct, params)` implements the standard Bayesian Knowledge Tracing update exactly as specified in `CLAUDE.md`: a Bayesian posterior update from the observed correct/incorrect response, followed by the fixed learning-transit step. `MASTERY_THRESHOLD = 0.8` is imported from here by both `graph.py` (routing) and `curriculum.py` (unlock checks) — it's the single definition of "mastered" in the codebase. The function returns a new dict rather than mutating its input.

## Skills: templates + bug rules (`skills/`)

Every skill module exports the same three things, dispatched by tag from `nodes/problem_gen.py` and `nodes/diagnosis.py`:

- `SKILL_TAG: str`
- `generate(difficulty: float, rng: random.Random | None = None) -> Problem`
- `BUG_RULES: list[tuple[str, Callable[[Problem, int], bool]]]` — empty for skills with no documented misconceptions (`addition_no_carry`, `subtraction_no_borrow`).

`_arithmetic.py` holds the shared pure helpers every generator uses: digit-width helpers, `has_any_carry`/`has_any_borrow` (used both to build problems that require carrying/borrowing and to build ones that deliberately don't), `format_question`/`parse_operands` (the canonical `"a op b"` string and its inverse — any future flavor-text wrapper must preserve this round-trip), and `bucket(difficulty)` mapping a float to `easy`/`medium`/`hard` template widths.

`grade_and_diagnose` checks a wrong answer against a skill's `BUG_RULES` **in order** and returns the first match — order encodes priority when more than one rule could theoretically fire. `subtraction_borrow.py` has three, checked in this order: reversed operands, no-borrow (column-wise absolute difference), off-by-ten-in-the-borrowed-place. `addition_carry.py` has one: no-carry (digit-wise sum, overflow truncated instead of carried).

The prerequisite DAG lives in `skills/skill_graph.py` as `DEFAULT_SKILL_GRAPH` — currently a strict linear chain:

```
addition_no_carry → addition_carry → subtraction_no_borrow → subtraction_borrow
```

`select_next_skill()` (`nodes/curriculum.py`) walks `topological_order()` and returns the first skill that's unlocked (all prerequisites mastered) and not yet mastered itself; if everything is mastered it falls back to the last skill in order (there's no distinct "curriculum complete" state).

## LLM touchpoints (`llm/narrative.py`)

The only four LLM calls anywhere in this backend, all fail-open (`None` on a missing API key, timeout, or any error — never raises):

| Function | Fires | Input |
|---|---|---|
| `flavor_word_problem` | optionally, wrapping a freshly generated problem | question, correct answer, skill, difficulty |
| `mastery_moment_narrative` | once, on the `advance_skill` transition | the mastered skill, its misconception log entries, attempt count |
| `effort_reward_narrative` | on every correct answer | skill, attempt count, average time per attempt |
| `boss_battle_narrative` | alongside the mastery moment, for the newly entered skill | the new skill name |

None of these run inside the graph — they're all invoked from `api.py`, *after* `graph.invoke()` returns, using per-session attempt/time tracking (`_ATTEMPTS`) that lives in the API layer, not in `SessionState` (the schema is frozen per `CLAUDE.md` and isn't extended just to carry LLM-input bookkeeping). Isolation is grep-verifiable: `git ls-files 'backend/*.py' | xargs grep -l openai` should only ever return this file.

## HTTP API (`api.py`)

| Endpoint | Method | Does |
|---|---|---|
| `/sessions` | POST | start a new session for a `student_id` |
| `/sessions/{id}` | GET | resume an existing session |
| `/sessions/{id}/answer` | POST | grade an answer, advance the turn, return the next state |

Session state (plus the flavor-text cache and attempt tracker) lives in plain in-memory dicts keyed by `session_id` — restarting the process drops every session, and this only works correctly with a single uvicorn worker. This matches `CLAUDE.md`'s "no persistence beyond current session" non-goal; it is not an oversight.

The HTTP response models (`SessionResponse`, `AnswerResponse`, `Feedback`, `SkillProgress`, `ProblemOut`) are deliberately separate from `SessionState` — the wire format hides things the frontend shouldn't see and derives things it needs that `SessionState` doesn't carry directly:

- `current_problem.correct_answer` is never sent before grading (only inside `Feedback`, after the fact).
- `misconception_log` and raw `skill_mastery` never reach the client at all — only the derived `skill_progress` list (`skill`, `mastery`, `unlocked`, `mastered` per skill, computed from `DEFAULT_SKILL_GRAPH`) and, per answer, a single `Feedback` object.

CORS (`CORSMiddleware`) allowlists exactly `http://localhost:5173` and `127.0.0.1:5173` — the Vite dev server's default port.

## How this connects to the frontend

See `../frontend/README.md` for the frontend's side of this contract in detail. In short: `frontend/src/api.js` hardcodes `API_BASE = "http://localhost:8000"` and calls exactly the three endpoints above; if either port changes, both this file's CORS allowlist and the frontend's `API_BASE` need updating together. The backend deliberately sends raw tags (`skill_tag`, `bug_type`) rather than display text — `frontend/src/constants.js` is where those tags get turned into copy a student sees, so adding a skill or bug rule here means adding a matching entry there (an unmapped tag falls back gracefully to the raw string, it doesn't break).

## Running it

```bash
# from the repo root
uv run uvicorn backend.api:app --reload --port 8000
```

## Tests (`tests/`)

| File | Covers |
|---|---|
| `test_api.py` | the three HTTP endpoints |
| `test_bkt.py` | `update_mastery()` posterior/transit math |
| `test_bug_rules.py` | the misconception detectors firing on known wrong answers |
| `test_curriculum.py` | `select_next_skill()` |
| `test_engagement.py` | `decide_engagement()` |
| `test_graph.py` | a scripted session driving `graph.invoke()` end to end |
| `test_narrative.py` | the four LLM touchpoints' fail-open behavior and isolation |
| `test_problem_gen.py` | per-skill template generators |
| `test_skill_graph.py` | the prerequisite DAG (`is_unlocked`, `topological_order`) |
| `conftest.py` | shared fixtures |

```bash
uv run pytest
```

## Extending the system

To add a fifth skill: write a new module in `skills/` exporting `SKILL_TAG`, `generate()`, and `BUG_RULES`; register it in `nodes/problem_gen.py`'s `_GENERATORS` and `nodes/diagnosis.py`'s `_BUG_RULES` dicts; add it (with its prerequisites) to `DEFAULT_SKILL_GRAPH` in `skills/skill_graph.py`; and add a display name / bug-hint entry in `frontend/src/constants.js` so the frontend renders something other than the raw tag. Nothing in `graph.py`, `models/`, or `nodes/` (other than those two dispatch dicts) needs to change — the graph and the deterministic nodes are skill-agnostic by design.

Any change beyond that — a fifth LLM call, a new dependency, a new node or orchestration layer — needs sign-off first, per `CLAUDE.md`'s hard constraints.
