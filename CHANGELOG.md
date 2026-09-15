# Changelog

## 2026-09-15 — UI shell: end-of-quest report, sound, hero-manipulative layout, mascot states (revision-plan Part 6)

Replaced the hardcoded "Quest complete!" placeholder with a real `SessionSummary.jsx`
naming mastered skills, misconceptions repaired (labeled via a new `GET /misconceptions`
endpoint serving the existing `misconceptions.json` catalog, tied to mastery so a
misconception on a since-demoted skill shows separately under "Still practicing" rather
than being claimed as fixed), problems solved, elapsed time (a new `sessionStartRef` in
`App.jsx`, persisted to `localStorage` so it survives a refresh), and a "Play again"
button. Added three Web Audio API synthesized sound effects (`frontend/src/lib/sound.js`,
no binary assets/dependencies) for correct answers, bundling-sticks snapping into a ten,
and quest completion. Reordered `ProblemCard.jsx` so the manipulative canvas renders
before the equation, with new CSS (`:has()`-based) demoting the equation to a caption
only when a manipulative is actually present. Added a `"thinking"` mascot state wired to
the submit-to-verdict `loading` window, and softened the wrong-answer face to read as
encouraging rather than sad, per revision-plan Part 6 items 2, 4, 5, 6 (items 1 and 3,
the number pad and quest map, were already done). Verified live in-browser end to end
(seeded and fresh sessions, correct/incorrect/quest-complete paths); backend suite stays
green (111 tests).

## 2026-09-14 — Seeded sessions and localStorage restart recovery (revision-plan Part 7.1/7.2)

Added `POST /sessions/seed/{new|struggling|fluent}`, backing a `?seed=` URL param the demo
video needs: `struggling` installs `addition_carry` mastery at `0.3` with one prior
`add_concat_no_carry` misconception (manipulative open by default), `fluent` installs it at
`0.85` (abstract-only), both via a new `_install_seeded_state` helper that generates a real
`current_problem` for the profile's skill without running the graph — the same "read the
state back as-is" pattern `GET /sessions/{id}` already used. The frontend still shows the
name form for all three seeds (so a real name can be typed on camera) and only swaps which
endpoint `handleStart` calls. Reused that same helper for `POST /sessions/{id}/restore`,
which fixes the other open Part 7 item: `App.jsx` now snapshots the *full* safe session
(mastery, misconceptions, engagement, progress — everything `SessionResponse` already sent
minus `correct_answer`, which was widened to include the previously-omitted fields) to
localStorage on every turn instead of just a bare session id, and on a 404 (backend
restarted, lost its in-memory `_SESSIONS`) restores that snapshot under the same session id
rather than losing it. The in-flight problem and attempt count don't survive a restart —
intentionally: the pre-restart problem's answer was never sent to the client and reconstructing
it would mean either violating CLAUDE.md constraint #7 or adding a heavier server-side
persistence layer, so a fresh problem on the same skill is generated instead; mastery/XP/
misconceptions all do survive. Also fixed `api.js`'s `handle()` to attach the HTTP status to
thrown errors (previously indistinguishable from a network-level failure), and a genuinely
unreachable backend now shows a visible message instead of silently discarding the cached
session. 6 new backend tests; verified live end-to-end in-browser for all three seeds, a
plain mid-session refresh, a killed-and-restarted backend recovering via `/restore`, and a
still-down backend showing the new error message. Full suite (111) green.

## 2026-09-14 — Number line and ten-frame manipulatives (revision-plan Part 4)

Added the two remaining manipulatives from the Part 4 table: `NumberLine.jsx` (for
the four `number_line/*` misconceptions — `add_off_by_one`, `add_used_subtraction`,
`reversed_operands`, `digit_reversal`), which force-opens on attempt 2 exactly like
`BundlingSticks` does for `base10_blocks/*`, groups hop tokens by place value via the
existing `toBlocks` helper (so a 3-digit operand is still at most 9 hops per place,
not hundreds of individual unit hops), and lets the student drag hops onto a track to
build their own answer; and `TenFrame.jsx`, a low-mastery scaffold for
`addition_no_carry` (which has no bug rules and thus no diagnosis to hook a force-open
into) shown whenever mastery is below 0.4, reusing the same `bandFromMastery` bands as
bundling sticks. Both follow the established pointer-events drag pattern (ghost
element, single-zone hit-testing) and the shared `App.css` design tokens — no new
dependencies, no per-component stylesheets. Wired into `ProblemCard.jsx`; number line
needs no skill-tag gate since its bug types span multiple skills. Verified live
end-to-end in-browser: a `74 + 57` problem answered wrong on attempt 2 opened the
number line with the correct hop counts and direction, dragging advanced the readout
correctly, and it was gone by attempt 3; a fresh `addition_no_carry` session showed
the ten-frame pre-filled and fillable by drag. Full backend suite (106, untouched by
this frontend-only change) still green.

## 2026-09-14 — Wire remediation into the graph (revision-plan Part 5)

