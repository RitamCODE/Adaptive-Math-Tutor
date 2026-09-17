import { SKILL_DISPLAY_NAMES } from "../constants";

export default function ResumeSessionPrompt({ snap, onResume, onStartFresh, loading }) {
  const skillLabel = SKILL_DISPLAY_NAMES[snap.current_problem?.skill_tag] ?? snap.current_problem?.skill_tag;

  return (
    <div className="resume-session-prompt">
      <p className="resume-session-prompt-message">
        The server restarted. Continue as <strong>{snap.student_id}</strong>, on{" "}
        <strong>{skillLabel}</strong>?
      </p>
      <div className="resume-session-prompt-stats">
        <div className="stat-chip stat-chip-streak">
          <span className="stat-chip-icon" aria-hidden="true">
            🔥
          </span>
          <span>{snap.engagement.streak}</span>
        </div>
        <div className="stat-chip stat-chip-xp">
          <span className="stat-chip-icon" aria-hidden="true">
            ⭐
          </span>
          <span>{snap.engagement.xp} XP</span>
        </div>
      </div>
      <div className="resume-session-prompt-actions">
        <button type="button" onClick={onResume} disabled={loading}>
          {loading ? "Resuming…" : "Resume"}
        </button>
        <button type="button" className="resume-session-prompt-secondary" onClick={onStartFresh} disabled={loading}>
          Start fresh
        </button>
      </div>
    </div>
  );
}
