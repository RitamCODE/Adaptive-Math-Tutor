# Adaptive math tutor: project context

Read this fully before writing any code. This file is the source of truth for architecture and scope. If a task seems to require deviating from it (new dependency, new agent, new LLM call), stop and ask first rather than proceeding.

## Project summary

A K-5 adaptive math learning app for the Nerdy AI Hackathon (Prompt 01: K-5 Math Game). A deterministic state machine tracks per-skill mastery via Bayesian Knowledge Tracing, generates problems calibrated to the student's level, diagnoses the specific misconception behind wrong answers using rule-based bug detection, and drives a skill-tree progression system off that real mastery data. A small, fixed set of LLM calls handles natural language generation only. Everything else is plain, fast, deterministic Python.

The engine is built. The remaining work is a revision pass specified in `docs/revision-plan.md`, whose purpose is to make the existing intelligence visible to the student. Read the relevant Part of that file before starting a task. Do not read the whole file unless asked.

## Hard constraints, do not violate these

1. **No LLM calls in the grading, mastery-update, or curriculum-selection path, ever.** These must be deterministic functions. Correctness of math grading cannot depend on model output.
2. **LLM calls are restricted to exactly these four use cases** (see "LLM touchpoints" below). Do not add an LLM call anywhere else in the codebase without asking first.
3. **Do not introduce additional agents, orchestration layers, or frameworks beyond what's listed in "Tech stack."** Two exceptions are pre-authorized and no others: the `remediation` node described under "Node specifications", and the `langsmith` dependency for tracing. Anything else, propose and wait.
4. **Frontend polish is in scope, within the existing stack.** CSS, layout, and libraries already in the stack. No new frontend dependency, no framework change, no build-step changes. Visual assets are allowed only as **inline SVG React components authored in code**, which covers the mascot, the manipulatives, and icons. No binary image pipeline. Audio is out of scope.
5. **Keep node functions pure where possible.** Given the same state and inputs, a node should produce the same output. This makes the system testable without mocking an LLM.
6. **Latency budget.** Submit to verdict is under 150 ms. No LLM call may sit between a student pressing submit and the verdict rendering. Word-problem flavor text for the *next* problem is prefetched during the current one.
7. **The correct answer is never sent to the client before attempt 3.** Not in the payload, not hidden in the DOM.

## Changelog

