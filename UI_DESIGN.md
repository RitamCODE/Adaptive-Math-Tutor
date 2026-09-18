# UI Design — AdaptMATH

Planning doc only. No component or CSS files are touched by this doc — it exists so the
design direction can be reviewed before any frontend implementation begins, per
CLAUDE.md's constraint that frontend polish stay within CSS/layout/existing libraries.

## 1. Current state summary

The frontend (`frontend/src/`) is a minimal Vite + React app: `App.jsx` owns all session
state and renders `StatsBar` + `SkillMap`, plus `FeedbackBanner` and `ProblemCard`
conditionally. Styling is a single flat `App.css`, flexbox-only, no CSS variables, no
animations, no keyframes, no transitions anywhere in the codebase. The stack is bare
React 19 + Vite (confirmed via `package.json`) — no router, no state-management library,
no CSS framework, no animation/icon library. Anything beyond CSS, inline SVG, and Unicode
glyphs is a new dependency and requires sign-off per CLAUDE.md.

Layout today is fixed-width, not responsive: `.app-shell` is hardcoded to
`max-width: 480px`, there are no CSS media queries anywhere in `App.css`, and no
`clamp()`/fluid sizing — the same narrow single column renders identically whether the
viewport is a phone or a 27" monitor. CLAUDE.md previously listed mobile-responsive
polish as a non-goal; that's been revised (see below) to bring mobile, tablet, and
laptop support into scope for this redesign.

The backend (`backend/api.py`) already returns everything the redesign below needs,
without any backend change: `skill_progress` (`skill`, `mastery`, `unlocked`, `mastered`
per skill), `engagement` (`xp`, `streak`, `frustration_signal`), and per-answer
`feedback` (`correct`, `bug_type`, `correct_answer`, plus the four LLM narratives).
`skill_graph.py` is a strict linear 4-skill chain
(`addition_no_carry → addition_carry → subtraction_no_borrow → subtraction_borrow`), so
at most one skill is ever "unlocked but not mastered" at a time.

