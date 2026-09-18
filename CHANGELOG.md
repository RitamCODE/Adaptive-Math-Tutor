# Changelog

## 2026-09-18 — Deployed to Railway (backend) + Vercel (frontend)

Made `API_BASE`/CORS `allow_origins` env-var-driven (`VITE_API_BASE`, `FRONTEND_ORIGIN`) instead of
hardcoded to localhost, and added a `Procfile` so Railway's Railpack builder finds the uvicorn start
command (it doesn't auto-detect a nested `backend.api:app` module). Backend runs as a single Railway
replica/worker, matching the in-memory `_SESSIONS` constraint. Verified end to end in a real browser
against the live URLs: session start, wrong-then-correct retry ladder, refresh-resume, and the
`?seed=fluent` deep link all work cross-origin. LLM narrative touchpoints and LangSmith tracing are
pending new API keys (the originals were exposed in a terminal session and revoked).

## 2026-09-17 — Simulated-learner results added to README, full data in new KNOWN_GAPS.md

Added a README section reporting the eval's headline finding (engine-confirmed mastery, not
ground-truth mastery, is where adaptive pacing shows a real ~9-point edge, in 2 of 4 ability
profiles) and a new top-level `KNOWN_GAPS.md` with the complete per-profile/per-skill/session-
length data plus two-proportion z-tests and a multiple-comparisons caveat (the finding survives
BH-FDR within its own test family but not a Bonferroni correction across every test run). Every
percentage in both files uses one consistent round-half-up rule, checked against the exact
n/200 counts rather than trusting the eval script's own (banker's-rounding) console output.

## 2026-09-17 — Simulated-learner harness: verified metric independence, added digit-width effect

Added `effective_p_slip`/`width_sensitivity_true` so a synthetic learner's true correctness now
degrades with a problem's digit-width, since without it the digit-width ladder had zero causal
effect on simulated outcomes. Confirmed (and added tests proving) the "true/engine mastered"
metrics use the real, unpatched `is_mastered` independent of the baseline's routing patches, and
that those patches never leak into a later adaptive run. Along the way, found and fixed a
reproducibility bug: problem generators draw from a shared `default_rng` singleton, not the
seedable global `random` module, so `simulate.py` now reseeds that singleton directly.
`simulate.py` also gained per-ability-profile breakdown and a turn-count distribution.

## 2026-09-17 — Simulated-learner evaluation harness