Made `build_remediation` a real LangGraph node (`build_remediation_node` in `graph.py`),
reached via a new conditional edge for any wrong, signal-bearing answer (attempts 1
through 3 alike — attempt 3's worked-solution reveal is the same node's output with
`reveal_answer=True`, already baked in by `grade_and_diagnose`, not a separate path).
Added `last_diagnosis`/`remediation` fields to `SessionState` to carry the result
across the node boundary, and updated CLAUDE.md's schema to match (a `Remediation`
class definition was also missing from CLAUDE.md's data models and got added).
Removed `api.py`'s duplicate direct calls to `grade_and_diagnose`/`build_remediation`,
which had been re-running grading a second time outside the graph purely to get
hint/visual/`reveal_answer` for the HTTP response — the graph is now the sole place
grading and remediation run. The prerequisite-demotion routing (`demote_skill_node`)
was already in place from the 2026-09-12 retry-ladder work and needed no change.
Added the real branching diagram to `backend/README.md`'s "How a turn flows" section.
2 new tests in `test_graph.py`; verified live end-to-end via curl (hint-only at
attempt 1, visual at attempt 2, `reveal_answer` at attempt 3, correct demotion
fallback for a root skill); full suite (106) green.

## 2026-09-14 — Bundling sticks manipulative (revision-plan Part 4)

Added `BundlingSticks.jsx`, a pointer-events-only drag manipulative (no library, per CLAUDE.md
constraint #4) rendered for `addition_carry`/`subtraction_borrow` problems: loose "ones" sticks
auto-bundle into a ten at 10 (glow → snap → slide), and a tens/hundreds bundle can be dragged
down a place to unbundle for borrowing — one generic physics rule handles both operations and
cascading borrow-across-zero. Wired to the retry ladder (attempt-2 wrong answers force it open,
pre-seeded from the operands, per revision-plan 4.2) and to live BKT mastery (`<0.4` open,
`0.4–0.7` collapsed, `>0.7` hidden-on-request), reusing `skill_progress` already flowing to the
frontend — no backend changes needed. New `frontend/src/lib/arithmetic.js` parses `question`
strings and splits numbers into place-value blocks client-side. Also fixed a real crash found
during manual testing (a transient render reads `pileA`/`pileB`/`removeTarget` before the reset
effect re-seeds them on an operation-changing prop transition) and a `.gitignore` bug where an
unanchored `lib/` pattern from the Python template was silently swallowing the new
`frontend/src/lib/` directory. Verified live end-to-end in-browser: `85 + 94`-style carrying and
both plain and across-zero borrowing solved entirely by dragging, submitted via the number pad
and graded correct; fading bands and the diagnostic-preload override confirmed via a temporary
local harness (not shipped) since the backend resets mastery per session, making
`subtraction_borrow` unreachable in one live sitting. Also corrected CLAUDE.md's `docs/PLAN.md`
references (four places) to the file's actual name, `docs/revision-plan.md`.

## 2026-09-13 — Misconception catalog and event log (revision-plan Parts 2 and 3)

Added `backend/content/misconceptions.json` (hint + visual per bug_type, replacing the
inline stopgap dict in `diagnosis.py`) and six new bug-rule detectors reaching CLAUDE.md's
full catalog: `add_concat_no_carry` (the `86 + 94 -> 1017` acceptance case),
`add_carry_wrong_column`, `add_off_by_one`, `add_used_subtraction` in `addition_carry.py`;
`sub_zero_minus_n` and `sub_borrow_across_zero` in `subtraction_borrow.py`; plus a new
skill-agnostic `backend/skills/cross_cutting.py` for `digit_reversal` and
`place_value_confusion`, dispatched after each skill's own rules in `grade_and_diagnose`.
The four pre-existing detectors (`no_carry`, `reversed_operands`,
`no_borrow_smaller_from_larger`, `off_by_ten_in_borrow`) keep their original names by
request rather than being renamed to CLAUDE.md's catalog spelling. `digit_reversal`'s
"mastery is not penalized" requirement is handled in `graph.py`'s `update_mastery_node`,
which skips the BKT call when the just-recorded bug_type is `digit_reversal` while still
running the normal attempt/retry ladder. Also added `backend/logging/events.py`, a
SQLite event log (one row per submission, signal-bearing or not) wired into
`api.py`'s `submit_answer` via `BackgroundTasks` so it stays off the latency-critical
path. Every hint is machine-checked at ≤12 words in `test_misconceptions_catalog.py`
rather than eyeballed. 20 new tests; full suite (105) green.

## 2026-09-12 — Retry ladder, quest termination, latency split, number pad (revision-plan 1.1–1.4, 6.1)

Implemented the three-attempt retry ladder (`SessionState.attempt_number`/`attempt_history`, new `retry_problem`/`demote_skill`/`end_session` routing in `graph.py`), quest termination (`problems_completed >= quest_length`, 2 skills mastered, or 4 consecutive wrong via a new `EngagementState.consecutive_wrong` field — CLAUDE.md's schema updated to match), and non-signal (blank/rapid-guess) handling that skips BKT and the attempt counter. Fixed a real constraint-#7 violation where `Feedback.correct_answer` was sent unconditionally on wrong answers. Split the three narrative LLM calls off `submit_answer` into a new `GET /sessions/{id}/narrative` endpoint, and found/fixed a second latency bug where flavor-text prefetch was still blocking every submission (including redundant re-generation on every retry attempt) — moved to `BackgroundTasks`, skipped when the problem hasn't changed. Replaced `<input type="number">` with a `NumberPad` component. `backend/tests/test_retry_ladder.py` added (written and confirmed red before implementation); verified live end-to-end in-browser (attempt ladder, root-skill demotion fallback, fatigue-stop terminal screen, sub-15ms submit latency) with no console errors.

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
