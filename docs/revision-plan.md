# AdaptMATH: revision plan

Target: Nerdy AI Hackathon submission, Sep 18. Seven days from Sep 11.

---

## The core diagnosis

You do not have an intelligence problem. You have a **surfacing problem**.

The BKT mastery model, the bug rules, the curriculum graph: all of that exists in the backend and none of it reaches the child's eyes. What reaches the child is a red banner that says "the answer was 8" and a new problem. From the outside, the app is indistinguishable from a random quiz generator with a praise string attached.

Every item below is about moving existing intelligence onto the screen, plus fixing four real bugs. Almost nothing here requires new modeling work.

---

## Part 1: Bugs to fix first (Day 1, non-negotiable)

### 1.1 Feedback is detached from its problem

Your screenshot shows "the answer was 8" above the problem `8 - 8`. The 8 belongs to the *previous* problem (9 - 1). The feedback banner is global and the problem pane re-rendered underneath it.

**Fix:** feedback carries `problem_id`. The frontend renders feedback *inside the problem card it belongs to*, never in a floating banner, and clears it when `problem_id` changes. No feedback can ever be visible next to a different problem.

### 1.2 There is no retry loop

Right now: wrong answer → reveal correct answer → advance. That single behaviour destroys the entire pedagogical premise of the app. A child who never gets a second attempt never repairs a misconception, and your diagnosis engine has no purpose.

**Fix: three-attempt ladder on the same problem.**

| Attempt | Response | Answer revealed? |
|---|---|---|
| 1 wrong | One-line targeted hint from the bug rule | No |
| 2 wrong | Manipulative opens, pre-loaded with *their* wrong answer, showing the error | No |
| 3 wrong | Animated worked solution, then a gentler problem on the prerequisite skill | Yes |

`SessionState` additions: `attempt_number`, `attempt_history: [answer, bug_id]`, `current_problem` persists across turns. This is the change that makes the graph matter.

### 1.3 The session never ends

**Fix:** a session is a **quest** with a defined shape:

- 8 to 12 problems, or
- 2 skills advanced to mastery threshold, or
- fatigue stop: 4 consecutive wrong answers, or 3 unresolved problems

whichever comes first, ending in a **boss battle** (3 synthesis problems on the skill just mastered) and then a **hard stop** on a summary screen. No auto-restart. A "play again" button only.

### 1.4 Latency on the correctness verdict

An LLM call sits on the critical path between "child presses submit" and "child sees anything." For K-5 that is fatal, and it is also unnecessary: grading is integer comparison.

**Fix, in priority order:**

1. **Split the response.** The verdict, the bug diagnosis, and the templated hint are all deterministic and return in under 100 ms. Ship that immediately.
2. **Prefetch narrative.** While the child is typing an answer, generate the next problem's flavor text in the background. By the time they submit, it is cached.
3. **Templates for the common path.** Wrong-answer hints are hand-written per bug rule, not generated. They need to be precise and age-appropriate, which a template does better than a model anyway.
4. **LLM only for rare, high-value moments:** mastery narrative, boss-battle framing, end-of-session summary. These can take 800 ms because they land on a screen where the child is already celebrating, not waiting.

Target: submit-to-feedback under 150 ms, always.

---

## Part 2: Feedback that actually teaches

### 2.1 The current copy is wrong for the audience

> "Amazing job mastering addition without carrying! You did it on your first try, showing that you've really grasped how to combine numbers correctly without needing to regroup. Keep up the great work!"

A seven-year-old reads roughly 60 to 80 words per minute. That is a 10-second read for a reward they already received. They will skip it, and skipping the reward text trains them to skip all text, including the hints that matter.

**Hard caps, enforced in code by truncation, not just in the prompt:**

| Moment | Cap | Example |
|---|---|---|
| Correct | 4 words, or none | "Nice!" plus animation |
| Streak | 6 words | "Three in a row!" |
| Wrong, attempt 1 | 12 words | "Check the ones column. What is 6 + 4?" |
| Mastery moment | 20 words | the one place a real sentence earns its space |

The celebration should be **motion, sound, and a number going up**, not prose. XP flying into a bar, the mascot reacting, the skill node on the map lighting up. That is what a child registers as a reward.