Added `backend/eval/` (synthetic_learner.py, driver.py, baseline.py, simulate.py), an offline
tool separate from the shipped app: synthetic students with an independent hidden
slip/guess/learning-rate per skill are driven turn-by-turn through the real, compiled
`backend.graph.app` (no FastAPI/LLM/SQLite involved) and compared against a non-adaptive
baseline that swaps only `is_mastered`/`select_next_skill`/`_difficulty_for` (via targeted
monkeypatches on `backend.graph`'s namespace) for a fixed problems-per-skill budget and a
pinned digit-width, while sharing the real BKT update, retry ladder, and session-end rules.
4 new sanity tests in `test_eval_simulation.py`, one of which caught a real bug (the fixed
schedule's fallback returning a still-locked skill once every unlocked skill's budget ran
out) before it shipped.

## 2026-09-17 — Mastery card's three narrative lines are now sequential, color-coded steps

The mastery-moment card stacked its three narrative lines as plain unstyled text under
one "Next" button; the user asked for something more engaging. `FeedbackBanner.jsx` now
shows one step at a time (gold trophy = mastery, coral lightning = reward, teal sword =
boss-battle), each with progress dots and its own "Next →", advancing to the real next
problem only from the last step. New CSS in `App.css` reuses the app's existing
coral/gold/teal palette and its column-arithmetic entrance-animation style.

## 2026-09-17 — Mastery-card narratives merged into one structured LLM call

The mastery-moment card's three lines (mastery, reward, boss-battle) each came from
their own sequential OpenAI call with a near-identical prompt and no visibility into
what the other two would say, which read as formulaic and tripled the endpoint's
latency. `mastery_moment_narrative`, `effort_reward_narrative`, and
`boss_battle_narrative` are replaced by one `mastery_card_narrative` structured-output
call in `backend/llm/narrative.py` that shares full context across all three lines and
is explicitly told to vary their openers; `flavor_word_problem` is untouched.

## 2026-09-17 — Mastery moment no longer shows a stale, seemingly-live problem

The already-answered problem stayed on screen behind the mastery-moment narrative
until "Next" was clicked, and its brief correct-flash faded long before a student
finished reading; after that it looked like a plain unanswered problem sitting above
a subtly-disabled number pad, which read as broken rather than solved.
`ProblemCard.jsx` now hides the equation, manipulative canvas, and number pad while
`justAdvanced` is true, showing only the narrative banner and "Next" — which exposed
a second bug where `handleAdvance()` never reset `justAdvanced`, permanently hiding
the next problem after "Next" was clicked; both are fixed together. Verified live
through a full `addition_carry -> subtraction_no_borrow` mastery transition.

## 2026-09-17 — All four skills now render their equation stacked

`addition_no_carry` and `subtraction_no_borrow` used to render a plain horizontal
equation string, while `addition_carry`/`subtraction_borrow` stacked theirs in
column form via `ColumnArithmetic`. Added `StackedEquation.jsx`, a lighter
column-stack (no annotation row, no answer row, no block manipulative) reusing
`ColumnArithmetic`'s CSS, so every skill now stacks its equation. Manipulatives
are unchanged: `TenFrame` still backs `addition_no_carry`, `subtraction_no_borrow`
still has none, and the two regrouping skills keep their full block manipulative.
Verified live across all four skills via seeded profiles.

## 2026-09-17 — Backend-restart recovery now asks before reinstalling a stale session

A backend restart wipes the in-memory session store, but the browser's cached
localStorage snapshot survives it; the frontend was silently reinstalling that
snapshot on the next reload (via `POST /sessions/{id}/restore`), which could
land a student — or a developer testing a fresh flow — back mid-quest on a
downstream skill with no indication why. `App.jsx`'s mount effect now stops at
a new `ResumeSessionPrompt` on a 404-triggered recovery instead of restoring
automatically; the student picks "Resume" (unchanged restore payload/behavior)
or "Start fresh" (clears localStorage, falls through to the name form). A
plain refresh with the backend still alive is unaffected. Verified live:
restarted the backend mid-session and confirmed both branches.

## 2026-09-17 — Session restore was dropping sustained-mastery runs

When the backend restarts mid-session, the frontend recovers by POSTing its cached
snapshot to `/sessions/{id}/restore`. That payload carried `skill_mastery` and
`active_skill` but not `mastery_run` — so a restored session kept its real BKT
probabilities and kept resuming wherever it had left off (including a downstream skill
like subtraction), while `is_mastered()`, which requires 3 consecutive sustained answers
and not just a high probability, saw every run reset to zero and reported every skill
unmastered. The trail map showed a skill as still in progress while the problem on
screen was already from further along. Fixed by including `mastery_run` in the restore
payload (`frontend/src/App.jsx`), matching the resurface fields it was already sent
alongside.

## 2026-09-17 — Number pad's ones-first entry now matches carrying, not just digit order

The previous ones-first fix prepended every keystroke, so a carrying answer like 148 (from
97 + 51) typed as 8, then 4, then 1 — reproducing digit order but not the arithmetic: a
column only ever writes one digit, carrying the rest into the next column, except the
final column, which has nowhere left to carry into and may write two. `NumberPad` now
takes a `columnCount` (the wider operand's digit count, computed from `problem.question`
via the existing `parseQuestion` in `frontend/src/lib/arithmetic.js`) so it can tell a
new-column keystroke (prepend) from the final column's own second digit (inserted right
after its first): 97 + 51 now types 8 -> 18 -> 148, and 91 + 9 types 0 -> 10 -> 100.

## 2026-09-16 — Mastery narrative needs a click, number pad types ones-first

The mastery-moment banner (LLM narrative across all three touchpoints) was disappearing on
a fixed 4-second timer regardless of whether the student had finished reading it. It now
stays up with a "Next" button; the next-stage payload is already known when the button
appears, so clicking it doesn't wait on the narrative fetch. Separately, the number pad
now enters digits ones-first — each new digit is prepended rather than appended, and
backspace drops the leftmost (most recently typed) character — mirroring how column
arithmetic is actually solved right to left, instead of typing like a left-to-right
calculator.

