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

## Plan mode output

Write plan mode output in whatever shape fits the task, sections, numbered steps, prose, as normal. This rule governs the writing inside it, not its structure.

Rule: the first time any specific thing appears, a function name, a file, an exact number, an edge case, a library term, the sentence introducing it says what it does in plain words, in that same sentence or the one right before it. After that, use it freely without re-explaining.

Test before writing anything: if someone could point at a specific noun and ask "what's that," and the plan doesn't answer in the same breath, rewrite it before moving on.

This applies to every part of the plan, including verification and edge cases. Nothing gets cut to simplify, if a detail is worth including, it's worth one clause explaining what it is before you use it.

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
      _difficulty_ladder.py # digit-width progression, independent of BKT mastery  [new]
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
      test_mastery_gate.py [new]
      test_difficulty_ladder.py [new]
  frontend/
    (problem display, number pad, manipulative canvas, skill map, XP/streak)
    src/components/ColumnArithmetic.jsx  # stacked equation + blocks in one grid
    src/lib/columnBoard.js   # pure board state: digits, places, borrow/carry
    src/lib/remediation.js   # bandFromMastery(): which remediation a wrong answer earns
    src/lib/copy.js          # sentence-safe cap for the LLM narrative copy limits
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

class Remediation(BaseModel):
    hint: str | None
    visual: str | None
    reveal_answer: bool

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
    last_diagnosis: DiagnosisResult | None    # set by grade_and_diagnose_node; None until this
                                               # turn's answer is graded
    remediation: Remediation | None           # set by build_remediation_node; None on a correct
                                               # answer, since there's nothing to remediate
    engagement: EngagementState
    problems_completed: int
    mastery_run: dict[str, int]              # per skill: consecutive signal-bearing answers
                                             # that left its mastery at or above 0.8
    digit_level: dict[str, int]               # per skill: current digit-width tier index into
                                               # that skill's own width ladder (see "Digit-width
                                               # progression is independent of mastery" below).
                                               # Never read from or written by the BKT update.
    digit_level_run: dict[str, int]           # per skill: consecutive signal-bearing correct
                                               # answers at the current digit_level, toward the
                                               # next tier
    seen_combos: dict[str, list[list[int]]]   # per skill: 1-digit (a, b) operand pairs already
                                               # shown this session, while that skill is still at
                                               # its narrowest tier — avoids repeats without
                                               # requiring the full combo space be exhausted
    quest_length: int                        # default 16
    pending_resurface: str | None            # skill demoted FROM, awaiting resurface (revision-plan 7.3)
    resurface_progress: int                  # correct answers on the prerequisite since that demotion
    resurfaced_skills: list[str]              # skills that already used their one resurface chance
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

Default parameters live in `BKTParams` above. New skills start at `p_init = 0.3`. Mastery threshold for "skill mastered" is **0.8**.

### Mastery must be sustained, not merely crossed

With the parameters above a single correct answer lifts a fresh skill from 0.30 to **0.9025**, past the threshold. So crossing 0.8 once is not mastery. A skill counts as mastered only when it has been at or above 0.8 after each of the last **3** consecutive signal-bearing answers on it (`MASTERY_MIN_RUN` in `bkt.py`). Any answer that drops it below 0.8 resets that run to zero. The run lives in `SessionState.mastery_run`, maintained by `update_mastery_node`.

Two answers deliberately leave the run untouched rather than resetting it: a **non-signal** submission (blank or rapid guess), which never reaches the mastery node at all, and a **`digit_reversal`** answer, which already skips the BKT update because the underlying skill is intact — so it is neither penalized nor rewarded.

This is expressed as exactly one helper, and every "is this mastered" question in the codebase goes through it — routing, `select_next_skill`, `SkillGraph.is_unlocked`, and the `mastered` flag the API sends the UI — so the engine and the interface can never disagree:

```python
def is_mastered(skill: str, state: SessionState) -> bool: ...
```

Note the gate is sticky in one direction: from a saturated skill it takes four consecutive wrong answers to fall back under 0.8, and the fatigue stop ends the session at exactly four. A genuinely mastered skill is not un-mastered mid-session.

**Distinct from the mastery threshold**, the remediation bands are 0.4 and 0.7. Do not unify these numbers. 0.8 governs progression; 0.4 and 0.7 govern **what kind of remediation a wrong answer earns**, not what is visible by default — no manipulative is shown before an error at any mastery level. See "Manipulatives are remediation" below.