**Praise speed and effort, but not interchangeably.** Speed praise is legitimate in exactly one context: a skill the child has already mastered, where automaticity *is* the learning objective. Fast recall of number facts is a real K-5 goal and worth celebrating. Speed praise on a skill they are still acquiring is where it does damage, because it teaches that fast equals smart, and the next slow problem becomes evidence they are not. Gate it on the data you already have:

| Condition | Praise |
|---|---|
| Mastery > 0.7, correct, fast | Speed. "Lightning fast!" |
| Correct on attempt 1, still learning | The skill. "You nailed the carry." |
| Correct after 2 or 3 attempts | Effort. "You stuck with it." |
| Correct after using the blocks | Strategy. "Good call using the blocks." |

You have `mastery`, `time_taken`, and `attempt_count` in state already, so this is a four-branch lookup with no LLM call. It also means the praise line is *evidence* the engine knows what happened, which a generic "great job" never is.

### 2.2 Wrong answers must name the error

Your example is exactly right. For `86 + 94`, a child who writes `1017` did not "get it wrong." They did two correct single-digit additions and concatenated them. They are one concept away from correct, and the app should say so.

**Response shape for every wrong answer:**

```json
{
  "problem_id": "p_1041",
  "verdict": "incorrect",
  "bug_id": "ADD_CONCAT_NO_CARRY",
  "hint": "You added each column right! But 6 + 4 is 10, and 10 ones become 1 ten.",
  "visual": { "type": "base10_blocks", "highlight": "ones_column_overflow" },
  "attempts_remaining": 2,
  "reveal_answer": false
}
```

The `hint` is written once per bug rule by hand. The `visual` payload is what makes attempt 2 work.

### 2.3 Digit reversal deserves its own rule

You raised dyslexia specifically. Add a detector that fires when the submitted answer is the digit-reversal of the correct one (student writes 51, answer is 15). That is not an arithmetic error and should never be treated as one.

Hint: "You have the right digits! Check their order." No penalty to the mastery score, since the underlying skill is intact.

This is cheap to implement and it is a genuinely good line in your demo video.

---

## Part 3: The misconception catalog

You asked for a single file listing everything a student can get wrong. Build it as **`misconceptions.yaml`**, loaded at startup, one entry per bug. Data, not code, so you can add rules without touching the engine.

```yaml
- id: ADD_CONCAT_NO_CARRY
  skill: add_2digit_carry
  detect: column_concatenation
  hint: "You added each column right! But 6 + 4 is 10, and 10 ones become 1 ten."
  visual: base10_blocks/ones_overflow
  severity: procedural
```

### Starter catalog

**Addition**

| ID | What the child did | Example |
|---|---|---|
| `ADD_CONCAT_NO_CARRY` | Wrote both column sums side by side | 86 + 94 → 1017 |
| `ADD_CARRY_DROPPED` | Kept the ones digit, ignored the carry | 86 + 94 → 170 |
| `ADD_CARRY_WRONG_COLUMN` | Carried into the ones instead of the tens | 86 + 94 → 181 |
| `ADD_OFF_BY_ONE` | Counting-on error | 8 + 5 → 12 |
| `ADD_USED_SUBTRACTION` | Operator misread | 8 + 5 → 3 |

**Subtraction**

| ID | What the child did | Example |
|---|---|---|
| `SUB_SMALLER_FROM_LARGER` | Subtracted the smaller digit from the larger regardless of position | 42 - 17 → 35 |
| `SUB_BORROW_NO_DECREMENT` | Borrowed but did not reduce the tens | 42 - 17 → 35 |
| `SUB_ZERO_MINUS_N` | Treated 0 - N as N | 40 - 7 → 47 |
| `SUB_BORROW_ACROSS_ZERO` | Failed on the zero column | 305 - 8 → 307 |
| `SUB_REVERSED_OPERANDS` | Computed the problem backwards | 3 - 8 → 5 |

**Cross-cutting**

