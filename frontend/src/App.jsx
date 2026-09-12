import { useEffect, useRef, useState } from "react";
import { getSession, getNarrative, startSession, submitAnswer } from "./api";
import StudentIdForm from "./components/StudentIdForm";
import ProblemCard from "./components/ProblemCard";
import SkillTrailMap from "./components/SkillTrailMap";
import StatsBar from "./components/StatsBar";
import Mascot from "./components/Mascot";
import "./App.css";

const SESSION_STORAGE_KEY = "adaptive-math-tutor:session_id";
const REACTION_DURATION_MS = 1600;

export default function App() {
  const [sessionData, setSessionData] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [justAdvanced, setJustAdvanced] = useState(false);
  const [reaction, setReaction] = useState("idle");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [resuming, setResuming] = useState(true);
  const problemStartRef = useRef(Date.now());

  useEffect(() => {
    const cachedId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!cachedId) {
      setResuming(false);
      return;
    }
    getSession(cachedId)
      .then((data) => setSessionData(data))
      .catch(() => localStorage.removeItem(SESSION_STORAGE_KEY))
      .finally(() => setResuming(false));
  }, []);

  useEffect(() => {
    problemStartRef.current = Date.now();
  }, [sessionData?.current_problem?.problem_id]);

  useEffect(() => {
    if (!feedback) return;
    setReaction(feedback.correct ? "correct" : "incorrect");
    const timer = setTimeout(() => setReaction("idle"), REACTION_DURATION_MS);
    return () => clearTimeout(timer);
  }, [feedback]);

  function handleStart(studentId) {
    setLoading(true);
    setError(null);
    startSession(studentId)
      .then((data) => {
        localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
        setSessionData(data);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  function handleSubmitAnswer(answer) {
    const timeTakenSec = (Date.now() - problemStartRef.current) / 1000;
    setLoading(true);
    setError(null);
    const sessionId = sessionData.session_id;
    submitAnswer(sessionId, answer, timeTakenSec)
      .then((data) => {
        setSessionData(data);
        setFeedback(data.feedback);
        setJustAdvanced(data.next_action === "advance_skill");
        // Off the submit-to-verdict critical path: fire-and-forget, merge in
        // whenever the narrative text resolves (it may already be cached).
        getNarrative(sessionId)
          .then((narrativeData) => {
            setFeedback((prev) =>
              prev && prev.problem_id === data.feedback.problem_id ? { ...prev, ...narrativeData } : prev
            );
          })
          .catch(() => {});
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  if (resuming) {
    return <div className="app-shell">Loading…</div>;
  }

  const masteredCount = sessionData?.skill_progress?.filter((entry) => entry.mastered).length ?? 0;
  const questComplete = sessionData && sessionData.next_action === "end_session";

  return (
    <div className="app-shell">
      <h1>Adaptive Math Tutor</h1>
      {error && <div className="error-banner">{error}</div>}

      {!sessionData ? (
        <StudentIdForm onStart={handleStart} loading={loading} />
      ) : (
        <>
          <StatsBar engagement={sessionData.engagement} />
          <div className="side-panel">
            <Mascot
              masteredCount={masteredCount}
              reaction={reaction}
              frustration={sessionData.engagement.frustration_signal}
            />
            <SkillTrailMap skillProgress={sessionData.skill_progress} />
          </div>
          <div className="main-panel">
            {questComplete ? (
              <div className="problem-card quest-complete">Quest complete! Nice work today.</div>
            ) : (
              sessionData.current_problem && (
                <ProblemCard
                  problem={sessionData.current_problem}
                  onSubmit={handleSubmitAnswer}
                  loading={loading}
                  flashState={reaction === "idle" ? null : reaction}
                  feedback={feedback}
                  justAdvanced={justAdvanced}
                />
              )
            )}
          </div>
        </>
      )}
    </div>
  );
}
