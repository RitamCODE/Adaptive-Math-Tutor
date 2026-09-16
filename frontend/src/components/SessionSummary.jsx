import { useEffect, useState } from "react";
import { getMisconceptionCatalog } from "../api";
import { SKILL_DISPLAY_NAMES } from "../constants";

function formatDuration(ms) {
  const totalSec = Math.max(0, Math.round(ms / 1000));
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  if (min === 0) return `${sec} sec`;
  return `${min} min ${sec} sec`;
}

function dedupeByBugType(entries) {
  const seen = new Map();
  for (const entry of entries) {
    if (!seen.has(entry.bug_type)) seen.set(entry.bug_type, entry);
  }
  return [...seen.values()];
}

export default function SessionSummary({ sessionData, elapsedMs, onPlayAgain }) {
  const [catalog, setCatalog] = useState(null);

  useEffect(() => {
    getMisconceptionCatalog()
      .then(setCatalog)
      .catch(() => setCatalog({}));
  }, []);

  const groups = sessionData.group_progress ?? [];
  const masteredSkills = sessionData.skill_progress.filter((entry) => entry.mastered);
  const masteredTags = new Set(masteredSkills.map((entry) => entry.skill));

  const repaired = dedupeByBugType(
    sessionData.misconception_log.filter((entry) => masteredTags.has(entry.skill))
  );
  const stillPracticing = dedupeByBugType(
    sessionData.misconception_log.filter((entry) => !masteredTags.has(entry.skill))
  );

  function labelFor(bugType) {
    return catalog?.[bugType]?.hint || bugType;
  }

  return (
    <div className="problem-card session-summary">
      <h2 className="session-summary-title">Quest complete!</h2>

      <div className="session-summary-stats">
        <div className="session-summary-stat">
          <span className="session-summary-stat-value">{sessionData.problems_completed}</span>
          <span className="session-summary-stat-label">problems solved</span>
        </div>
        <div className="session-summary-stat">
          <span className="session-summary-stat-value">{formatDuration(elapsedMs)}</span>
          <span className="session-summary-stat-label">time played</span>
        </div>
        <div className="session-summary-stat">
          <span className="session-summary-stat-value">{sessionData.engagement.xp}</span>
          <span className="session-summary-stat-label">XP earned</span>
        </div>
      </div>

      <div className="session-summary-section">
        <h3>Skills mastered</h3>
        {masteredSkills.length > 0 ? (
          <ul className="session-summary-list">
            {/* Reported at the parent level — Addition, Subtraction — with the
                sub-skills beneath, so the student sees the two big things they
                were working toward rather than four tags. A parent is only
                listed as complete when both of its sub-skills are. */}
            {groups.map((group) => {
              const done = masteredSkills.filter((entry) => entry.group === group.group);
              if (done.length === 0) return null;
              return (
                <li key={group.group}>
                  <span className="session-summary-group">
                    {group.display_name}
                    {group.mastered ? " — mastered" : ` — ${group.mastered_count} of ${group.total}`}
                  </span>
                  <ul className="session-summary-sublist">
                    {done.map((entry) => (
                      <li key={entry.skill}>{SKILL_DISPLAY_NAMES[entry.skill] || entry.skill}</li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="session-summary-empty">Still building toward the first mastered skill.</p>
        )}
      </div>

      <div className="session-summary-section">
        <h3>Misconceptions repaired</h3>
        {repaired.length > 0 ? (
          <ul className="session-summary-list">
            {repaired.map((entry) => (
              <li key={entry.bug_type}>{labelFor(entry.bug_type)}</li>
            ))}
          </ul>
        ) : (
          <p className="session-summary-empty">No misconceptions logged on mastered skills this quest.</p>
        )}
      </div>

      {stillPracticing.length > 0 && (
        <div className="session-summary-section session-summary-section-muted">
          <h3>Still practicing</h3>
          <ul className="session-summary-list">
            {stillPracticing.map((entry) => (
              <li key={entry.bug_type}>{labelFor(entry.bug_type)}</li>
            ))}
          </ul>
        </div>
      )}

      <button type="button" className="session-summary-play-again" onClick={onPlayAgain}>
        Play again
      </button>
    </div>
  );
}
