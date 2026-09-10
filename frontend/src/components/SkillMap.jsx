import { SKILL_DISPLAY_NAMES } from "../constants";

export default function SkillMap({ skillProgress }) {
  return (
    <div className="skill-map">
      {skillProgress.map((entry) => (
        <div
          key={entry.skill}
          className={
            "skill-card" +
            (entry.mastered ? " skill-mastered" : "") +
            (!entry.unlocked ? " skill-locked" : "")
          }
        >
          <div className="skill-name">
            {SKILL_DISPLAY_NAMES[entry.skill] || entry.skill}
            {entry.mastered && " ✓"}
            {!entry.unlocked && " 🔒"}
          </div>
          <div className="skill-bar-track">
            <div
              className="skill-bar-fill"
              style={{ width: `${Math.min(entry.mastery, 1) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
