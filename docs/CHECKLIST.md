# Verification checklist

Run this as a manual pass. Every item is a thing you can observe in the browser, not a thing you can assume from the code. Companion to `docs/revision-plan.md`.

### A. Feedback is bound to its problem — ready to test (2026-09-12)

- [ ] Answer a problem wrong. The feedback text names a number that belongs to *that* problem, not the previous one.
- [ ] Answer wrong, then trigger a new problem. Old feedback is gone before the new problem paints.
- [ ] Feedback renders inside the problem card. There is no floating banner anywhere in the DOM.

### B. Retry loop

- [ ] Wrong on attempt 1: the same problem stays on screen, the answer is not shown, a specific hint appears. — ready to test (2026-09-12)
- [ ] Wrong on attempt 2: what arrives with the hint depends on the skill's live mastery band, and the manipulative never opens by itself before this point. Below 0.4 it opens pre-loaded with the wrong answer; 0.4 to 0.7 it is highlighted one tap away ("Show me the blocks") but stays closed; above 0.7 the hint stands alone. — ready to test (2026-09-16): verified live in-browser at all three bands for `addition_carry` (0.30 open, 0.55 offered, 0.89 hint-only). `NumberLine` follows the same bands inside its own `number_line/*` remediation window.
- [ ] Wrong on attempt 3: worked solution plays, then the next problem is on the *prerequisite* skill, not the same one. — routing to the prerequisite is ready to test; the "worked solution plays" animation is NOT ready (Part 4/6).
- [ ] A demoted skill comes back once, after two correct answers on the prerequisite; failing it again ends the quest instead of demoting further. — confirmed live in-browser (2026-09-16) via `?seed=struggling`: 3 wrong on `addition_carry` demoted to `addition_no_carry` with a "Take a breath" message; 2 correct there resurfaced `addition_carry` (base10 blocks reopened, low mastery); 3 wrong on the resurfaced skill ended the quest cleanly on the `addition_no_carry` win instead of demoting again, with the still-unresolved misconception listed under "Still practicing." Required fixing a seed bug first — see 2026-09-16 changelog entry.
- [ ] Correct on attempt 2 or 3 is celebrated with effort framing, not treated as a failure. — effort-framing text is ready to test (needs `OPENAI_API_KEY` set; falls back to "Correct!" otherwise).
- [ ] At no point in attempts 1 or 2 does the correct answer appear anywhere, including in the network response payload. — ready to test (2026-09-12); also fixes a real bug where this previously fired unconditionally.
- [ ] The hint/visual/reveal-answer payload actually comes from inside the graph (revision-plan Part 5, "making the graph earn its place"), not a duplicate grading call in the API layer — ready to test (2026-09-14): confirm in `backend/README.md`'s branching diagram and `graph.py`'s `build_remediation_node`; behavior is unchanged from the rows above, this is a structural check.

### C. Diagnosis quality — ready to test (2026-09-13)

