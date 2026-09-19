# AdaptMATH — Frontend

A minimal browser UI for AdaptMATH: problem display, answer input, skill map, and XP/streak tracking, driven entirely by the FastAPI backend in `../backend`.

## Stack

Vite + plain React. No router, no state-management library, no CSS framework. Per the project's "frontend stays minimal" constraint (see the repo root `CLAUDE.md`), the time budget goes into the backend's adaptive engine, not UI infrastructure — there's exactly one page and one piece of client state, so none of that machinery earns its keep here.

## Running it

See the root [`README.md`](../README.md#running-it-locally) for the exact commands — this app **requires the backend running separately**, since `src/api.js` hardcodes `http://localhost:8000` as its base URL and the backend's CORS allowlist (`backend/api.py`) only permits `http://localhost:5173` / `127.0.0.1:5173`. If you serve the frontend on a different port, both sides need updating together.

## File structure

```
src/
  main.jsx              mounts <App /> into #root
  App.jsx                the single state owner — see "How it fits together" below
  api.js                  fetch wrappers for the backend endpoints
  constants.js            skill display names (presentation only — misconception hint
                           text now comes pre-rendered from the backend, see below)
  App.css                 all styling; no CSS framework
  index.css                base HTML/body reset loaded once in main.jsx
  components/
    StudentIdForm.jsx      start-session form
    ProblemCard.jsx         current problem + flavor text + feedback + NumberPad + manipulative canvas
    NumberPad.jsx           on-screen digit/backspace/submit pad — no <input type="number"> anywhere;
                             also accepts physical-keyboard digits/Backspace/Enter and a draggable
                             text cursor on the answer display
    FeedbackBanner.jsx      correct/incorrect feedback + misconception hint + narrative copy
    SkillTrailMap.jsx       skill progress as a winding trail of locked/current/mastered nodes,
                             grouped under the two parent skills (Addition, Subtraction) with an
                             "n of 2" count per group
    StatsBar.jsx            XP, streak, frustration note
    Mascot.jsx              growth-stage companion that reacts to answers (idle/thinking/correct/incorrect)
    BundlingSticks.jsx      base-10-blocks manipulative for addition-with-carrying and subtraction-with-borrowing
    NumberLine.jsx          manipulative for the four number_line/* misconceptions (off-by-one, operator
                             misread, reversed operands, digit reversal)
    TenFrame.jsx            opt-in scaffold for addition_no_carry (which has no bug rules of its own,
                             so nothing can auto-open it — it appears only on request)
    SessionSummary.jsx      end-of-quest report — skills mastered, misconceptions repaired, "Play again"
  lib/
    arithmetic.js           parses `question` strings into place-value blocks for the manipulatives
    remediation.js           bandFromMastery(): which remediation a wrong answer earns —
                             open / offered / hint-only, at the 0.4 and 0.7 mastery bands
    praise.js                the deterministic four-branch per-problem praise lookup (speed/named-skill/
                             effort/strategy) CLAUDE.md's copy-limits section requires — not an LLM call
    sound.js                 three Web Audio API synthesized sound effects (correct, bundle-into-ten,
                             quest complete) — no binary audio assets or libraries
```

## How it fits together

`App.jsx` is the only component that holds state or talks to `api.js`. Everything under `components/` is presentational: it receives data as props and reports user actions through callback props (`onStart`, `onSubmit`). There's no context provider and no global store — data flows down as props, actions flow up as callbacks, and `App` is the single place that reconciles a callback with a new `fetch` call and a state update.

`App` holds:
- `sessionData` — the last `SessionResponse`/`AnswerResponse` from the backend (current problem, engagement, skill progress, session id, `next_action`)
- `feedback` — the `Feedback` object from the most recent answer (`null` before the first answer), later merged with whatever `getNarrative` resolves to
- `justAdvanced` — set from `data.next_action === "advance_skill"` on each answer response; tells `FeedbackBanner` to show the mastery-moment and boss-battle lines alongside the ordinary correct message
- `reaction` — derived from `feedback.correct`, drives both `Mascot`'s transient correct/incorrect pose and `ProblemCard`'s flash/shake/confetti, then reverts to `"idle"` after a fixed timeout
- `loading` / `error` — request status
- `resuming` — true only during the initial mount's `getSession` resume check, so nothing renders as "start a new session" for a frame before that resolves
- `problemStartRef` — a timestamp ref reset whenever the current problem's `problem_id` changes, used to measure `time_taken_sec`

`api.js` is the only module that calls the backend. Its seven functions (`startSession`, `seedSession`, `restoreSession`, `getSession`, `submitAnswer`, `getNarrative`, `getMisconceptionCatalog`) are thin `fetch` wrappers against `API_BASE = "http://localhost:8000"` and throw on a non-2xx response so `App` can catch and surface `error`.

`constants.js` exists because the backend deliberately sends the raw `skill_tag` rather than display text — `SKILL_DISPLAY_NAMES` is what `SkillTrailMap` uses to render a skill's name instead of its tag. Misconception copy is different: `Feedback.hint` already arrives from the backend as finished, display-ready text (backed by `content/misconceptions.json` on the backend side), so `FeedbackBanner` renders it directly — there's no client-side hint lookup to keep in sync when a new bug rule is added.

### Start / resume a session

On mount, `App` checks `localStorage` for a cached `session_id`. If one exists, it calls `getSession(id)` to resume; a 404 (e.g. the backend restarted and lost its in-memory session store) clears the cached id and falls back to the start form. With no cached id, `App` renders `StudentIdForm`, whose `onStart(studentId)` callback calls `startSession`, stores the returned `session_id` in `localStorage`, and sets `sessionData`.

### Answering a problem

A student types on `NumberPad` (digits, backspace, submit — no `<input type="number">` anywhere, per `CLAUDE.md`'s constraint that an answer must be computed, not spun to). `NumberPad` also accepts a physical keyboard (digits, Backspace, Enter) and a draggable text cursor on the answer display; pure on-screen tapping stays byte-identical to before, and the first keyboard keystroke or cursor drag switches that answer to standard left-to-right cursor editing until the next problem resets it back to the default right-to-left, column-aware auto-placement. Submitting calls `ProblemCard`'s `onSubmit(answer)`. `App` computes `time_taken_sec` from `problemStartRef` (reset via a `useEffect` keyed on `current_problem.problem_id`, so it resets exactly when a new problem is served, but *not* on a same-problem retry), calls `submitAnswer(sessionId, answer, timeTakenSec)`, and on success:
- updates `sessionData` — re-renders `StatsBar` (xp/streak) and `SkillTrailMap` (node states) with the new values, and `Mascot` (growth stage, from the count of mastered skills)
- sets `feedback` and `justAdvanced` (from `next_action === "advance_skill"`) — renders `FeedbackBanner`, which shows the mastery-moment/boss-battle lines only when `justAdvanced` is true, and drives `reaction` (above)
- fires `getNarrative(sessionId)` fire-and-forget, off the response that already rendered — when it resolves, its fields are merged into `feedback` (guarded on `problem_id` still matching, so a narrative that resolves after the student has already moved to a new problem doesn't get attached to the wrong one)

Because a wrong answer on attempt 1 or 2 keeps the *same* `problem_id` (the retry ladder — see `backend/README.md`), `problemStartRef` intentionally does not reset in that case, and `FeedbackBanner` re-renders inside the same `ProblemCard` rather than a new one.

### Manipulatives and the end of a quest

`ProblemCard` pins the **equation** at the top of the card (`position: sticky`, so the numerals never need scrolling to however tall the manipulative below grows) and renders the manipulative area underneath it. The three manipulatives (`BundlingSticks`, `NumberLine`, `TenFrame` — see the file structure above) are chosen by skill tag, and they are **remediation, not default furniture**:

- Nothing opens on attempt 1 of any problem, at any mastery. The backend withholds the `visual` field until attempt 2, and there is no low-mastery auto-open.
- On a wrong, signal-bearing answer, `bandFromMastery` (`lib/remediation.js`, shared rather than copied per component) decides what the hint comes with: **below 0.4** the manipulative opens pre-seeded from the student's own wrong answer via `lib/arithmetic.js`; **0.4 to 0.7** it is highlighted and one tap away ("Show me the blocks") but stays closed; **above 0.7** the hint stands alone.
- The opt-in toggle ("Show blocks" / "Show frame") is present at every mastery level and on every attempt, and closed by default. `NumberLine` is the exception — it is the remediation for four specific misconceptions rather than a general scaffold, so it only appears inside its own remediation window.
- The blocks show assembled place values and the ten-ones-bundle animation, but no running numeric total: a live tally would put the answer on screen before the student typed it. `lib/sound.js` fires alongside correct answers, a manipulative bundling into a ten, and quest completion. When `next_action === "end_session"`, `App` renders `SessionSummary` instead of `ProblemCard` — skills mastered (reported at the parent-skill level, Addition and Subtraction, with the sub-skills nested beneath), misconceptions repaired (labeled via `getMisconceptionCatalog`), problems solved, elapsed time, and a "Play again" button that clears the cached session.

## Backend contract

This frontend is coupled to `backend/api.py`'s response shapes (`SessionResponse`, `AnswerResponse`, `Feedback`, `SkillProgress`, `GroupProgress`, `NarrativeOut`) and to the skill tags hardcoded in `constants.js`'s `SKILL_DISPLAY_NAMES`. If a new skill is added on the backend, add a matching entry there — an unrecognized `skill_tag` doesn't break anything, `SkillTrailMap` just falls back to rendering the raw tag string. Misconception hint text is not a frontend concern at all: `Feedback.hint` arrives pre-rendered from the backend's `content/misconceptions.json`, so a new bug rule needs no frontend change to display its hint.

## Known limitations

No auth — one student per browser, identified by whatever name is typed into the start form and cached in `localStorage`. Responsive layout covers standard mobile/tablet/laptop viewport reflow only (see `UI_DESIGN.md` at the repo root) — no native-app gestures, device detection, or installable/PWA behavior. Session state lives only in the backend's in-memory store, so restarting the backend process ends every in-progress session.