## 2026-09-16 — Digit-width ladder decoupled from BKT mastery; narrative word budgets

A student's first correct answer on a skill lifted BKT mastery from 0.3 to ~0.9 (by
design — see `bkt.py`), and digit-width was reading that raw mastery value straight into
a 3-bucket table, so problems jumped from 1-digit to 3-digit with no 2-digit step.
Digit-width is now its own sustained-run ladder per skill (`_difficulty_ladder.py`),
entirely independent of mastery: 3 consecutive correct answers advance most tiers, and
the narrowest (1-digit) tier additionally escalates trivial-then-non-trivial across its
2-correct gate. Separately, `mastery_moment_narrative`/`effort_reward_narrative`/
`boss_battle_narrative` now state an explicit 20-word budget in their prompts (mirroring
the word-problem touchpoint), since the missing budget was letting the model write two
sentences and `copy.js`'s truncation silently drop the specific one, leaving only generic
praise on screen.

## 2026-09-16 — Column arithmetic: the blocks and the written digits become one thing

Browser testing of subtraction found the borrow flow to be a dead end. The mechanic existed
— `runTransition("unbundle", …)` is the carry animation run backwards, and was already wired
for subtraction — but the only way to reach it was dragging a tens bundle onto the ones
*column*, cued by nothing but a pulsing border. The take-away target was a caption
(`"3 tens, 8 ones"`), so removing a piece deleted a phrase rather than changing an object,
which made the student's own actions read as things the app had done for them. Replaced
`BundlingSticks` with `ColumnArithmetic`: the equation is stacked in column form and the
block columns sit under their own digit columns (one shared `grid-template-columns`), work
runs right to left one column at a time, the subtrahend is drop-slots that fill as pieces
land in them, and a short column offers a labelled pad that breaks a block open where the
student can watch it. Each column's answer digit appears under the rule when that column is
finished — the per-column exception now recorded in CLAUDE.md, since the digits are results
the student produced, not a tally the app keeps. Addition uses the same grid. Pure board
logic split into `lib/columnBoard.js` and swept over every problem the curriculum can
generate (426k cases, including borrow-across-zero, which chains two visible steps).

Also: the mastery narrative no longer flashes. It costs up to three serial OpenAI calls, so
merging it into a fixed 4s window that started at submit left it about a second of life; the
card is now held until it resolves (capped at 6s) and the reading window starts from there,
the fetch only fires on an advance, a per-turn id replaces the `problem_id` merge guard that
aliased across retries of the same problem, and the 20-word cap CLAUDE.md requires is
enforced on sentence boundaries. Praise strategy branch was `"Nice use of the tool!"` — five
words against a four-word cap, so it shipped as `"Nice use of the"`; the literal is now
four words and `capWords` warns in dev when it truncates. Added `?seed=borrowing`, without
which `subtraction_borrow` is ~12 correct answers from a fresh start.

## 2026-09-16 — Sustained mastery, skill groups, and manipulatives as remediation