- [ ] `86 + 94 → 1017` returns `add_concat_no_carry` with a hint that names the carry, not the answer.
- [ ] `86 + 94 → 70` returns `no_carry` (the existing "column overflow truncated mod 10" rule — kept under its original name rather than CLAUDE.md's catalog spelling `add_carry_dropped`, by request).
- [ ] `42 - 17 → 35` returns `no_borrow_smaller_from_larger`, not `unclassified`.
- [ ] Answer 51 when the answer is 15: returns `digit_reversal`, hint mentions order, mastery score is unchanged (verified in `test_retry_ladder.py`).
- [ ] An answer matching no rule returns a procedural nudge and opens the manipulative. — ready to test (2026-09-14) on `addition_carry`/`subtraction_borrow` (`base10_blocks/unclassified`). It never returns "the answer was X."
- [x] Every bug id in the catalog has a hint under 12 words — machine-checked in `backend/tests/test_misconceptions_catalog.py`, not by eye.

### D. Non-signals

- [ ] Submit blank: no attempt consumed, no BKT update.
- [ ] Submit three answers in under two seconds: held as non-signal (`signal: false` in the event log, not a bug_type — CLAUDE.md's catalog has no `RAPID_GUESS` entry), no BKT update, mascot redirects to the blocks (mascot behavior is Part 4/6 scope).
- [x] Confirm in the event log that these rows exist and are flagged, not silently dropped — ready to test (2026-09-13): `event_log.db`, `signal` column is 0 for blank/rapid-guess rows, `backend/tests/test_events.py` covers this.

### E. Session actually ends

- [ ] Play a fresh, unseeded session correctly all the way through. Subtraction problems are genuinely served, and the quest ends because both parent skills are mastered — not because a problem count ran out. — ready to test (2026-09-16): confirmed live in-browser, 12 problems, ending with Addition 2/2 and Subtraction 2/2.
- [ ] Play a full quest to completion. It stops on a summary screen and does not auto-advance. — ready to test (2026-09-15): `SessionSummary.jsx` replaces the old placeholder; verified live in-browser via `?seed=struggling`.
- [ ] Get four wrong in a row deliberately. The fatigue stop fires and the session wraps gently. — ready to test (2026-09-12); verified live in-browser.
- [ ] From the summary screen, the only way forward is an explicit button. — ready to test (2026-09-15): "Play again" clears the cached session and returns to the name form; verified live in-browser.
- [ ] Summary names specific misconceptions repaired, not just a count. — ready to test (2026-09-15): misconceptions logged against a since-mastered skill are labeled with their real hint text (via new `GET /misconceptions`), deduped by `bug_type`; ones logged against a still-unmastered skill show separately under "Still practicing." Verified live in-browser.

### F. Latency — ready to test (2026-09-12)

- [ ] Submit-to-verdict measured in the network tab is under 150 ms. (Measured ~6–15ms server-side via curl during implementation.)
- [ ] No LLM call appears in the network waterfall between submit and the verdict rendering.
- [ ] Throttle the connection to slow 3G. The verdict still appears instantly; only narrative lags.

### G. Manipulatives — ready to test for all three: bundling sticks (addition-with-carrying and subtraction-with-borrowing), number line (the four `number_line/*` misconceptions), and ten-frame (`addition_no_carry`, opt-in only — that skill has no bug rules, so nothing can auto-open it). As of 2026-09-16 all three are remediation rather than default furniture: none appears on attempt 1, and the mastery band decides what a wrong answer delivers.

- [ ] `86 + 94` can be solved end to end by dragging, with no keyboard. — verified live in-browser with `85 + 94`; subtraction (`42 - 17`, and the borrow-across-zero case `305 - 8`) was originally verified via a temporary local harness because `subtraction_borrow` was unreachable in one sitting. That is no longer true: the "any 2 skills mastered" quest stop is gone and a fresh session played correctly now reaches `subtraction_borrow` in 12 problems (confirmed live 2026-09-16), so this is re-testable by simply playing through.
- [ ] Ten loose sticks cannot remain loose: they glow, snap into a bundle and slide to the tens column, and the per-place counts above the columns update as they do. There is deliberately **no** resolved numeric total on screen — the student reads the place values and enters the number themselves. — ready to test (2026-09-16): the bundling animation and cascading ones→tens→hundreds case were verified earlier; the removal of the "Combined total" readout is verified live in-browser.
- [ ] No manipulative appears on attempt 1 of any problem, at any mastery level, including the first problem of a fresh session (where mastery sits at `p_init` = 0.3 and the old rule opened the blocks before any mistake). — ready to test (2026-09-16): verified live in-browser on a fresh session and on `?seed=struggling`; the opt-in toggle is present and closed.
- [ ] Mastery above 0.7: a wrong answer on attempt 2 gives hint text only — nothing opens — and the manipulative is still reachable through its always-available opt-in. — ready to test (2026-09-16): verified live in-browser at mastery 0.89.
- [ ] Verify the fading changes what a *wrong answer* delivers between the `new` and `fluent` seeds — not what is visible before one, which is now nothing in both cases. `new` lands on `addition_no_carry` at `0.3` (a wrong answer opens the scaffold); `fluent` lands on `addition_carry` at `0.85` (a wrong answer gives hint text only). — ready to test (2026-09-16): both seeds verified live in-browser; `fluent` now plays on instead of ending the quest on its first answer.
- [ ] Number line appears on attempt 2 of an `add_off_by_one`/`add_used_subtraction`/`reversed_operands`/`digit_reversal` diagnosis — opening outright below 0.4, offered one tap away between 0.4 and 0.7, and not at all above 0.7 — shows hop tokens grouped by place value (from `toBlocks`), and only accepts drops on the track (any order). The band gate is new (2026-09-16) and not yet re-confirmed live; the rest was verified live in-browser: `74 + 57` answered `130` on attempt 2 opened the number line with 5 tens-hops + 7 ones-hops from a marker at 74; dragging 1 tens-hop and 2 ones-hops advanced the readout 74 → 84 → 86 correctly; the widget was gone again once attempt 3 (worked-solution/demotion) took over.
- [ ] Ten-frame is reachable for `addition_no_carry` through its always-available "Show frame" opt-in, pre-fills `a` cells, and fills the remaining cells by dragging `b` supply dots one at a time. It is never auto-opened: that skill has no bug rules, so no diagnosis ever names a visual for it. — the drag behaviour was verified live in-browser (a fresh `2 + 2` session showed 2 pre-filled cells + 2 draggable supply dots; dragging both filled the frame to 4/10 and the supply tray emptied); the opt-in-only gating is new (2026-09-16) and confirmed closed-by-default live, but the drag path has not been re-walked since.

### H. Touch and tablet

- [ ] Every drag works with a finger on a real tablet, or at minimum in Chrome device emulation with touch enabled. — bundling sticks verified with simulated pointer drags (mouse-derived pointer events); real touch-device/emulation pass still outstanding.
- [ ] Dragging a stick does not scroll the page. — `touch-action: none` is set on the canvas and every token; not yet confirmed on a real touch device.
- [ ] Number pad keys are at least 64px and hittable with a thumb. — ready to test (2026-09-12); CSS sets 64x64px minimum.
- [ ] Full session playable at 1024 x 768 with nothing clipped or off-screen, including no horizontal scrolling with the widest problem the generator can produce (`999 + 999`, nine tokens in every place of both operands) and the blocks open. — ready to test (2026-09-16): measured live at the 1024-viewport layout with every place forced to nine tokens — no element's `scrollWidth` exceeds its `clientWidth` and the page does not scroll sideways. Token art is now capped at the 48px touch target in both dimensions (a ones-stick previously rendered 48x144). The equation is pinned and stays on screen throughout.

### I. Copy

- [ ] No feedback string anywhere exceeds its cap. Assert this in a test over the template file.
- [ ] Speed praise only fires when mastery is above 0.7. Confirm by forcing a fast correct answer on a low-mastery skill and checking the line names the skill, not the speed.
- [ ] Every generated word problem is under 20 words. Validate in code with a regeneration fallback. — ready to test (2026-09-15): `flavor_word_problem` checks the word count and regenerates once with a "too long" nudge before falling back to the plain numeric problem; machine-checked in `test_narrative.py` via a mocked `_complete`, not by eye against a real API call.

### J.5 Digit-width progression — ready to test (2026-09-16)

- [ ] Start a fresh session on `addition_no_carry`. The first problem has single-digit operands (e.g. `7 + 0`).
- [ ] Answer correctly twice in a row. Digit-width should not jump straight to 3-digit — it advances to 2-digit only, even though BKT mastery itself crosses 0.8 on the very first correct answer.
- [ ] The first correct answer at 1-digit is a "trivial" combo (an operand is 0); the second is not, before the tier advances.
- [ ] `addition_carry`/`subtraction_borrow` (which start at 2-digit, never 1-digit) need 3 correct answers in a row to reach 3-digit, not 2.
- [ ] `?seed=borrowing` still lands on 3-digit `subtraction_borrow` problems immediately, not 2-digit.

### J. Demo readiness

- [ ] All four seeds load directly from a URL and land in the right state, including `?seed=borrowing` (added 2026-09-16, verified live), which lands on `subtraction_borrow` at mastery `0.3` with all three prerequisites mastered — the `open` band, so a wrong attempt 2 opens the blocks, and an explicit `digit_level` at the skill's own top tier (2026-09-16: digit-width no longer follows from mastery, see `_difficulty_ladder.py`), so problems start at 3-digit immediately rather than ramping up. — ready to test (2026-09-14): `?seed=new|struggling|fluent` still shows the name form (so a real name can be typed on camera), then calls `POST /sessions/seed/{name}` instead of the plain start; `struggling` lands on `addition_carry` at mastery `0.3` with one prior `add_concat_no_carry` misconception and its prerequisite reading as mastered (it ships a `mastery_run` so the sustained-mastery gate passes); `fluent` lands on `addition_carry` at `0.85` one answer short of completing the Addition parent skill. Both carry `quest_length` 16. Re-verified live in-browser 2026-09-16: no manipulative is open on load for either, and `fluent` now plays on instead of ending the quest on its first answer.
- [ ] Refresh mid-session: the same problem and the same attempt count come back. — ready to test (2026-09-14): unchanged `GET /sessions/{id}` path, now backed by a `SessionResponse` that also carries `skill_mastery`/`misconception_log`/`problems_completed`/`quest_length`/`attempt_number`. Verified live in-browser.
- [ ] Kill and restart the server mid-session: the frontend recovers rather than white-screening. — ready to test (2026-09-14): a 404 on `GET` triggers `POST /sessions/{id}/restore` from the browser's own cached (correct-answer-free) snapshot, reinstalling mastery/XP/misconceptions under the same session id with a freshly generated problem on the same skill (attempt count resets to 1 — the pre-restart problem's answer was never sent to the client to begin with). A backend that's simply unreachable (not just restarted) now shows a visible "Can't reach the server" message instead of silently dropping the session. Verified live: killed and restarted uvicorn mid-session, confirmed recovery; also confirmed the fully-unreachable case shows the message and keeps the cached session.
- [ ] Open the live link in a fresh incognito window as a judge would. Something interesting is visible within ten seconds. — ready to test (2026-09-15): all six Part 6 UI-shell items now implemented (number pad, hero-manipulative layout, quest map, 4-state mascot, real end-of-quest report, sound). Judgment call on "interesting within ten seconds" still needs a human look.
- [ ] LangSmith shows traces for all four LLM touchpoints. — ready to test (2026-09-15): `langsmith` added as a dependency and the OpenAI client is wrapped with `wrap_openai` in `narrative._client()`, so each touchpoint's completion call auto-emits a traced run regardless of call site (all four run outside `graph.app.invoke()`, so graph-level auto-tracing alone wouldn't have caught them). Needs a real `OPENAI_API_KEY` plus `LANGSMITH_TRACING`/`LANGSMITH_API_KEY`/`LANGSMITH_PROJECT` set and a manual look at the LangSmith UI — not machine-checkable.
- [ ] The event log has one row per submission with `bug_id` populated.
