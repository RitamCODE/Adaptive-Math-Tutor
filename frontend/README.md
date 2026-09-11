# Adaptive Math Tutor — Frontend

A minimal browser UI for the adaptive math tutor: problem display, answer input, skill map, and XP/streak tracking, driven entirely by the FastAPI backend in `../backend`.

## Stack

Vite + plain React. No router, no state-management library, no CSS framework. Per the project's "frontend stays minimal" constraint (see the repo root `CLAUDE.md`), the time budget goes into the backend's adaptive engine, not UI infrastructure — there's exactly one page and one piece of client state, so none of that machinery earns its keep here.

## Running it

```bash
npm install
npm run dev
```

Serves on `http://localhost:5173`. This app **requires the backend running separately** at `http://localhost:8000`:

```bash
# from the repo root
uv run uvicorn backend.api:app --reload --port 8000
```

`src/api.js` hardcodes that base URL, and the backend's CORS allowlist (`backend/api.py`) only permits `http://localhost:5173` / `127.0.0.1:5173` — if you serve the frontend on a different port, both sides need updating.

## File structure

```
src/
  main.jsx              mounts <App /> into #root
  App.jsx                the single state owner — see "How it fits together" below
  api.js                  fetch wrappers for the three backend endpoints
  constants.js            skill display names + bug-type hint text (presentation only)
  App.css                 all styling; no CSS framework
  components/
    StudentIdForm.jsx      start-session form
    ProblemCard.jsx         current problem + numeric answer input
    FeedbackBanner.jsx      correct/incorrect feedback + misconception hint
    SkillMap.jsx            per-skill mastery bars, locked/mastered state
    StatsBar.jsx            XP, streak, frustration note
```

## How it fits together

`App.jsx` is the only component that holds state or talks to `api.js`. Everything under `components/` is presentational: it receives data as props and reports user actions through callback props (`onStart`, `onSubmit`). There's no context provider and no global store — data flows down as props, actions flow up as callbacks, and `App` is the single place that reconciles a callback with a new `fetch` call and a state update.

`App` holds:
- `sessionData` — the last `SessionResponse`/`AnswerResponse` from the backend (current problem, engagement, skill progress, session id)
- `feedback` — the `Feedback` object from the most recent answer (`null` before the first answer)
- `loading` / `error` — request status
- `problemStartRef` — a timestamp ref reset whenever a new problem appears, used to measure `time_taken_sec`

`api.js` is the only module that calls the backend. Its three functions (`startSession`, `getSession`, `submitAnswer`) are thin `fetch` wrappers against `API_BASE = "http://localhost:8000"` and throw on a non-2xx response so `App` can catch and surface `error`.

`constants.js` exists because the backend deliberately only sends raw tags (`skill_tag`, `bug_type`), not display text — `SKILL_DISPLAY_NAMES` and `BUG_TYPE_HINTS` translate those tags into what `SkillMap` and `FeedbackBanner` actually render.

### Start / resume a session

On mount, `App` checks `localStorage` for a cached `session_id`. If one exists, it calls `getSession(id)` to resume; a 404 (e.g. the backend restarted and lost its in-memory session store) clears the cached id and falls back to the start form. With no cached id, `App` renders `StudentIdForm`, whose `onStart(studentId)` callback calls `startSession`, stores the returned `session_id` in `localStorage`, and sets `sessionData`.

### Answering a problem

`ProblemCard` collects a numeric answer and calls `onSubmit(answer)`. `App` computes `time_taken_sec` from `problemStartRef` (reset via a `useEffect` keyed on the current problem's `question` + `skill_tag`, so it resets exactly when a new problem is served — including after a wrong answer, an advance, or a repeat), calls `submitAnswer(sessionId, answer, timeTakenSec)`, and on success:
- updates `sessionData` — re-renders `StatsBar` (xp/streak) and `SkillMap` (mastery bars, locked/mastered state) with the new values
- sets `feedback` — renders `FeedbackBanner`, which shows a mastery-moment message when the response's `next_action` is `"advance_skill"`

## Backend contract

This frontend is coupled to `backend/api.py`'s response shapes (`SessionResponse`, `AnswerResponse`, `Feedback`, `SkillProgress`) and to the specific skill and bug-type tags currently hardcoded in `constants.js`. If a new skill or misconception rule is added on the backend, add a matching entry there — an unrecognized tag doesn't break anything, it just falls back to the raw tag string (`SkillMap`) or a generic hint (`FeedbackBanner`).

## Known limitations

No auth — one student per browser, identified by whatever name is typed into the start form and cached in `localStorage`. No mobile/responsive layout work. Session state lives only in the backend's in-memory store, so restarting the backend process ends every in-progress session.