| ID | Notes |
|---|---|
| `DIGIT_REVERSAL` | Right digits, wrong order. No mastery penalty. |
| `PLACE_VALUE_CONFUSION` | Answer off by an exact power of ten |
| `OFF_BY_TEN` | Carry or borrow counted as 1 instead of 10 |
| `NO_RESPONSE` | Timeout or blank. Not a knowledge signal. Do not update BKT, do not consume an attempt. |
| `RAPID_GUESS` | Answer submitted under ~2 seconds with no working. Not a knowledge signal. Do not update BKT. |
| `UNCLASSIFIED` | Catch-all |

Two of these are **non-signals**, and treating them as wrong answers will quietly poison the mastery model. A child mashing submit three times in four seconds is not demonstrating a misconception, and if BKT reads that as evidence of non-mastery the curriculum will demote them for boredom. On `RAPID_GUESS`, hold the problem, do not count the attempt, and have the mascot prompt them to try the blocks instead.

### The unclassified case matters

When no rule fires, **never fall back to "the answer was X."** Fall back to a procedural prompt:

> "Let's redo this one column at a time. Start with the ones."

and open the manipulative. A generic procedural nudge is still teaching. Revealing the answer is not.

Log every `UNCLASSIFIED` event with the problem and the submitted answer. That log becomes your "what's next" slide: the catalog grows from real student data.

---

## Part 4: Manipulatives (this is what wins the hackathon)

Numbers on a screen are abstract. A six-year-old does not have the abstraction yet. The established approach is **Concrete → Representational → Abstract**, and it maps cleanly onto the mastery model you already have.

### 4.1 Build three, not seven

| Manipulative | Skills | Why it is the right one |
|---|---|---|
| **Bundling sticks** | Add and subtract within 20, and all carrying | 10 loose sticks snap into a bundle. Carrying *is* bundling. A child who watches 10 ones become 1 ten cannot produce 1017. |
| **Number line** | Counting on, subtraction, comparison | Subtraction as distance, not takeaway. Fixes `SUB_SMALLER_FROM_LARGER` directly. |
| **Ten-frame** | Making 10, number bonds | The fastest path to fluency facts |

Base-10 blocks are the same primitive as bundling sticks with a different sprite. Build the sticks, reskin later if there is time.

### 4.2 The moment that sells the whole app

On attempt 2, the manipulative opens **pre-loaded with the child's own wrong answer**.

For `86 + 94 → 1017`: show 8 bundles + 6 sticks, then 9 bundles + 4 sticks. The child drags them together. The 10 loose sticks glow and refuse to sit as loose sticks. They snap into a bundle and slide to the tens column.

> **Superseded, 2026-09-16.** "The number under the blocks updates to 180 as it happens" contradicts CLAUDE.md's "a manipulative never resolves the answer for the student", which forbids a total that tallies while the student drags. What actually shipped is the per-column answer digit: each column's digit appears under the rule when that column is finished, and nothing updates mid-drag. See "Column arithmetic" in CLAUDE.md.

Nobody explained the rule. The child saw why the rule exists.

Film this for the demo video. It is the single strongest 15 seconds you have.

### 4.3 Fading is driven by the mastery model

This is where BKT stops being invisible:

| Mastery estimate | Mode |
|---|---|
| < 0.4 | Manipulative always visible, child solves by manipulating |
| 0.4 to 0.7 | Manipulative collapsed, one tap to open, appears automatically on error |
| > 0.7 | Abstract only, manipulative available on request |

Now the mastery model has a *visible consequence*. When a judge asks what the adaptive engine does, the answer is "it decides whether this child still needs to see the blocks," which anyone understands instantly.

---

## Part 5: Making the graph earn its place

Current flow is effectively linear. Add one node and three conditional edges:

```
Curriculum ──► Problem Gen ──► [student answers] ──► Diagnosis
                    ▲                                    │
                    │                         ┌──────────┼──────────┐
                    │                     correct    bug found   3rd fail
                    │                         │          │          │
                    │                         ▼          ▼          ▼
                    │                   Engagement  Remediation  Curriculum
                    │                         │          │      (demote to
                    └─────────────────────────┴──────────┘    prerequisite)
```

**Remediation node** (new): takes `bug_id` and `attempt_number`, returns the hint plus the visual payload, routes back to the same problem. No LLM call. Roughly 40 lines.

