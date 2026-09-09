# Adaptive math tutor — project context

Read this fully before writing any code. This file is the source of truth for architecture and scope. If a task seems to require deviating from it (new dependency, new agent, new LLM call), stop and ask first rather than proceeding.

## Project summary

A K-5 adaptive math learning app for the Nerdy AI Hackathon (Prompt 01: K-5 Math Game). A deterministic state machine tracks per-skill mastery via Bayesian Knowledge Tracing, generates problems calibrated to the student's level, diagnoses the specific misconception behind wrong answers using rule-based bug detection, and drives a skill-tree progression system off that real mastery data. A small, fixed set of LLM calls handles natural language generation only. Everything else is plain, fast, deterministic Python.

## Hard constraints — do not violate these

1. **No LLM calls in the grading, mastery-update, or curriculum-selection path, ever.** These must be deterministic functions. Correctness of math grading cannot depend on model output.
2. **LLM calls are restricted to exactly these four use cases** (see "LLM touchpoints" below). Do not add an LLM call anywhere else in the codebase without asking first.
3. **Do not introduce additional agents, orchestration layers, or frameworks beyond what's listed in "Tech stack."** If you think a fifth node or a new library would help, propose it and wait for confirmation before implementing.
4. **Frontend stays minimal.** Time budget goes into the adaptive engine (curriculum, mastery model, misconception detection), not UI polish. A working, plain interface beats a polished one that ships late.
5. **Keep node functions pure where possible.** Given the same state and inputs, a node should produce the same output. This makes the system testable without mocking an LLM.

## Changelog

