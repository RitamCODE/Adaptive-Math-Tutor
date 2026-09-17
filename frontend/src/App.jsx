import { useEffect, useRef, useState } from "react";
import { getSession, getNarrative, restoreSession, seedSession, startSession, submitAnswer } from "./api";
import StudentIdForm from "./components/StudentIdForm";
import ProblemCard from "./components/ProblemCard";
import SkillTrailMap from "./components/SkillTrailMap";
import StatsBar from "./components/StatsBar";
import Mascot from "./components/Mascot";
import SessionSummary from "./components/SessionSummary";
import { playCorrectTone, playQuestComplete } from "./lib/sound";
import { selectPraise } from "./lib/praise";
import { capNarrative } from "./lib/copy";
import "./App.css";

// Holds { session_id, snapshot } where `snapshot` is the last full
// SessionResponse the server sent us — enough to rehydrate on a plain
// refresh (via GET) or restore a session the backend lost on restart
// (via POST .../restore), without ever caching a correct_answer.
const SESSION_STORAGE_KEY = "adaptive-math-tutor:session";
const REACTION_DURATION_MS = 1600;
// A correct answer's graph turn already advances to the next problem (or
// ends the session) in the same response as the feedback for the one just
// answered — without a display delay, the feedback for a correct answer
// would never get a render frame of its own. These hold the just-answered
// problem (and its praise line) on screen before `displayData` reveals the
// next state.
const ADVANCE_DELAY_MS = 1600;
// The mastery moment does not use a fixed read window at all — its narrative
// (touchpoints 2-4) costs up to three sequential OpenAI calls, so any fixed
// window either flashes past before the text is readable or lingers when the
// student is already done reading. Instead the card is held on screen with a
// "Next" button until the student clicks it themselves; the narrative merges
// into the banner whenever it resolves, or NARRATIVE_WAIT_CAP_MS bounds the
// wait so a slow or dead API degrades to the generic line instead of leaving
// the banner without any narrative at all.
const NARRATIVE_WAIT_CAP_MS = 6000;
const VALID_SEEDS = ["new", "struggling", "fluent", "borrowing"];

/** Resolve to the promise's value, or to null on timeout or failure. Never
 *  rejects, and a late arrival after the cap is ignored rather than rendered
 *  into a window that has already closed. */
function withTimeout(promise, ms) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(null), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      () => {
        clearTimeout(timer);
        resolve(null);
      }
    );
  });
}

function loadCachedSession() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function seedFromUrl() {
  const value = new URLSearchParams(window.location.search).get("seed");
  return VALID_SEEDS.includes(value) ? value : null;
}

function stripSeedFromUrl() {
  const url = new URL(window.location.href);
  url.searchParams.delete("seed");
  window.history.replaceState({}, "", url);
}

