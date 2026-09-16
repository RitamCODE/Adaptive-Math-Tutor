import { SKILL_DISPLAY_NAMES } from "../constants";

function skillSymbol(skillTag) {
  return skillTag.startsWith("addition") ? "+" : "−";
}

function SkillNode({ entry }) {
  const state = entry.mastered ? "mastered" : entry.unlocked ? "current" : "locked";
  return (
    <div className="skill-node-row">
      <div className={`skill-node ${state}`}>
        <div className="skill-node-ring" style={{ "--mastery": Math.min(entry.mastery, 1) }}>
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
        <div className="skill-node-label">{SKILL_DISPLAY_NAMES[entry.skill] || entry.skill}</div>
      </div>
    </div>
  );
}

/**
 * The quest map, grouped by parent skill.
 *
 * The four skills are two parent skills of two sub-skills each. Each
 * sub-skill keeps its own mastery and its own node here; the parent is
 * mastered only once both of its sub-skills are, which is what the header's
 * "n of 2" and its check report. `groupProgress` comes straight from the
 * backend, which derives both it and each node's `mastered` flag from the
 * same gate the router uses — so the map can't disagree with the engine.
 */
export default function SkillTrailMap({ skillProgress, groupProgress }) {
  if (!groupProgress?.length) {
    return (
      <div className="skill-trail">
        {skillProgress.map((entry) => (
          <SkillNode key={entry.skill} entry={entry} />
        ))}
      </div>
    );
  }

  return (
    <div className="skill-trail">
      {groupProgress.map((group) => {
        // Keep the DAG's own ordering rather than the group's listing order.
        const members = skillProgress.filter((entry) => entry.group === group.group);
        return (
          <div className="skill-group" key={group.group}>
            <div className={`skill-group-header${group.mastered ? " mastered" : ""}`}>
              <span className="skill-group-name">{group.display_name}</span>
              <span className="skill-group-count">
                {group.mastered ? "✓ " : ""}
                {group.mastered_count} of {group.total}
              </span>
            </div>
            {members.map((entry) => (
              <SkillNode key={entry.skill} entry={entry} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
