export default function StatsBar({ engagement }) {
  return (
    <div className="stats-bar">
      <span>XP: {engagement.xp}</span>
      <span>Streak: {engagement.streak}</span>
      {engagement.frustration_signal && (
        <span className="frustration-note">Take a breath — you've got this.</span>
      )}
    </div>
  );
}
