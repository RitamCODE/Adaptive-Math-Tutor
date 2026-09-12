import { SKILL_DISPLAY_NAMES } from "../constants";

function skillSymbol(skillTag) {
  return skillTag.startsWith("addition") ? "+" : "−";
}

export default function SkillTrailMap({ skillProgress }) {
  return (
    <div className="skill-trail">
      {skillProgress.map((entry) => {
        const state = entry.mastered ? "mastered" : entry.unlocked ? "current" : "locked";
        return (
          <div className="skill-node-row" key={entry.skill}>
            <div className={`skill-node ${state}`}>
              <div
                className="skill-node-ring"
                style={{ "--mastery": Math.min(entry.mastery, 1) }}
              >
                <div className="skill-node-badge">
                  <span className="skill-node-symbol" aria-hidden="true">
                    {skillSymbol(entry.skill)}
                  </span>
                  {state === "locked" && (
                    <span className="skill-node-flag" aria-hidden="true">
                      🔒
                    </span>
                  )}
                  {state === "mastered" && (
                    <span className="skill-node-flag" aria-hidden="true">
                      ✓
                    </span>
                  )}
                </div>
              </div>
              <div className="skill-node-label">
                {SKILL_DISPLAY_NAMES[entry.skill] || entry.skill}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