### Digit-width progression is independent of mastery

Raw BKT mastery is not used to choose operand digit-width. It can't be: with this project's parameters a single correct answer lifts a fresh skill from `p_init = 0.3` to ~0.90, so any bucket table keyed on `P(L)` skips whatever tier sits between "just started" and "clearly fluent" — that was the original bug this section closes. Digit-width is instead its own small integer ladder per skill, implemented in `backend/skills/_difficulty_ladder.py`, and BKT mastery never feeds it and it never feeds BKT mastery.

`addition_no_carry` and `subtraction_no_borrow` start at a 1-digit tier; `addition_carry` and `subtraction_borrow` start at 2-digit, since a carry or borrow is impossible with single digits.

**General rule (any tier above the narrowest one)**: exactly 3 consecutive correct, signal-bearing answers at the current digit-width advance to the next tier (`LEVEL_UP_RUN`). A wrong answer resets that count to zero. This run is tracked in `SessionState.digit_level_run` and is a completely separate counter from `mastery_run` — a skill can sit at its widest tier while still well below 0.8 mastery, and vice versa.

**Narrowest tier (1-digit) rule**: 2 consecutive correct answers (`NARROW_TIER_BASE_RUN`) advance to 2-digit, but the pair must escalate — the first correct answer is on a "trivial" combo (an operand is 0 for addition; the subtrahend is 0 or the two operands are equal for subtraction), the second on a "non-trivial" one. `SessionState.seen_combos` tracks which 1-digit operand pairs have already been shown this session per skill, so the same combo isn't repeated while at this tier — this is a selection heuristic to avoid boredom, not a coverage gate; the 2-correct rule above is still the only thing that advances the tier.

**No degradation**: digit-width only ever increases within a skill. Sustained struggle is handled entirely by the existing attempt-3 demotion to the prerequisite skill, which is unrelated to digit-width.

### Skill groups

The four skills are two **parent skills** of two sub-skills each, declared in `skill_graph.py` alongside the prerequisite DAG:

| Parent | Sub-skills |
|---|---|
| Addition | `addition_no_carry`, `addition_carry` |
| Subtraction | `subtraction_no_borrow`, `subtraction_borrow` |

Each sub-skill keeps its own independent BKT mastery value and its own 0.8 threshold, unchanged. A parent skill is mastered only when **every** one of its sub-skills is. Grouping changes how mastery is aggregated and reported — the quest-end condition, the quest map's headings, the end-of-quest report — and never the traversal order: `select_next_skill` walks the same DAG in the same sequence it always did.

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
def select_next_skill(state: SessionState, skill_graph: SkillGraph) -> str: ...  # needs mastery_run, not just mastery
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
  is_mastered(skill, state)  -> select_next_skill      (advance_skill)
  otherwise                  -> generate_problem       (new_problem, same skill)

incorrect, attempt 1         -> build_remediation      (retry_problem, hint only)
incorrect, attempt 2         -> build_remediation      (retry_problem; what the hint comes
                                                        with depends on the mastery band, see
                                                        "Manipulatives are remediation")
incorrect, attempt 3         -> worked solution, then select_next_skill on the
                                prerequisite            (demote_skill)

non-signal submission        -> retry_problem, attempt counter unchanged, no BKT update