After completing any task from "Task breakdown" below, append a short entry to CHANGELOG.md (create it if it doesn't exist) with the date, what changed, and why. Keep entries to 2-3 lines. Do not narrate exploration or dead ends, only what actually landed.

## Tech stack

- **Backend**: Python 3.11+, LangGraph for state orchestration, FastAPI for serving
- **Frontend**: React (Vite)
- **Storage**: SQLite for session/student state and the event log, no external DB
- **LLM**: OpenAI API, called only from the four functions listed under "LLM touchpoints"
- **Tracing**: LangSmith via environment variables, auto-tracing LangGraph. Traces LLM calls only; product analytics go to the event log, not here.
- **Testing**: pytest for the deterministic core (curriculum, generation, grading, BKT update, bug-rule detection)
- **Dependency management**: uv (`pyproject.toml` / `uv.lock`), use `uv add <pkg>` / `uv add --dev <pkg>` to add dependencies, `uv run <cmd>` to run things

## Project structure

```
adaptive-math-tutor/
  backend/
    graph.py              # LangGraph wiring, state schema, conditional edges
    nodes/
      curriculum.py        # select_next_skill()
      problem_gen.py       # generate_problem()
      diagnosis.py         # grade_and_diagnose(), detector dispatch
      remediation.py       # build_remediation()  [new]
      engagement.py        # decide_engagement()
    models/
      state.py             # SessionState, Problem, DiagnosisResult, etc. (pydantic)
      bkt.py               # BKTParams, update_mastery()
    skills/
      skill_graph.py       # prerequisite DAG
      addition_carry.py    # templates + detectors for this skill
      subtraction_borrow.py
    content/
      misconceptions.json  # hint copy + visual payload, keyed by bug_type  [new]
    logging/
      events.py            # one row per submission  [new]
    llm/
      narrative.py         # the four LLM touchpoints, isolated here only
    tests/
      test_bkt.py
      test_bug_rules.py
      test_curriculum.py
      test_retry_ladder.py [new]
  frontend/
    (problem display, number pad, manipulative canvas, skill map, XP/streak)
  docs/
    revision-plan.md
    CHECKLIST.md
  CLAUDE.md
```

**Detectors are code, copy is data.** Detector functions stay in the per-skill Python modules where they already live. The student-facing hint string and the visual payload for each `bug_type` move into `misconceptions.json`. Adding a hint or retuning wording must not require touching engine code.

## Data models

```python
class Problem(BaseModel):
    problem_id: str
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float

class LastResponse(BaseModel):
    answer: int | None          # None for a blank submission
    correct: bool
    time_taken_sec: float

class Misconception(BaseModel):
    skill: str
    bug_type: str
    timestamp: datetime

class DiagnosisResult(BaseModel):
    problem_id: str
    correct: bool
    bug_type: str | None        # None when correct; "unclassified" when no detector fires
    hint: str | None
    visual: str | None          # e.g. "base10_blocks/ones_overflow"
    attempts_remaining: int
    reveal_answer: bool         # True only on the third failed attempt
    signal: bool                # False for blank and rapid-guess submissions

class EngagementState(BaseModel):
    streak: int
    xp: int
    frustration_signal: bool
    consecutive_wrong: int      # signal-bearing wrong answers in a row; drives the
                                 # end_session fatigue stop at 4, frustration_signal at 3

class SessionState(BaseModel):
    student_id: str
    session_id: str
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    current_problem: Problem | None
    attempt_number: int                      # 1-indexed, resets only on a new problem
    attempt_history: list[tuple[int | None, str | None]]   # (answer, bug_type) this problem
    last_response: LastResponse | None
    engagement: EngagementState
    problems_completed: int
    quest_length: int                        # default 10
    next_action: Literal[
        "new_problem", "retry_problem", "remediate",
        "advance_skill", "demote_skill", "end_session",
    ]
```

**Note on `LastResponse.correct`**: this field is required by the schema, but when a caller submits a new answer to the graph, its value is provisional. The caller does not compute correctness. `grade_and_diagnose` is the sole source of truth: the graph's grading node overwrites `last_response.correct` with the diagnosis result before `update_mastery` reads it. Callers should submit any placeholder value (e.g. `False`) and never rely on their own `correct` value downstream.

**Non-signal submissions.** A blank answer, or any answer submitted under 2 seconds with no manipulative interaction, sets `signal = False`. These do not consume an attempt and do not update BKT. They are still written to the event log.

```python
class BKTParams(BaseModel):
    p_init: float = 0.3
    p_transit: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.05  # numeric entry, not multiple choice, so guess rate is low
```

## Algorithms, implement exactly as specified

### Bayesian Knowledge Tracing update

Given current mastery `P(L)` for a skill and an observed response:

```
if correct:
    P(L | evidence) = P(L) * (1 - p_slip) / (P(L) * (1 - p_slip) + (1 - P(L)) * p_guess)
else:
    P(L | evidence) = P(L) * p_slip / (P(L) * p_slip + (1 - P(L)) * (1 - p_guess))

P(L_next) = P(L | evidence) + (1 - P(L | evidence)) * p_transit
```

Default parameters live in `BKTParams` above. New skills start at `p_init = 0.3`. Mastery threshold for "skill mastered" is **0.8**, the value the curriculum node checks before routing to `advance_skill`.

**Distinct from the mastery threshold**, the manipulative fading bands are 0.4 and 0.7. Do not unify these numbers. 0.8 governs progression; 0.4 and 0.7 govern how much visual scaffolding is shown.

### Misconception bug rules

Each skill module exports a list of `(bug_type: str, detector: Callable[[Problem, int], bool])` pairs. `grade_and_diagnose` checks the student's answer against each detector in order and logs the first match. Write these as pure functions: `def detect_no_borrow(problem: Problem, answer: int) -> bool`.

**Addition with carrying** (`addition_carry.py`):
- `add_concat_no_carry`: each column summed correctly, then concatenated. `86 + 94 -> 1017`
- `add_carry_dropped`: column overflow truncated mod 10 instead of carried. `86 + 94 -> 170`
- `add_carry_wrong_column`: carry applied to the ones instead of the tens
- `add_off_by_one`: counting-on error
- `add_used_subtraction`: operator misread

**Subtraction with borrowing** (`subtraction_borrow.py`):
- `sub_smaller_from_larger`: digit-wise `abs()` on each column instead of borrowing. `42 - 17 -> 35`
- `sub_borrow_no_decrement`: borrowed without reducing the tens
- `sub_zero_minus_n`: treated `0 - n` as `n`
- `sub_borrow_across_zero`: failed on the zero column
- `sub_reversed_operands`: computed `b - a` instead of `a - b`

**Cross-cutting** (checked after skill-specific detectors):
- `digit_reversal`: answer is the digit-reversal of the correct one. Hint names order, **mastery is not penalized**, the underlying skill is intact.
- `place_value_confusion`: answer off by an exact power of ten
- `unclassified`: no detector matched

**The unclassified path must never reveal the answer.** It returns a procedural nudge ("Let's redo this one column at a time. Start with the ones.") and opens the manipulative, and writes the submission to the event log so the catalog can grow from real data.

## Node specifications

```python
def select_next_skill(mastery: dict[str, float], skill_graph: SkillGraph) -> str: ...
def generate_problem(skill: str, difficulty: float) -> Problem: ...
def grade_and_diagnose(problem: Problem, answer: int | None, attempt: int) -> DiagnosisResult: ...
def build_remediation(diagnosis: DiagnosisResult, attempt: int) -> Remediation: ...
def update_mastery(mastery: dict[str, float], skill: str, correct: bool, params: BKTParams) -> dict[str, float]: ...
def decide_engagement(state: SessionState) -> EngagementState: ...
```

### Routing logic (in `graph.py`)

A wrong answer keeps the **same problem** on screen. It does not generate a new one.

```
correct                      -> decide_engagement
  mastery >= 0.8             -> select_next_skill      (advance_skill)
  otherwise                  -> generate_problem       (new_problem, same skill)

incorrect, attempt 1         -> build_remediation      (retry_problem, hint only)
incorrect, attempt 2         -> build_remediation      (retry_problem, manipulative pre-loaded
                                                        with the student's wrong answer)
incorrect, attempt 3         -> worked solution, then select_next_skill on the
                                prerequisite            (demote_skill)

non-signal submission        -> retry_problem, attempt counter unchanged, no BKT update

problems_completed >= quest_length, or 2 skills mastered,
or 4 consecutive wrong       -> end_session
```

`end_session` is a terminal state. It renders a summary and stops. There is no auto-restart.

A skill demoted at attempt 3 is re-surfaced once, after two correct answers on its prerequisite. If it fails again, end the quest on the lower-level success rather than grinding.

## Frontend requirements

- **No `<input type="number">` anywhere.** On-screen number pad only: digits, backspace, submit. A student must not be able to reach an answer without computing it, because a spun-to answer produces a correct grade with no misconception signal and inflates the mastery estimate.
- Feedback carries `problem_id` and renders **inside the problem card it belongs to**, cleared when `problem_id` changes. No global banner.
- All drag interactions use pointer events (`pointerdown` / `pointermove` / `pointerup`), never mouse events. Drag surfaces set `touch-action: none`.
- Minimum 48px touch targets, 64px for number pad keys.
- Primary target is **tablet landscape**, roughly 1024 x 768, scaling up to laptop. Phone portrait is out of scope: a manipulative canvas plus a number pad cannot be usable at that width.
- Error state is never signaled by color alone.
- Session state snapshots to `localStorage` every turn and rehydrates on load.
- A `?seed=` URL parameter loads one of three fixed profiles (`new`, `struggling`, `fluent`) for demo and testing.

### Copy limits, enforced by truncation in code

| Moment | Cap |
|---|---|
| Correct | 4 words |
| Streak | 6 words |
| Wrong-answer hint | 12 words |
| Mastery moment | 20 words |
| Generated word problem | 20 words, one name, one countable object, digits as numerals |

Per-problem praise selection is a **deterministic four-branch lookup**, not an LLM call: speed when mastery > 0.7 and the answer was fast, the named skill on a first-try correct, effort after multiple attempts, strategy when the manipulative was used.

## LLM touchpoints, the only four places an LLM call is allowed

1. **Word-problem flavor text**: wraps a generated numeric problem in a one-line story. Called from `problem_gen.py`, prefetched for the next problem during the current one, falls back to the plain numeric problem if the call fails or is skipped.
2. **Mastery-moment narrative**: fires once, on the `advance_skill` transition. Input: the skill's `misconception_log` entries and attempt count. Output: one or two sentences naming the specific pattern the student overcame.
3. **Effort-aware reward framing**: fires at the mastery moment only, not per problem. Differentiates a student who struggled through a skill from one who moved quickly, using real `time_taken_sec` and attempt-count data.
4. **Boss-battle narrative wrapper**: short framing text for the mastery-check problem set, naming the specific skill being confirmed.

Before adding any LLM call outside this list, apply this test: does the generated sentence depend on this student's specific session data? If it could be written without knowing anything about this particular student, it's decoration, don't add it.

## Task breakdown

The engine below is complete. Do not rebuild it.

- [x] Skill graph + templates
- [x] BKT + initial bug rules
- [x] LangGraph wiring
- [x] Minimal frontend
- [x] LLM touchpoints

Remaining work, per `docs/revision-plan.md`:

- [ ] **Retry ladder and session termination** (Plan Part 1). *Acceptance: a wrong answer keeps the same problem on screen, never reveals the answer on attempt 1 or 2, and a full quest reaches a terminal summary screen.*
- [ ] **Misconception catalog** (Plan Parts 2 and 3). *Acceptance: every bug_type above fires on a known wrong answer in a unit test, and `86 + 94 -> 1017` returns `add_concat_no_carry`.*
- [ ] **Manipulatives** (Plan Part 4). *Acceptance: `86 + 94` is solvable end to end by dragging, on touch, and the fading bands change behavior between the `new` and `fluent` seeds.*
- [ ] **UI shell** (Plan Part 6). *Acceptance: number pad, quest map, mascot, end-of-quest report, full session playable at 1024 x 768.*
- [ ] **Demo readiness** (Plan Part 7). *Acceptance: all three seeds load from a URL, refresh mid-session recovers, LangSmith shows traces for all four touchpoints.*
- [ ] **Demo polish**: record the 2-3 minute walkthrough per the demo script in `docs/revision-plan.md`.

Verification for all of the above lives in `docs/CHECKLIST.md`. Flag items as ready to test; do not tick them yourself, most are visual.

## Non-goals, explicitly out of scope

- User authentication or accounts beyond a single local student ID
- Persistence beyond the current session and localStorage
- Multi-student or classroom features
- Any subject beyond math for the actual demo (the architecture should be subject-agnostic in principle, but do not build a second subject module for this submission)
- Audio, TTS, voice input
- Phone portrait layout, orientation handling
- More than three manipulatives
- Refactoring the BKT model