| Component | Renders today | Available but unused |
|---|---|---|
| `App.jsx` | Orchestrates session state; renders `StatsBar`, `SkillMap`, `FeedbackBanner`, `ProblemCard` | `student_id` is received but never displayed (no "Hi, {name}" greeting) |
| `StudentIdForm.jsx` | Name input + Start button | — (pre-session, no session data yet) |
| `ProblemCard.jsx` | `current_problem.question`, `.flavor_text`, numeric input, Submit button | `current_problem.skill_tag`, `.difficulty` — both present in the prop object, never rendered |
| `FeedbackBanner.jsx` | `feedback.correct`, `.reward_narrative`, `.mastery_narrative`, `.boss_battle_narrative`, `.bug_type` (via `BUG_TYPE_HINTS`), `.correct_answer` | `feedback.skill_tag` — present, unused |
| `SkillMap.jsx` | A **vertical list** of full-width `.skill-card` divs: name + ✓/🔒 suffix + thin blue progress bar | All of `skill_progress[]`'s fields are already consumed (`skill`, `mastery`, `unlocked`, `mastered`) — nothing missing data-wise, but it's a list, not a map, and shows no numeric mastery %, no sense of a path/journey |
| `StatsBar.jsx` | Plain bold text `XP: {n}` / `Streak: {n}`, amber frustration note when `frustration_signal` is true | All of `EngagementState` already consumed — nothing missing data-wise, but no icons, no persistence emphasis (it's already at the top, but visually forgettable), no animation on increment |

No component currently animates, reacts, or visually differentiates the *degree* of
mastery beyond a bar-fill percentage — every skill's fill uses the same blue regardless
of how close it is to mastered, and there is no character/companion element at all.

## 2. Design direction

**A companion mascot that grows with the student.** A new `Mascot.jsx`, built entirely
from inline SVG shapes and CSS (no image assets), that does two things at once:

- **Reflects overall mastery progress** via 5 cumulative growth stages, keyed to the
  count of `mastered: true` entries in `skill_progress` (0 through 4, since there are 4
  skills total): *Seed* (0 mastered) → *Sprout* (1, first leaf appears) → *Sapling* (2,
  second leaf + blush) → *Budding* (3, flower bud + soft glow) → *Bloom* (4/4, full
  flower + gentle halo loop). Each stage only adds SVG layers on top of the previous
  stage's shape (CSS class toggles visibility) — it's one mascot, not five separate
  drawings.
- **Reacts to correct/incorrect answers** via a transient reaction layer composed on top
  of whatever growth stage is current: idle (gentle bob loop), correct (bounce + small
  sparkle burst + happy eyes/mouth), incorrect (soft head-tilt wobble + "hmm" brow —
  never shrinks, never turns red, stays visibly encouraging). Reaction fires off
  `feedback.correct` and reverts to idle before/as the next problem loads.

**The skill map as an actual map.** `SkillMap.jsx` becomes `SkillTrailMap`: still a
vertical arrangement (the app's existing 480px column width suits a path running down
the page more than a wide horizontal board), but restyled as a winding trail — circular
node badges alternating left/right offset, connected by a CSS-drawn line, instead of
stacked full-width cards. Because the skill graph is a strict linear chain, there are
only ever three node states to design for: **locked**, **current** (the one
unlocked-but-not-yet-mastered skill), and **mastered**. The current node gets a
`conic-gradient`-drawn mastery arc around its badge showing raw progress toward 0.8.

**Warm, high-contrast palette.** Replace the ad-hoc hardcoded hex values with three CSS
custom-property accents (see section 4) on a warm cream background with warm dark-brown
ink for contrast — no gray/blue dashboard feel. Labels move to sentence case throughout
(no ALL CAPS, no Title Case), base type size increases, and spacing units scale up from
the current tight rem values to feel roomier and more game-like.

**Persistent streak/XP.** `StatsBar` becomes a `position: sticky; top: 0` pill-chip bar
so it's always visible while scrolling the trail map, not just present-but-easy-to-miss
at the top of the page. A 🔥 streak chip (coral) and ⭐ XP chip (gold) replace the plain
bold text (Unicode glyphs, consistent with the ✓/🔒 already used in the current
`SkillMap`). The streak chip gets a small gold pulse at a milestone (e.g. streak ≥ 3).
The frustration note becomes a small pill under the bar rather than inline text.

**Non-punishing feedback animation.** On submit: correct answers get a scale-pulse on
the problem card plus a short CSS-keyframe confetti burst (6–8 small divs in the three
accent colors, no library) alongside the mascot's correct-reaction. Incorrect answers
get a low-amplitude, brief horizontal shake (2–3 gentle oscillations — never a jarring
snap) alongside the mascot's incorrect-reaction and the existing `BUG_TYPE_HINTS` hint
text. Incorrect never uses red, never dims or shrinks the card, and always pairs with a
next step — matching the "non-punishing" requirement.

**Responsive layout across mobile, tablet, and laptop.** CSS-only (media queries,
relative units, `clamp()`), no separate mobile build:

- *Mobile* (up to ~599px) — today's single-column layout is effectively the mobile
  baseline: `.app-shell` stays a centered single column, sticky stats bar, full-width
  problem card, trail map stacked vertically. Tap targets (Submit button, numeric input,
  trail nodes) sized to at least 44×44px for touchscreen use.
- *Tablet* (~600–1023px) — same single-column structure, but `.app-shell`'s max-width
  and base spacing/type scale up fluidly via `clamp()` rather than jumping at a hard
  breakpoint, so the layout doesn't look like a stretched phone view.
- *Laptop/desktop* (≥1024px) — one real breakpoint switches `.app-shell` from a single
  flex column to a two-region CSS Grid: trail map + mascot in a left region, sticky
  stats bar + problem card + feedback banner in a right region, so the extra horizontal
  space is used rather than leaving a long, narrow scrolling column centered on a wide
  screen.
- The trail map's alternating left/right node offsets are expressed as percentages of
  the container width (not fixed px), so the zigzag scales instead of breaking at
  narrow widths. Font sizes and the mascot's size use `clamp(min, fluid, max)` so there's
  one smooth scale across the whole range instead of many discrete breakpoints.

## 3. Component breakdown

| Component | SessionState / API fields consumed | Visual states |
|---|---|---|
| `App.jsx` (orchestrator) | `session_id`, `current_problem`, `engagement`, `skill_progress`, `feedback`, `next_action` (+ derives `masteredCount` and a transient `lastCorrect` flag) | loading / resuming / error / active session |
| `StudentIdForm.jsx` | none (pre-session) | idle / submitting |
| `ProblemCard.jsx` | `current_problem.question`, `.flavor_text` | idle / submitting-disabled / correct-flash (scale-pulse + confetti host) / incorrect-shake |
| `FeedbackBanner.jsx` | `feedback.correct`, `.bug_type`, `.correct_answer`, `.reward_narrative`, `.mastery_narrative`, `.boss_battle_narrative` | correct / incorrect / correct + advanced (mastery moment, coincides with a mascot stage-up) |
| `SkillTrailMap` (renamed from `SkillMap.jsx`) | `skill_progress[].skill`, `.mastery`, `.unlocked`, `.mastered` | per node: locked / current (pulsing ring + mastery arc) / mastered (settled, sparkle) |
| `StatsBar.jsx` | `engagement.xp`, `.streak`, `.frustration_signal` | normal / streak-milestone-glow / frustration-note-shown |
| `Mascot.jsx` (new) | derived `masteredCount` (from `skill_progress`), `feedback.correct` (transient), `engagement.frustration_signal` | growth stage 0–4 × reaction {idle, correct, incorrect}, composed as (stage class) + (reaction class) — not 15 separate assets, just layered CSS |
| Feedback-flash behavior (logic inside `ProblemCard`/`App`, not necessarily a separate file) | `feedback.correct` | none / correct-burst / incorrect-shake |

## 4. Color and state mapping

Three accents total, plus warm neutrals for background/text/locked state.

- Cream background `#FBF4E9` · warm-brown ink `#3A2B22` · warm neutral gray `#C9C0B4` (locked/disabled)
- **Coral** `#FF6F59` — current/in-progress/energy
- **Gold** `#F5A623` — mastery/XP/reward
- **Teal** `#2FB6A3` — correct/success (used sparingly)

| Condition | Visual treatment |
|---|---|
| Skill locked | Warm gray `#C9C0B4` fill, padlock glyph, ~0.6 opacity, static (no animation) |
| Skill unlocked & in progress (current) | Coral `#FF6F59` ring, pulsing glow, `conic-gradient` mastery arc (0 → progress toward 0.8) |
| Skill mastered (≥ 0.8) | Gold `#F5A623` fill, checkmark glyph, idle sparkle, settled (pulse stops) |
| Answer correct | Teal `#2FB6A3` flash on feedback banner, confetti burst (coral + gold + teal dots), mascot correct-reaction |
| Answer incorrect | Muted terracotta tint (never harsh red), gentle shake, mascot incorrect-reaction, hint shown |
| Frustration signal true | Gold-toned encouragement pill, mascot optional thought-bubble cue |
| Streak ≥ milestone (e.g. 3) | Coral glow pulse on the streak chip |
| Mascot growth stage (0–4) | Tied to count of mastered skills in `skill_progress`; cumulative features (leaf → leaves → bud → bloom), no new color per stage — stage is shape/feature-driven, not color-driven |

## 5. Non-goals

Everything below is explicitly out of scope for this redesign, per CLAUDE.md's hard
constraints (§4: CSS/layout/existing-libraries only) and existing non-goals:

- **No new npm dependencies** — no animation library (Framer Motion, GSAP), no icon
  library, no charting library. All motion is CSS `@keyframes`/`transition`, all node
  progress rings are CSS `conic-gradient`.
- **No image/asset pipeline** — the mascot, trail nodes, and confetti are all inline
  SVG/CSS shapes or Unicode glyphs (🔥 ⭐ ✓ 🔒), never raster or vector image files.
- **No sound effects.**
- **No backend/API changes** — `skill_progress`, `engagement`, and `feedback` already
  carry everything this design needs; this is a frontend-only pass.
- **No new LLM touchpoints** — this is a visual/CSS layer over the four narrative
  fields that already exist; the four-touchpoint restriction is untouched.
- **No device-specific native behavior** — responsive CSS reflow across mobile/tablet/
  laptop viewports is in scope (see section 2), but no native-app gestures, no device
  detection/user-agent branching, no orientation-specific redesign beyond standard
  responsive reflow, no PWA/installable-app work.
- **No persistence of mascot growth stage or animation state** beyond the current
  session (matches the existing "no persistence beyond session" non-goal).
- **No routing or multi-page map view** — the trail map stays inside the existing
  single-page `App.jsx` tree.
- **No pan/zoom/drag interactivity** on the map — static layout, CSS-only hover/focus
  states at most.

If any of the above turns out to be necessary to hit the design direction in section 2,
stop and ask before adding it, per CLAUDE.md.