After completing any task from "Task breakdown" below, append a short entry to CHANGELOG.md (create it if it doesn't exist) with the date, what changed, and why. Keep entries to 2-3 lines. Do not narrate exploration or dead ends, only what actually landed.

## Tech stack

- **Backend**: Python 3.11+, LangGraph for state orchestration, FastAPI for serving
- **Frontend**: plain React (Vite) or vanilla HTML/CSS/JS, whichever is faster to stand up
- **Storage**: SQLite (or plain JSON files) for session/student state, no external DB
- **LLM**: single provider, called only from the four functions listed under "LLM touchpoints"
- **Testing**: pytest for the deterministic core (curriculum, generation, grading, BKT update, bug-rule detection)
- **Dependency management**: uv (`pyproject.toml` / `uv.lock`) — use `uv add <pkg>` / `uv add --dev <pkg>` to add dependencies, `uv run <cmd>` to run things

## Project structure

```
adaptive-math-tutor/
  backend/
    graph.py              # LangGraph wiring, state schema, conditional edges
    nodes/
      curriculum.py        # select_next_skill()
      problem_gen.py        # generate_problem()
      diagnosis.py          # grade_and_diagnose(), bug rule table
      engagement.py         # decide_engagement()
    models/
      state.py              # SessionState, Problem, DiagnosisResult, etc. (pydantic)
      bkt.py                 # BKTParams, update_mastery()
    skills/
      skill_graph.py         # prerequisite DAG
      addition_carry.py      # templates + bug rules for this skill
      subtraction_borrow.py  # templates + bug rules for this skill
    llm/
      narrative.py            # the four LLM touchpoints, isolated here only
    tests/
      test_bkt.py
      test_bug_rules.py
      test_curriculum.py
  frontend/
    (problem display, answer input, skill map, XP/streak display)
  CLAUDE.md                  # this file
```

## Data models

```python
class Problem(BaseModel):
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float

class LastResponse(BaseModel):
    answer: int
    correct: bool
    time_taken_sec: float

class Misconception(BaseModel):
    skill: str
    bug_type: str
    timestamp: datetime

class EngagementState(BaseModel):
    streak: int
    xp: int
    frustration_signal: bool

class SessionState(BaseModel):
    student_id: str
    session_id: str
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    current_problem: Problem | None
    last_response: LastResponse | None
    engagement: EngagementState
    next_action: Literal["new_problem", "repeat_skill", "advance_skill", "hint"]

class BKTParams(BaseModel):
    p_init: float = 0.3
    p_transit: float = 0.15
    p_slip: float = 0.1
    p_guess: float = 0.05  # numeric entry, not multiple choice, so guess rate is low
```

## Algorithms — implement exactly as specified

### Bayesian Knowledge Tracing update

Given current mastery `P(L)` for a skill and an observed response:

```
if correct:
    P(L | evidence) = P(L) * (1 - p_slip) / (P(L) * (1 - p_slip) + (1 - P(L)) * p_guess)
else:
    P(L | evidence) = P(L) * p_slip / (P(L) * p_slip + (1 - P(L)) * (1 - p_guess))

P(L_next) = P(L | evidence) + (1 - P(L | evidence)) * p_transit
```

Default parameters live in `BKTParams` above. New skills start at `p_init = 0.3`. Mastery threshold for "skill mastered" is **0.8** — this is the value the curriculum node checks before routing to `advance_skill`.

### Misconception bug rules

Each skill module exports a list of `(bug_type: str, detector: Callable[[Problem, int], bool])` pairs. `grade_and_diagnose` checks the student's answer against each detector in order and logs the first match.

**Subtraction with borrowing** (`subtraction_borrow.py`):
- `no_borrow_smaller_from_larger`: answer equals the result of subtracting digit-wise with `abs()` on each column instead of borrowing
- `off_by_ten_in_borrow`: answer is exactly 10 off from the correct result in the borrowed place
- `reversed_operands`: answer equals `b - a` instead of `a - b`

**Addition with carrying** (`addition_carry.py`):
- `no_carry`: answer equals the digit-wise sum of each place value with overflow truncated (mod 10) instead of carried to the next place

Write these as pure functions: `def detect_no_borrow(problem: Problem, answer: int) -> bool`.

## Node specifications

```python
def select_next_skill(mastery: dict[str, float], skill_graph: SkillGraph) -> str: ...
def generate_problem(skill: str, difficulty: float) -> Problem: ...
def grade_and_diagnose(problem: Problem, answer: int) -> DiagnosisResult: ...
def update_mastery(mastery: dict[str, float], skill: str, correct: bool, params: BKTParams) -> dict[str, float]: ...
def decide_engagement(state: SessionState) -> EngagementState: ...
```

Routing logic (in `graph.py`): after `decide_engagement`, if mastery for the current skill >= 0.8, route to `select_next_skill` (`advance_skill`). Otherwise route back to `generate_problem` for the same skill (`repeat_skill`).

## LLM touchpoints — the only four places an LLM call is allowed

1. **Word-problem flavor text**: wraps a generated numeric problem in a one-line story. Called from `problem_gen.py`, optional, falls back to the plain numeric problem if the call fails or is skipped.
2. **Mastery-moment narrative**: fires once, on the `advance_skill` transition. Input: the skill's `misconception_log` entries and attempt count. Output: one or two sentences naming the specific pattern the student overcame.
3. **Effort-aware reward framing**: one line differentiating a student who struggled through a skill (many attempts, long time-taken) from one who moved through it quickly, using real `time_taken_sec` and attempt-count data.
4. **Boss-battle narrative wrapper**: short framing text for the mastery-check problem set, naming the specific skill being confirmed.

Before adding any LLM call outside this list, apply this test: does the generated sentence depend on this student's specific session data? If it could be written without knowing anything about this particular student, it's decoration — don't add it.

## Task breakdown

- [ ] **Skill graph + templates**: prerequisite DAG for 3-4 skills, problem templates for addition-carry and subtraction-borrow. *Acceptance: `generate_problem` produces a valid, auto-gradable problem for each skill at 3 difficulty levels.*
- [ ] **BKT + bug rules**: implement `update_mastery` and the bug-rule detectors above. *Acceptance: unit tests cover correct/incorrect update math and each bug rule fires on a known wrong answer.*
- [ ] **LangGraph wiring**: connect the four nodes with the routing logic above. *Acceptance: a scripted session (no UI) runs end to end from session start through at least one skill mastery transition.*
- [ ] **Minimal frontend**: problem display, answer input, skill-map view driven by `skill_mastery`. *Acceptance: a student can play through a session in the browser and see the skill map update live.*
- [ ] **LLM touchpoints**: wire the four narrative calls, isolated in `llm/narrative.py`. *Acceptance: each call is invoked only at its specified trigger point, verify by grepping for LLM client usage outside this file.*
- [ ] **Demo polish**: record the 2-3 minute walkthrough per the demo script in the companion notes doc.

## Non-goals — explicitly out of scope

- User authentication or accounts beyond a single local student ID
- Persistence beyond the current session/local storage
- Multi-student or classroom features
- Mobile-responsive design polish
- Any subject beyond math for the actual demo (the architecture should be subject-agnostic in principle, but do not build a second subject module for this submission)