Three connected defects made the app mis-describe what a student knows. With the project's
BKT parameters one correct answer lifts a fresh skill from 0.30 to 0.9025, so a bare
`>= 0.8` check flagged every skill mastered on its first success; `route_after_engagement`
then ended the quest at `mastered_count >= 2`, which — because the DAG unlocks strictly in
order — was in practice "both addition sub-skills done", leaving subtraction unreachable by
play and ending the `fluent` seed on its first answer. Mastery now has to be *held*: a skill
counts as mastered only after being at or above 0.8 following each of the last 3 consecutive
signal-bearing answers (`MASTERY_MIN_RUN`, tracked in a new `SessionState.mastery_run`),
expressed as one helper, `is_mastered(skill, state)`, that every raw threshold comparison in
the codebase now calls — routing, `select_next_skill` (which takes the whole `SessionState`
now), `SkillGraph.is_unlocked`, and the `mastered` flag `api.py` sends the UI — so the engine
and the interface cannot disagree. Non-signal submissions and `digit_reversal` answers leave
the run untouched rather than resetting it, matching the existing "mastery is not penalized"
rule. Added the skill-group model to `skill_graph.py`: the four skills are two parent skills
of two sub-skills each, each sub-skill keeping its own independent mastery and threshold, and
the quest now ends when both parents are mastered, on `quest_length` (raised 10 → 16, since a
flawless run needs 12 problems), or on the unchanged 4-consecutive-wrong fatigue stop.
Manipulatives stopped being default furniture: `bandFromMastery` moved to a shared
`frontend/src/lib/remediation.js` and was repointed at the remediation decision, so nothing
opens on attempt 1 at any mastery (a fresh student at `p_init` = 0.3 previously got blocks
before making a single mistake) and a wrong answer's band decides what arrives with the hint —
below 0.4 the manipulative opens pre-loaded, 0.4–0.7 it is highlighted one tap away, above 0.7
the hint stands alone — with the opt-in toggle available at every level and closed by default.
Pinned the equation above the manipulative area as a sticky line (it sat *below* a full card of
block rows and scrolled off), capped token art at the 48px touch target in both dimensions (a
ones-stick was rendering 48x144 from a stretched 16x48 viewBox), and removed the "Combined
total" readout, which tallied the assembled place values into the finished answer before the
student typed it — the piles, per-place counts and bundling animation all stay. Re-tuned all
three seeds with `mastery_run` and the new quest length, leaving `fluent` one answer short of
completing Addition so it plays instead of ending immediately. Also fixed a gap the rewrite
exposed: the quest-end check runs before the advance branch, so the answer mastering the final
skill exited as `end_session` and never queued LLM touchpoints 2 and 3 — the session's biggest
moment was the one that went unnarrated. 26 new tests (new `test_mastery_gate.py`, plus the
first coverage of either quest-end condition); full suite (154) green. Verified live
in-browser at 1024x768: a fresh session reaches and is served `subtraction_borrow` and ends on
curriculum completion in 12 problems, no manipulative appears on any attempt 1, all three
bands behave distinctly, and `999 + 999` with every place at nine tokens produces no
horizontal scrolling. Docs swept against the new behaviour: `CLAUDE.md`, all three READMEs and
eight `CHECKLIST.md` rows, plus a pass-2 table in `docs/DOCS_AUDIT.md`; `revision-plan.md` and
`UI_DESIGN.md` left frozen per their role. The sweep also turned up two pre-existing errors and
fixed them: both READMEs claimed `skill_mastery`/`misconception_log` "never reach the client"
when they are in fact sent as the localStorage snapshot, and the root README carried a
parenthetical about stale `docs/PLAN.md` references that had themselves been fixed in `957ca15`.

## 2026-09-16 — Fixed `struggling` seed blocking skill-resurfacing demo, verified live

The `struggling` seed profile (`backend/api.py`) started `engagement.consecutive_wrong` at 1
instead of 0. Since `route_after_engagement` checks the 4-consecutive-wrong fatigue stop
before the attempt-3 demote branch, three wrong answers on the seed's starting problem hit
exactly 4 consecutive wrong and ended the session via the fatigue stop instead of demoting —
meaning the seed built for demoing revision-plan 7.3's resurfacing behavior could never
actually reach it. Confirmed the underlying graph logic itself was already correct (direct
`graph.app.invoke()` calls with `consecutive_wrong=0` demote and resurface exactly per spec)
before concluding the seed fixture was the only broken part. Fixed by starting the seed at
`consecutive_wrong=0`; no test asserted the old value. Verified the full flow live in the
browser via `?seed=struggling`: demote to `addition_no_carry` ("Take a breath" message), two
correct answers there resurface `addition_carry` (blocks reopen at its still-low mastery), a
third failure on the resurfaced skill ends the quest cleanly on the lower-level win with the
unresolved misconception listed under "Still practicing." Full suite (128) still green.

## 2026-09-16 — Fixed stale flavor text on problem transitions