both parent skills mastered (all four sub-skills past the gate),
or problems_completed >= quest_length,
or 4 consecutive wrong       -> end_session
```

`end_session` is a terminal state. It renders a summary and stops. There is no auto-restart.

A skill demoted at attempt 3 is re-surfaced once, after two correct answers on its prerequisite. If it fails again, end the quest on the lower-level success rather than grinding.

## Frontend requirements

### Manipulatives are remediation, not default furniture

A manipulative — the base-ten blocks, the ten frame, the number line — is help a student gets **after** an error or asks for deliberately. It is never the surface they meet a problem on.

- **No manipulative is ever shown on attempt 1 of any problem, at any mastery level.** There is no low-mastery auto-open. (A fresh student sits at `p_init = 0.3`, so an "open below 0.4" rule meant blocks on problem 1, before any mistake.)
- On a wrong, **signal-bearing** answer, the mastery band decides what the remediation delivers. The fading is in how much scaffolding the error earns:

| Mastery | What attempt 2 delivers |
|---|---|
| below 0.4 | the hint, and the manipulative opens pre-loaded with the student's own wrong answer |
| 0.4 to 0.7 | the hint, with the manipulative highlighted and one tap away, still closed |
| above 0.7 | the hint alone; nothing opens |

- An explicit **opt-in control** ("Show blocks" / "Show frame") is available at all times, at every mastery level and on every attempt, and is **closed by default**. A student who wants the scaffold can always request it.
- The band function is `bandFromMastery` in `frontend/src/lib/remediation.js`, shared by the manipulatives rather than copied into each.
- The number line is the exception to "available at all times": it is the remediation for four specific misconceptions rather than a general scaffold, so it appears only inside its own remediation window, and then only as much as the band allows.

### The equation is always visible

The equation is pinned above the manipulative area and sticks to the top of the problem card, so the numerals never require scrolling to during a problem, however tall the manipulative grows beneath them. It keeps full prominence whether or not a manipulative is present.

### Column arithmetic

`addition_carry` and `subtraction_borrow` render the equation **stacked in column form** rather than as the horizontal question string, with the block columns directly beneath their own digit columns. The equation grid and the block grid share one `grid-template-columns`, which is what makes that alignment structural rather than eyeballed — do not give one of them a template the other lacks. The equation grid is sticky and rendered whether or not the blocks are open, so the numerals never need scrolling to.

Work runs **right to left, one active column at a time**; other columns are dimmed and take no pointers. Regrouping is one mechanic in two directions — ten ones bundling into a ten, one ten breaking into ten ones — so carrying and borrowing are visibly the same event. Borrowing across a zero is two student-caused steps (hundreds into tens, then tens into ones), never one that reaches past the empty column. The pure board logic lives in `frontend/src/lib/columnBoard.js`, separate from the component, so it can be reasoned about and checked on its own.

The other two skills keep the plain horizontal equation and their existing widgets.

### A manipulative never resolves the answer for the student

The base-ten blocks show the assembled place values and the bundling animation — ten ones snapping into a ten is the pedagogically valuable part and stays. They do **not** display a running numeric total: a readout that tallies to a finished number while the student drags turns the number pad into copying rather than computing. The student reads the place values and enters the number themselves.

**The per-column answer digit is the one exception**, on the same grounds as the number line's readout below: it is not a tally the app keeps, it is the result of work the student has already finished. In the column layout (see "Column arithmetic"), a column's answer digit appears under the rule only once that column is resolved — every take-away slot filled, or both addend piles emptied — and a column the student has not worked has no digit at all. Nothing anywhere updates mid-drag, and the student still types the whole number on the pad.

The number line is the deliberate exception. Its rail carries no tick labels, so its position readout is the only number on the widget, and landing on a position is what a number line *is*.

### Input, feedback, and layout

- **No `<input type="number">` anywhere.** On-screen number pad only: digits, backspace, submit. A student must not be able to reach an answer without computing it, because a spun-to answer produces a correct grade with no misconception signal and inflates the mastery estimate.
- Feedback carries `problem_id` and renders **inside the problem card it belongs to**, cleared when `problem_id` changes. No global banner.
- All drag interactions use pointer events (`pointerdown` / `pointermove` / `pointerup`), never mouse events. Drag surfaces set `touch-action: none`.
- Minimum 48px touch targets, 64px for number pad keys.
- Primary target is **tablet landscape**, roughly 1024 x 768, scaling up to laptop. Phone portrait is out of scope: a manipulative canvas plus a number pad cannot be usable at that width.
- Error state is never signaled by color alone.
- Session state snapshots to `localStorage` every turn and rehydrates on load.
- A `?seed=` URL parameter loads one of four fixed profiles (`new`, `struggling`, `fluent`, `borrowing`) for demo and testing. The first three are the demo path; `borrowing` exists because `subtraction_borrow` is otherwise ~12 correct answers from a fresh start, which made the borrow flow effectively untestable in a browser and let a pile of defects ship. It is a test affordance, not a demo profile.

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
- [ ] **Manipulatives** (Plan Part 4). *Acceptance: `86 + 94` is solvable end to end by dragging, on touch; no manipulative appears on any attempt 1; and the bands change what a wrong answer delivers between the `new` and `fluent` seeds.*
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

## Things to keep in mind

- after testing in each session always turn off the backend and the frontend