**Curriculum node** gains a demotion path: three failures on a skill pushes the child down to its prerequisite rather than forward. This is the behaviour that makes the app feel like a tutor instead of a worksheet, and it is currently missing.

Draw this diagram in the README and in the video. Judges respond to a graph with real conditional branching far more than to a linear pipeline.

---

## Part 6: UI shell

You are right that UI wins judged hackathons. Priorities, highest return first:

1. **Kill the number spinner.** Your screenshot uses `<input type="number">` with stepper arrows. This is the most damaging small thing in the app: a child can arrow their way to the correct answer without computing anything, which produces a correct answer with no misconception signal and a falsely inflated mastery estimate. It is also unusable on a tablet. Replace it with a large on-screen number pad: digits 0 to 9, backspace, submit. Big targets, no keyboard dependency, and every submission becomes a real answer.
2. **Manipulative canvas is the primary surface.** The equation is a caption underneath it, not the hero element. This one inversion changes the entire read of the app.
3. **Quest map.** A short path of 4 to 6 skill nodes, current node pulsing, completed ones filled. Visible progress is the main antidote to "the game never ends."
4. **Mascot with 4 states.** Idle, thinking, correct, encouraging. Cheap to build, enormously effective at the target age, and carries emotional tone so the *text* does not have to.
5. **End-of-quest report.** Skills mastered, misconceptions repaired (by name), problems solved, time. This screen doubles as your parent/teacher view and is where the invisible model becomes legible. Strong closing shot for the video.
6. **Sound.** Three effects: correct, snap-into-bundle, quest complete. Disproportionate impact for the effort.

Keep the palette to three colors plus neutrals, and one rounded display font. Consistency reads as polish more than any individual flourish.

### 6.1 Tablet and touch

You are right and I was wrong to cut this. The manipulatives are drag-and-drop, and drag built on `mousedown` / `mousemove` does not work on touch at all. Retrofitting that on Day 6 is a rewrite of the component you spent Day 3 on. Build it touch-first and it costs nothing.

**What this means concretely, and where it stops:**

- Use **pointer events** (`pointerdown` / `pointermove` / `pointerup`), not mouse events. One code path covers mouse, touch, and stylus. This is the whole decision, and making it on Day 3 is the entire cost.
- Set `touch-action: none` on the drag surface so the browser does not steal the gesture for scrolling. This is the bug that eats an hour if you hit it late.
- Minimum 48px touch targets. Number pad keys closer to 64px.
- **One layout, tablet landscape.** Target roughly 1024 x 768 and let it scale. Design at that size, verify it still works on a desktop browser at a wider width.

Explicitly not doing: phone portrait, a mobile breakpoint set, orientation-change handling. A 4-inch portrait screen cannot hold a manipulative canvas and a number pad at usable sizes, and no K-5 child is being handed a phone to do base-10 blocks on. Tablet landscape is the real device. Record the demo on it.

### 6.2 Dyslexia-adjacent basics

You raised dyslexia for the diagnosis rules. The same concern has cheap UI answers worth taking:

- Never signal error with color alone. Red plus an icon plus the hint text.
- Numerals stay visible at all times during a word problem, so the arithmetic does not depend on re-reading the sentence.
- Generous letter spacing and line height, and avoid a display font with ambiguous 6/9 or 1/7 forms in the *problem* area. Keep the playful font for chrome and headings only.

---

## Part 7: Things that will bite you on demo day

### 7.1 Seeded sessions

Scene 4 of your video shows a high-mastery student with the blocks faded out. You cannot film that unless you can *start* a session in that state, and you cannot reach it by playing, because a demo session is 10 problems long and mastery takes longer than that.

Build a `?seed=` parameter with three fixed profiles:

| Seed | State | Used for |
|---|---|---|
| `new` | Fresh, all mastery at prior | Default, and the video opening |
| `struggling` | Low mastery on `add_2digit_carry`, one prior `ADD_CONCAT_NO_CARRY` | The misconception scenes |
| `fluent` | Mastery > 0.8, blocks faded, abstract only | Scene 4, the CRA fading beat |