Found during a full-system check: `_to_session_response` served whatever flavor text was
cached for the session regardless of which problem it was generated for. Since
`_refresh_flavor_text` runs as a background task scheduled *after* a new problem is already
in the response, every problem transition briefly (and, since the frontend never re-polls,
often permanently) showed the *previous* problem's story glued to the new numbers — e.g.
"44 + 66" paired with a story about "3 toy cars... 5 more toy cars" left over from the prior
problem. Fixed in `backend/api.py` by only returning the cached text when
`_FLAVOR_TEXT_PROBLEM_ID` matches the current problem's id, falling back to `None` (plain
numeric problem) otherwise, per touchpoint 1's documented fallback behavior. Full suite
(128) still green; reproduced and confirmed fixed live via the API.

## 2026-09-16 — Documentation audit

Checked every README/`CLAUDE.md`/`docs/*.md` against the actual code. Found and fixed five
stale living-reference docs: `README.md`'s "Not yet built" list still claimed manipulatives,
the end-of-quest report, and seeded demo profiles were missing (all three shipped 2026-09-14/15);
`backend/README.md`'s endpoint table and `SessionState` field list were missing the seed/restore/
misconceptions endpoints and the skill-resurfacing fields; `frontend/README.md`'s file tree was
missing the three manipulative components and `lib/`; `docs/CHECKLIST.md` still referenced the
renamed `docs/PLAN.md`; `CLAUDE.md`'s `SessionState` schema was missing the resurfacing fields.
Added `docs/DOCS_AUDIT.md` to track doc currency going forward. `UI_DESIGN.md` and
`docs/revision-plan.md` are left as-is — both are frozen historical planning docs, not living
references.

## 2026-09-15 — Deterministic per-problem praise, touchpoint 3 gating, feedback display timing

Closed a spec gap flagged during review: `FeedbackBanner.jsx` was rendering the touchpoint-3
LLM narrative directly as the per-problem "Correct!" line instead of the deterministic
four-branch lookup CLAUDE.md's copy-limits section requires. Added `frontend/src/lib/praise.js`
(effort > strategy > speed > named-skill, each capped to 4 words) and fixed the root cause in
`backend/api.py`: the reward-narrative context was being queued on every correct answer
(`if diagnosis.correct`) instead of only at the mastery moment (`next_action == "advance_skill"`),
so touchpoint 3 was firing ~10x more than its own spec allows. Also discovered and fixed a
pre-existing bug where a correct answer's graph turn advances `current_problem` in the same
response as its feedback, leaving no render frame for any correct-answer banner (old or new) to
appear in — `App.jsx` now holds a `displayData` snapshot behind the live `sessionData` for a
timed delay (longer at the mastery moment, to give the async narrative fetch a chance to
resolve) before revealing the next problem or the end-of-quest screen. 3 new backend tests;
full suite (128) green; all four praise branches confirmed live in the browser.

## 2026-09-15 — Word-problem length cap, LangSmith tracing, skill resurfacing (revision-plan Part 7.3/7.4/7.5)

Closed the three remaining Part 7 demo-readiness gaps. `flavor_word_problem` now enforces
the 20-word/one-name/one-object/digits-not-words cap in its prompt and validates the
result in code, regenerating once with a "too long" nudge before falling back to `None`
(plain numeric problem) if it still overruns. Added `langsmith` as a dependency (the
CLAUDE.md-pre-authorized exception) and wrapped the OpenAI client with
`langsmith.wrappers.wrap_openai` in `_client()` — necessary because all four narrative
touchpoints run from FastAPI background tasks and a separate endpoint, never inside
`graph.app.invoke()`, so LangGraph's own auto-tracing would never see them. Implemented
skill resurfacing: `SessionState` gained `pending_resurface`/`resurface_progress`/
`resurfaced_skills`, `demote_skill_node` now queues the demoted skill, a new
`resurface_skill_node` brings it back after two correct answers on the prerequisite
(deliberately bypassing the mastery-threshold check, since that prerequisite is usually
already mastered and would otherwise resurface after one answer via a misfired
`advance_skill`), and a second attempt-3 failure on the resurfaced skill ends the quest
rather than demoting again. Threaded the three new fields through `SessionResponse`/
`RestoreRequest`/`_install_seeded_state` and `App.jsx`'s restore call so a refresh
mid-resurface-window doesn't silently drop it. 20 new tests; full suite (125) green.

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
