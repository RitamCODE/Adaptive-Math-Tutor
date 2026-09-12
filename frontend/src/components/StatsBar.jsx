export default function StatsBar({ engagement }) {
  const milestone = engagement.streak >= 3;

  return (
    <div className="stats-bar">
      <div className={`stat-chip stat-chip-streak${milestone ? " stat-chip-milestone" : ""}`}>
        <span className="stat-chip-icon" aria-hidden="true">
          🔥
        </span>
        <span>{engagement.streak}</span>
      </div>
      <div className="stat-chip stat-chip-xp">
        <span className="stat-chip-icon" aria-hidden="true">
          ⭐
        </span>
        <span>{engagement.xp} XP</span>
      </div>
      {engagement.frustration_signal && (
        <div className="frustration-pill">Take a breath — you've got this.</div>
      )}
    </div>
  );
}