Two hours of work. Without it you cannot film half your video, and a judge clicking your live link lands on a blank new session with nothing to see. Do this on Day 5, not Day 7.

### 7.2 Session survives a refresh

You deliberately chose no LangGraph checkpointer, with the caller managing `SessionState` between calls. That is the right call for restart-safety on the server, but it means a browser refresh mid-session loses everything. During a live demo, or on a judge's tablet, that is a dead end.

Persist the session id and state snapshot to `localStorage` on every turn, and rehydrate on load. Thirty lines. It also protects you from your own dev-server restarts all week.

### 7.3 Unresolved skills have to come back

Attempt 3 fails, the child is demoted to the prerequisite, and then the failed skill is never seen again. The session ends and the report says "unresolved" with no path forward.

Re-surface it: after two correct answers on the prerequisite, bring the original skill back once. If it fails again, end the quest early on a genuine win at the lower level rather than grinding. A tutor comes back to the hard thing. That behaviour is the whole claim of the app.

### 7.4 Word problems are a reading test unless you constrain them

The balloon problem is fine. An LLM left unconstrained will produce a 30-word sentence with a word a first grader cannot decode, and then you are measuring reading, not math. Constrain the generation prompt hard: **20 words maximum, one common name, one concrete countable object, present the numerals as digits, no clauses.** Validate the length in code and regenerate once if it overruns.

### 7.5 LangSmith tracing

Agreed, and it is cheaper than I implied: LangGraph auto-traces once the environment variables are set, so this is roughly 30 minutes on Day 6 and it gives you a visible artifact for the judges when you talk about production readiness.

One distinction worth keeping clear. LangSmith traces your **LLM calls**, and you only have four of them, all off the critical path. It will not capture the thing that actually matters for scale: which misconceptions fire, which fall through to `UNCLASSIFIED`, and where children abandon. That needs your own event log, written to the same SQLite file, one row per submission with `problem_id`, `skill`, `submitted`, `bug_id`, `attempt`, `time_taken`.

Build both. The event log is the one that turns into your "what's next" slide, because it is the data that grows the misconception catalog.

---

## Part 8: Sequencing

| Day | Work | Done when |
|---|---|---|
| **1** (Sep 11) | Bugs 1.1 to 1.4: feedback binding, retry ladder, quest termination, verdict split from narrative. Number pad replaces the spinner. | Wrong answer keeps the same problem on screen and never leaks the answer on attempt 1 |
| **2** | `misconceptions.json`, detectors, hand-written hints, digit-reversal rule, non-signal handling, event log table | Every bug in the catalog produces a specific hint in a unit test |
| **3** | Bundling sticks component, **pointer events from the first line**, auto-bundle animation | 86 + 94 solvable entirely by manipulation, working on a tablet |
| **4** | Wrong-answer pre-loading, number line, ten-frame, CRA fading wired to BKT, unresolved-skill return | Attempt 2 opens the visual showing the child's own error |
| **5** | Quest map, mascot, end-of-quest report, sound, seeded sessions, localStorage rehydration | Full session start to finish with no dead ends, and all three seeds load |
| **6** | Latency pass, prefetch, copy caps, word-problem constraints, LangSmith env setup, tablet-landscape layout pass, README with architecture diagram | Submit-to-feedback under 150 ms, clean on 1024 x 768 |
| **7** (Sep 17) | Demo video, submission form, AI-assistance disclosure | Submitted with a day of slack |

Submit on the 17th. Early submissions may be reviewed as they arrive, and a day of buffer protects you from a broken deploy on deadline night.

---

## Part 9: Explicitly not building

Say no to these now so they do not eat Day 5:

- Accounts, login, multi-user, persistence beyond a session
- More subjects. Subject-agnosticism is a claim you make in the "what's next" section, not code you write.
- Additional manipulatives past the three
- Speech, TTS, voice input
- Phone portrait layout, breakpoint sets, orientation handling. Tablet landscape only.
- Any new LLM touchpoint beyond the four already specified
- Refactoring the BKT model. It is fine. It just needs to be visible.

---

Verification lives in `docs/CHECKLIST.md`. Run it as a manual pass on Day 6 and again before recording.