export default function App() {
  // `sessionData` is the latest truth from the server. `displayData` is what
  // the UI actually renders — it matches `sessionData` immediately except
  // right after a correct answer, when it intentionally lags behind for
  // ADVANCE_DELAY_MS/MASTERY_ADVANCE_DELAY_MS so the just-answered problem's
  // feedback banner gets a chance to be seen before the next problem (or the
  // end-of-quest screen) replaces it.
  const [sessionData, setSessionData] = useState(null);
  const [displayData, setDisplayData] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [justAdvanced, setJustAdvanced] = useState(false);
  const [reaction, setReaction] = useState("idle");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resuming, setResuming] = useState(true);
  const problemStartRef = useRef(Date.now());
  const sessionStartRef = useRef(null);
  const advanceTimerRef = useRef(null);
  // Holds the next-stage payload (already known as soon as submitAnswer
  // resolves) during a mastery moment, until the student clicks "Next" to
  // move on. Unlike advanceTimerRef this is never driven by a timer.
  const pendingAdvanceRef = useRef(null);
  // Identifies one submit. `problem_id` cannot do this job: a wrong answer
  // keeps the same problem on screen, so every retry of it shares an id, and
  // a slow narrative request issued for one attempt would merge into the
  // next attempt's feedback. This counter is what makes a late response
  // recognisable as stale.
  const turnRef = useRef(0);
  const [seed] = useState(seedFromUrl);

  function hydrate(data) {
    setSessionData(data);
    setDisplayData(data);
  }

  useEffect(() => {
    // A seeded link always starts fresh through the name form below, taking
    // precedence over anything cached — it's meant to replace, not resume.
    if (seed) {
      setResuming(false);
      return;
    }
    const cached = loadCachedSession();
    if (!cached) {
      setResuming(false);
      return;
    }
    sessionStartRef.current = cached.startedAt ?? Date.now();
    getSession(cached.session_id)
      .then((data) => hydrate(data))
      .catch((err) => {
        // Backend restarted and lost this session: rebuild it from our own
        // cached (correct_answer-free) snapshot instead of losing progress.
        if (err.status === 404 && cached.snapshot?.current_problem) {
          const snap = cached.snapshot;
          return restoreSession(cached.session_id, {
            student_id: snap.student_id,
            skill_mastery: snap.skill_mastery,
            misconception_log: snap.misconception_log,
            engagement: snap.engagement,
            problems_completed: snap.problems_completed,
            quest_length: snap.quest_length,
            active_skill: snap.current_problem.skill_tag,
            // Without this, every skill's sustained-mastery run resets to
            // zero on restore even though its raw mastery is preserved, so
            // is_mastered() reports every skill unmastered — the trail map
            // shows a skill as still-in-progress while the problem actually
            // being served (from active_skill, above) can already be a
            // downstream one.
            mastery_run: snap.mastery_run,
            pending_resurface: snap.pending_resurface,
            resurface_progress: snap.resurface_progress,
            resurfaced_skills: snap.resurfaced_skills,
          }).then((data) => hydrate(data));
        }
        throw err;
      })
      .catch((err) => {
        if (err.status === 404) {
          // Nothing left to recover from (no snapshot, or restore itself
          // 404'd) — fall back to a clean start, same as before.
          localStorage.removeItem(SESSION_STORAGE_KEY);
        } else {
          // The backend is unreachable outright: keep the cached session
          // around and say so, rather than silently discarding it.
          setError("Can't reach the server. Check it's running, then refresh.");
        }
      })
      .finally(() => setResuming(false));
  }, [seed]);

  useEffect(() => {
    if (!sessionData) return;
    localStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({
        session_id: sessionData.session_id,
        snapshot: sessionData,
        startedAt: sessionStartRef.current,
      })
    );
  }, [sessionData]);

  useEffect(() => {
    problemStartRef.current = Date.now();
  }, [displayData?.current_problem?.problem_id]);

  useEffect(() => {
    if (!feedback) return;
    setReaction(feedback.correct ? "correct" : "incorrect");
    if (feedback.correct) playCorrectTone();
    const timer = setTimeout(() => setReaction("idle"), REACTION_DURATION_MS);
    return () => clearTimeout(timer);
  }, [feedback]);

  const questComplete = displayData && displayData.next_action === "end_session";

  useEffect(() => {
    if (questComplete) playQuestComplete();
  }, [questComplete]);

  useEffect(() => () => clearTimeout(advanceTimerRef.current), []);

  function handlePlayAgain() {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    sessionStartRef.current = null;
    clearTimeout(advanceTimerRef.current);
    pendingAdvanceRef.current = null;
    setSessionData(null);
    setDisplayData(null);
    setFeedback(null);
    setReaction("idle");
  }

  // Advances past a mastery moment's feedback banner on the student's own
  // click, instead of on a timer — see pendingAdvanceRef above.
  function handleAdvance() {
    const data = pendingAdvanceRef.current;
    if (!data) return;
    pendingAdvanceRef.current = null;
    setDisplayData(data);
    setLoading(false);
  }

  function handleStart(studentId) {
    setLoading(true);
    setError(null);
    const starter = seed ? seedSession(seed, studentId) : startSession(studentId);
    starter
      .then((data) => {
        sessionStartRef.current = Date.now();
        hydrate(data);
        // Once we've actually landed in the seeded state, drop ?seed= so a
        // later plain refresh rehydrates normally instead of re-seeding and
        // discarding whatever progress happened since.
        if (seed) stripSeedFromUrl();
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  function handleSubmitAnswer(answer, usedManipulative) {
    const timeTakenSec = (Date.now() - problemStartRef.current) / 1000;
    const attemptNumber = sessionData.attempt_number;
    const turnId = ++turnRef.current;
    setLoading(true);
    setError(null);
    setReaction("thinking");
    const sessionId = sessionData.session_id;
    submitAnswer(sessionId, answer, timeTakenSec)
      .then((data) => {
        setSessionData(data);
        if (!data.feedback.correct) {
          setFeedback(data.feedback);
          setJustAdvanced(false);
          setDisplayData(data);
          setLoading(false);
          return;
        }

        const praise = selectPraise({
          skillTag: data.feedback.skill_tag,
          mastery: data.skill_mastery[data.feedback.skill_tag],
          attemptNumber,
          timeTakenSec,
          priorAvgTimeSec: data.feedback.prior_avg_time_sec,
          usedManipulative,
        });
        setFeedback({ ...data.feedback, praise });
        const advanced = data.next_action === "advance_skill";
        setJustAdvanced(advanced);
        // Keep displayData (and the just-answered problem's card) on
        // screen for a beat instead of jumping straight to whatever this
        // turn's graph invocation already advanced to server-side.
        clearTimeout(advanceTimerRef.current);

        if (!advanced) {
          // Nothing async is coming: the narrative is only ever rendered on
          // an advance, so a plain correct answer doesn't fetch one at all.
          advanceTimerRef.current = setTimeout(() => {
            setDisplayData(data);
            setLoading(false);
          }, ADVANCE_DELAY_MS);
          return;
        }

        // Mastery moment. The verdict is already on screen — this is off the
        // submit-to-verdict path, so CLAUDE.md's 150ms budget is untouched.
        // The next-stage payload is already known, so the student can click
        // "Next" immediately; the narrative text hot-swaps into the banner
        // whenever it resolves (or the cap expires and the banner's built-in
        // fallback text stands instead).
        pendingAdvanceRef.current = data;
        withTimeout(getNarrative(sessionId), NARRATIVE_WAIT_CAP_MS).then((narrativeData) => {
          if (turnRef.current !== turnId) return;
          const capped = capNarrative(narrativeData);
          if (capped) {
            setFeedback((prev) => (prev ? { ...prev, ...capped } : prev));
          }
        });
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }

  if (resuming) {
    return <div className="app-shell">Loading…</div>;
  }

  const masteredCount = displayData?.skill_progress?.filter((entry) => entry.mastered).length ?? 0;

  return (
    <div className="app-shell">
      <h1>Adaptive Math Tutor</h1>
      {error && <div className="error-banner">{error}</div>}

      {!displayData ? (
        <StudentIdForm onStart={handleStart} loading={loading} />
      ) : (
        <>
          <StatsBar engagement={displayData.engagement} />
          <div className="side-panel">
            <Mascot
              masteredCount={masteredCount}
              reaction={reaction}
              frustration={displayData.engagement.frustration_signal}
            />
            <SkillTrailMap
              skillProgress={displayData.skill_progress}
              groupProgress={displayData.group_progress}
            />
          </div>
          <div className="main-panel">
            {questComplete ? (
              <SessionSummary
                sessionData={displayData}
                elapsedMs={Date.now() - (sessionStartRef.current ?? Date.now())}
                onPlayAgain={handlePlayAgain}
              />
            ) : (
              displayData.current_problem && (
                <ProblemCard
                  problem={displayData.current_problem}
                  onSubmit={handleSubmitAnswer}
                  onAdvance={handleAdvance}
                  loading={loading}
                  flashState={reaction === "idle" ? null : reaction}
                  feedback={feedback}
                  justAdvanced={justAdvanced}
                  skillProgress={displayData.skill_progress}
                />
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}
