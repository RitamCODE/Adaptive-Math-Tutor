import { useEffect, useRef, useState } from "react";
import { getSession, startSession, submitAnswer } from "./api";
import StudentIdForm from "./components/StudentIdForm";
import ProblemCard from "./components/ProblemCard";
import FeedbackBanner from "./components/FeedbackBanner";
import SkillMap from "./components/SkillMap";
import StatsBar from "./components/StatsBar";
import "./App.css";

const SESSION_STORAGE_KEY = "adaptive-math-tutor:session_id";

export default function App() {
  const [sessionData, setSessionData] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [justAdvanced, setJustAdvanced] = useState(false);
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
  }, [sessionData?.current_problem?.question, sessionData?.current_problem?.skill_tag]);

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
    submitAnswer(sessionData.session_id, answer, timeTakenSec)
      .then((data) => {
        setSessionData(data);
        setFeedback(data.feedback);
        setJustAdvanced(data.next_action === "advance_skill");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  if (resuming) {
    return <div className="app-shell">Loading…</div>;
  }

  return (
    <div className="app-shell">
      <h1>Adaptive Math Tutor</h1>
      {error && <div className="error-banner">{error}</div>}

      {!sessionData ? (
        <StudentIdForm onStart={handleStart} loading={loading} />
      ) : (
        <>
          <StatsBar engagement={sessionData.engagement} />
          <SkillMap skillProgress={sessionData.skill_progress} />
          {feedback && <FeedbackBanner feedback={feedback} justAdvanced={justAdvanced} />}
          {sessionData.current_problem && (
            <ProblemCard
              problem={sessionData.current_problem}
              onSubmit={handleSubmitAnswer}
              loading={loading}
            />
          )}
        </>
      )}
    </div>
  );
}
