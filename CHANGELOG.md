# Changelog

## 2026-09-10 — Minimal frontend

Added a thin FastAPI layer (`backend/api.py`) wrapping the compiled graph with an in-memory per-session store, exposing start/resume/submit-answer endpoints that hide the answer until graded and derive per-skill lock/mastery state from `DEFAULT_SKILL_GRAPH` for the skill map. Added a minimal Vite + React frontend (problem card, feedback banner, skill map, XP/streak) that drives a full session through the API; verified live in the browser through an `addition_no_carry -> addition_carry` mastery transition and a `no_carry` misconception hint. 3 new API smoke tests cover start/submit/404 wiring.

## 2026-09-10 — LangGraph wiring

Wired the five nodes (`select_next_skill`, `generate_problem`, `grade_and_diagnose`, `update_mastery`, `decide_engagement`) into a compiled `StateGraph` with a conditional entry point (fresh vs. in-progress turn) and a post-engagement router (advance vs. repeat) gated on the 0.8 mastery threshold. Added `SessionState`/`LastResponse`/`Misconception`/`EngagementState` and a simple deterministic engagement policy (streak/xp/frustration). A scripted, no-UI session test drives `graph.invoke()` in a loop and confirms a full `addition_no_carry -> addition_carry` mastery transition.

## 2026-09-09 — BKT + bug rules

Implemented `update_mastery` (exact BKT posterior + transition formulas from CLAUDE.md) and rule-based misconception detectors for `no_carry` (addition) and `reversed_operands`/`no_borrow_smaller_from_larger`/`off_by_ten_in_borrow` (subtraction), wired through the new `grade_and_diagnose` node. Both remain pure/deterministic per the project's hard constraints; 20 new tests cover the mastery math and each bug rule firing on a known wrong answer.

## 2026-09-09 — Skill graph + problem templates

Added the 4-skill prerequisite DAG (`addition_no_carry -> addition_carry -> subtraction_no_borrow -> subtraction_borrow`) and deterministic template generators for each, dispatched through `generate_problem`. First task in the breakdown; unblocks the BKT/bug-rule and curriculum-selection tasks.
