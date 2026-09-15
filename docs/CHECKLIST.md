# Verification checklist

Run this as a manual pass. Every item is a thing you can observe in the browser, not a thing you can assume from the code. Companion to `docs/PLAN.md`.

### A. Feedback is bound to its problem — ready to test (2026-09-12)

- [ ] Answer a problem wrong. The feedback text names a number that belongs to *that* problem, not the previous one.
- [ ] Answer wrong, then trigger a new problem. Old feedback is gone before the new problem paints.
- [ ] Feedback renders inside the problem card. There is no floating banner anywhere in the DOM.

### B. Retry loop

- [ ] Wrong on attempt 1: the same problem stays on screen, the answer is not shown, a specific hint appears. — ready to test (2026-09-12)
- [ ] Wrong on attempt 2: the manipulative opens automatically, pre-loaded with the wrong answer. — ready to test (2026-09-14) for `addition_carry`/`subtraction_borrow` (the `base10_blocks/*` visual family); `number_line/*` bug types still render hint-text only, by design (separate manipulative, not yet built).
- [ ] Wrong on attempt 3: worked solution plays, then the next problem is on the *prerequisite* skill, not the same one. — routing to the prerequisite is ready to test; the "worked solution plays" animation is NOT ready (Part 4/6).
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

- [ ] Play a full quest to completion. It stops on a summary screen and does not auto-advance. — ready to test (2026-09-15): `SessionSummary.jsx` replaces the old placeholder; verified live in-browser via `?seed=struggling`.
- [ ] Get four wrong in a row deliberately. The fatigue stop fires and the session wraps gently. — ready to test (2026-09-12); verified live in-browser.
- [ ] From the summary screen, the only way forward is an explicit button. — ready to test (2026-09-15): "Play again" clears the cached session and returns to the name form; verified live in-browser.
- [ ] Summary names specific misconceptions repaired, not just a count. — ready to test (2026-09-15): misconceptions logged against a since-mastered skill are labeled with their real hint text (via new `GET /misconceptions`), deduped by `bug_type`; ones logged against a still-unmastered skill show separately under "Still practicing." Verified live in-browser.

### F. Latency — ready to test (2026-09-12)

- [ ] Submit-to-verdict measured in the network tab is under 150 ms. (Measured ~6–15ms server-side via curl during implementation.)
- [ ] No LLM call appears in the network waterfall between submit and the verdict rendering.
- [ ] Throttle the connection to slow 3G. The verdict still appears instantly; only narrative lags.

### G. Manipulatives — ready to test (2026-09-14) for all three: bundling sticks (addition-with-carrying and subtraction-with-borrowing), number line (the four `number_line/*` misconceptions), and ten-frame (`addition_no_carry` low-mastery scaffold)

- [ ] `86 + 94` can be solved end to end by dragging, with no keyboard. — verified live in-browser with `85 + 94`; also verified subtraction (`42 - 17`, and the borrow-across-zero case `305 - 8`) via a temporary local harness, since reaching `subtraction_borrow` through a live session isn't currently possible in one sitting (mastery resets per session, and the quest ends after 2 skills mastered — a pre-existing backend behavior, not something this change touched).
- [ ] Ten loose sticks cannot remain loose. They bundle, and the number below updates as they do. — verified, including the cascading ones→tens→hundreds case.
- [ ] Mastery below 0.4: the manipulative is open by default. — verified.
- [ ] Mastery above 0.7: the manipulative is hidden and available only on request, and a wrong answer on attempt 2 still force-opens it regardless of band. — verified.
- [ ] Verify the fading actually changes between the `new` and `fluent` seeds. — NOT testable yet: the `?seed=` profile system is still out of scope (not built). Fading itself is implemented and testable within a single live session by playing enough problems to cross the 0.4/0.7 mastery bands.
- [ ] Number line force-opens on attempt 2 of an `add_off_by_one`/`add_used_subtraction`/`reversed_operands`/`digit_reversal` diagnosis, shows hop tokens grouped by place value (from `toBlocks`), and only accepts drops on the track (any order). — verified live in-browser: `74 + 57` answered `130` on attempt 2 opened the number line with 5 tens-hops + 7 ones-hops from a marker at 74; dragging 1 tens-hop and 2 ones-hops advanced the readout 74 → 84 → 86 correctly; the widget was gone again once attempt 3 (worked-solution/demotion) took over.
- [ ] Ten-frame shows for `addition_no_carry` at low mastery, pre-fills `a` cells, and fills the remaining cells by dragging `b` supply dots one at a time. — verified live in-browser: a fresh `2 + 2` session showed 2 pre-filled cells + 2 draggable supply dots; dragging both filled the frame to 4/10 and the supply tray emptied.

### H. Touch and tablet

- [ ] Every drag works with a finger on a real tablet, or at minimum in Chrome device emulation with touch enabled. — bundling sticks verified with simulated pointer drags (mouse-derived pointer events); real touch-device/emulation pass still outstanding.
- [ ] Dragging a stick does not scroll the page. — `touch-action: none` is set on the canvas and every token; not yet confirmed on a real touch device.
- [ ] Number pad keys are at least 64px and hittable with a thumb. — ready to test (2026-09-12); CSS sets 64x64px minimum.
- [ ] Full session playable at 1024 x 768 with nothing clipped or off-screen.

### I. Copy

- [ ] No feedback string anywhere exceeds its cap. Assert this in a test over the template file.
- [ ] Speed praise only fires when mastery is above 0.7. Confirm by forcing a fast correct answer on a low-mastery skill and checking the line names the skill, not the speed.
- [ ] Every generated word problem is under 20 words. Validate in code with a regeneration fallback.

### J. Demo readiness

- [ ] All three seeds load directly from a URL and land in the right state. — ready to test (2026-09-14): `?seed=new|struggling|fluent` still shows the name form (so a real name can be typed on camera), then calls `POST /sessions/seed/{name}` instead of the plain start; `struggling` lands on `addition_carry` at mastery `0.3` (manipulative open) with one prior `add_concat_no_carry` misconception, `fluent` lands on `addition_carry` at mastery `0.85` (abstract-only). Verified live in-browser.
- [ ] Refresh mid-session: the same problem and the same attempt count come back. — ready to test (2026-09-14): unchanged `GET /sessions/{id}` path, now backed by a `SessionResponse` that also carries `skill_mastery`/`misconception_log`/`problems_completed`/`quest_length`/`attempt_number`. Verified live in-browser.
- [ ] Kill and restart the server mid-session: the frontend recovers rather than white-screening. — ready to test (2026-09-14): a 404 on `GET` triggers `POST /sessions/{id}/restore` from the browser's own cached (correct-answer-free) snapshot, reinstalling mastery/XP/misconceptions under the same session id with a freshly generated problem on the same skill (attempt count resets to 1 — the pre-restart problem's answer was never sent to the client to begin with). A backend that's simply unreachable (not just restarted) now shows a visible "Can't reach the server" message instead of silently dropping the session. Verified live: killed and restarted uvicorn mid-session, confirmed recovery; also confirmed the fully-unreachable case shows the message and keeps the cached session.
- [ ] Open the live link in a fresh incognito window as a judge would. Something interesting is visible within ten seconds. — ready to test (2026-09-15): all six Part 6 UI-shell items now implemented (number pad, hero-manipulative layout, quest map, 4-state mascot, real end-of-quest report, sound). Judgment call on "interesting within ten seconds" still needs a human look.
- [ ] LangSmith shows traces for all four LLM touchpoints.
- [ ] The event log has one row per submission with `bug_id` populated.
