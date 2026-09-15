const STAGE_LABELS = ["a seed", "a sprout", "a sapling", "a budding flower", "a bloomed flower"];
const REACTION_LABELS = { idle: "calm", thinking: "thinking it over", correct: "delighted", incorrect: "encouraging" };

export default function Mascot({ masteredCount, reaction, frustration }) {
  const stage = Math.max(0, Math.min(4, masteredCount));
  const label = `Your companion, currently ${STAGE_LABELS[stage]}, feeling ${REACTION_LABELS[reaction] ?? reaction}`;

  return (
    <div
      className={`mascot mascot-stage-${stage} mascot-reaction-${reaction}`}
      role="img"
      aria-label={label}
    >
      <svg className="mascot-svg" viewBox="0 0 120 120">
        {stage >= 4 && <circle className="mascot-halo" cx="60" cy="55" r="52" />}
        {stage >= 3 && <circle className="mascot-glow" cx="60" cy="30" r="22" />}

        {stage >= 1 && <path className="mascot-stem" d="M60 70 L60 40" />}
        {stage >= 1 && (
          <path className="mascot-leaf mascot-leaf-1" d="M60 55 Q40 50 45 35 Q62 40 60 55 Z" />
        )}
        {stage >= 2 && (
          <path className="mascot-leaf mascot-leaf-2" d="M60 50 Q80 45 75 30 Q58 35 60 50 Z" />
        )}

        {stage === 3 && <circle className="mascot-bud" cx="60" cy="32" r="10" />}
        {stage >= 4 && (
          <g className="mascot-bloom">
            <circle className="petal" cx="60" cy="20" r="9" />
            <circle className="petal" cx="48" cy="27" r="9" />
            <circle className="petal" cx="72" cy="27" r="9" />
            <circle className="petal" cx="60" cy="34" r="9" />
            <circle className="petal-center" cx="60" cy="27" r="6" />
          </g>
        )}

        <circle className="mascot-body" cx="60" cy="75" r="32" />

        {stage >= 2 && (
          <>
            <ellipse className="mascot-cheek" cx="42" cy="82" rx="6" ry="4" />
            <ellipse className="mascot-cheek" cx="78" cy="82" rx="6" ry="4" />
          </>
        )}

        <g className="mascot-face">
          {reaction === "correct" ? (
            <>
              <path className="mascot-eye" d="M42 70 Q47 64 52 70" />
              <path className="mascot-eye" d="M68 70 Q73 64 78 70" />
              <path className="mascot-mouth" d="M45 82 Q60 96 75 82" />
            </>
          ) : reaction === "thinking" ? (
            <>
              <circle className="mascot-eye-dot" cx="49" cy="68" r="3" />
              <circle className="mascot-eye-dot" cx="75" cy="68" r="3" />
              <path className="mascot-brow" d="M42 60 Q47 57 53 60" />
              <path className="mascot-brow" d="M71 60 Q77 57 82 60" />
              <path className="mascot-mouth" d="M52 85 Q60 82 68 85" />
            </>
          ) : reaction === "incorrect" ? (
            <>
              <circle className="mascot-eye-dot" cx="47" cy="70" r="3" />
              <circle className="mascot-eye-dot" cx="73" cy="70" r="3" />
              <path className="mascot-brow" d="M41 61 Q46 58 53 61" />
              <path className="mascot-brow" d="M79 61 Q74 58 67 61" />
              <path className="mascot-mouth" d="M48 85 Q60 88 72 85" />
            </>
          ) : (
            <>
              <circle className="mascot-eye-dot" cx="47" cy="70" r="3" />
              <circle className="mascot-eye-dot" cx="73" cy="70" r="3" />
              <path className="mascot-mouth" d="M48 84 Q60 90 72 84" />
            </>
          )}
        </g>

        {reaction === "thinking" && (
          <g className="mascot-think-dots" aria-hidden="true">
            <circle className="think-dot d1" cx="88" cy="52" r="3" />
            <circle className="think-dot d2" cx="97" cy="45" r="2.4" />
            <circle className="think-dot d3" cx="104" cy="37" r="1.8" />
          </g>
        )}

        {reaction === "correct" && (
          <g className="mascot-sparkles">
            <path className="sparkle s1" d="M20 40 L23 46 L29 49 L23 52 L20 58 L17 52 L11 49 L17 46 Z" />
            <path className="sparkle s2" d="M95 55 L97 60 L102 62 L97 64 L95 69 L93 64 L88 62 L93 60 Z" />
            <path className="sparkle s3" d="M100 30 L102 34 L106 36 L102 38 L100 42 L98 38 L94 36 L98 34 Z" />
          </g>
        )}
      </svg>

      {frustration && reaction !== "correct" && (
        <div className="mascot-thought-bubble" aria-hidden="true">
          💭
        </div>
      )}
    </div>
  );
}
