# Changelog

## 2026-09-11 — Backend README + frontend README refresh

Added `backend/README.md` documenting the LangGraph turn cycle (entry/grading/advance-repeat routing), data models, BKT, the skill/bug-rule module contract, the four LLM touchpoints, the HTTP API's response shaping, and how it connects to the frontend. Also fixed `frontend/README.md`, which had gone stale after the UI redesign below — it still referenced the removed `SkillMap.jsx` and claimed no responsive work existed.

## 2026-09-11 — Frontend redesign per UI_DESIGN.md

Implemented the design from `UI_DESIGN.md`: a growth-stage SVG/CSS mascot (`Mascot.jsx`, 5 stages keyed to mastered-skill count, with idle/correct/incorrect reactions), `SkillMap.jsx` replaced by `SkillTrailMap.jsx` (a winding node trail with locked/current/mastered states and a conic-gradient mastery ring), a warm 3-accent CSS custom-property palette, sticky streak/XP pill chips, and non-punishing confetti/shake feedback animations — all CSS/inline-SVG, no new dependencies. Also made the layout responsive (mobile single column, tablet fluid scaling, ≥1024px two-region grid), which required revising CLAUDE.md's non-goals (mobile-responsive polish was previously out of scope; the user asked for it explicitly, so constraint 4 and the non-goals list were both updated). Verified end-to-end in-browser across mobile/tablet/laptop viewport sizes, including a live BKT mastery transition and both correct/incorrect answer paths.

## 2026-09-10 — Surface LLM narratives in the frontend

`backend/api.py` was already returning `flavor_text`, `reward_narrative`, `mastery_narrative`, and `boss_battle_narrative`, but `ProblemCard.jsx`/`FeedbackBanner.jsx` never rendered them — the UI showed the same hardcoded "Correct!"/"Skill mastered" strings regardless of what the LLM produced. Wired all four fields into the two components (with the original hardcoded strings kept only as the fail-open fallback when a field is `None`); verified live against a real `OPENAI_API_KEY` that each field now carries model-generated, per-response text. Also added a repo-root `.env` loader in `backend/llm/narrative.py` (dependency-free, since a new library needs sign-off per CLAUDE.md) so the key doesn't need to be exported manually per shell session.

## 2026-09-10 — LLM touchpoints

Added `backend/llm/narrative.py` — the sole file allowed to reference an LLM client — with fail-open functions for the four narrative touchpoints (word-problem flavor, mastery-moment, effort-aware reward, boss-battle framing), each returning `None` on a missing API key or any call failure. Since `SessionState`/`Problem` are frozen per CLAUDE.md's literal schema, all four calls are invoked from `backend/api.py` post-`graph.invoke()` rather than inside the graph nodes, keeping `graph.py`/`nodes/*.py` untouched and LLM-free; a new in-memory per-skill attempt/time tracker in `api.py` supplies the "struggled vs. quick" data the reward touchpoint needs. Added `uv add openai`, a grep-based isolation test, and an autouse fixture that strips `OPENAI_API_KEY` so the whole suite stays deterministic and network-free.

## 2026-09-10 — Minimal frontend

Added a thin FastAPI layer (`backend/api.py`) wrapping the compiled graph with an in-memory per-session store, exposing start/resume/submit-answer endpoints that hide the answer until graded and derive per-skill lock/mastery state from `DEFAULT_SKILL_GRAPH` for the skill map. Added a minimal Vite + React frontend (problem card, feedback banner, skill map, XP/streak) that drives a full session through the API; verified live in the browser through an `addition_no_carry -> addition_carry` mastery transition and a `no_carry` misconception hint. 3 new API smoke tests cover start/submit/404 wiring.

## 2026-09-10 — LangGraph wiring

Wired the five nodes (`select_next_skill`, `generate_problem`, `grade_and_diagnose`, `update_mastery`, `decide_engagement`) into a compiled `StateGraph` with a conditional entry point (fresh vs. in-progress turn) and a post-engagement router (advance vs. repeat) gated on the 0.8 mastery threshold. Added `SessionState`/`LastResponse`/`Misconception`/`EngagementState` and a simple deterministic engagement policy (streak/xp/frustration). A scripted, no-UI session test drives `graph.invoke()` in a loop and confirms a full `addition_no_carry -> addition_carry` mastery transition.

## 2026-09-09 — BKT + bug rules

Implemented `update_mastery` (exact BKT posterior + transition formulas from CLAUDE.md) and rule-based misconception detectors for `no_carry` (addition) and `reversed_operands`/`no_borrow_smaller_from_larger`/`off_by_ten_in_borrow` (subtraction), wired through the new `grade_and_diagnose` node. Both remain pure/deterministic per the project's hard constraints; 20 new tests cover the mastery math and each bug rule firing on a known wrong answer.

## 2026-09-09 — Skill graph + problem templates

Added the 4-skill prerequisite DAG (`addition_no_carry -> addition_carry -> subtraction_no_borrow -> subtraction_borrow`) and deterministic template generators for each, dispatched through `generate_problem`. First task in the breakdown; unblocks the BKT/bug-rule and curriculum-selection tasks.
