# Documentation audit

A recurring pass — first run 2026-09-16, re-run after any change that alters behaviour the docs describe — checking every descriptive file in the repo — READMEs, `CLAUDE.md`, `CHANGELOG.md`, and the `docs/` planning files — against the actual code and against `CHANGELOG.md`'s dated record of what has actually landed. Files under `.venv/` and auto-generated files like `.pytest_cache/README.md` are third-party or tooling output, not project docs, and are out of scope.

**Role** distinguishes two kinds of doc here: a *living reference* is meant to always describe current code, so drift is a bug; a *frozen historical doc* records a decision or a plan as it stood at a point in time, and rewriting it after the fact would erase that record — `CHANGELOG.md` is where "what actually happened" belongs instead.

| File | Role | Last touched (commit) | Verdict at audit time | Fix applied |
|---|---|---|---|---|
| `README.md` | Living reference | `fb0cd24` (2026-09-16) | Stale — "Not yet built" list claimed manipulatives, the end-of-quest report, and seeded demo profiles were unbuilt; all three had shipped on 2026-09-14/15 | Moved shipped items to "Working," added skill resurfacing and sound effects (also undocumented), updated the frontend file summary in "Project structure" |
| `CLAUDE.md` | Living reference (source of truth) | `70360bc` (2026-09-14) | Stale — `SessionState` schema missing the three fields skill resurfacing added | Added `pending_resurface`, `resurface_progress`, `resurfaced_skills` to the schema block |
| `CHANGELOG.md` | Living reference (append-only) | `fb0cd24` (2026-09-16) | Current — accurate by construction, each entry documents a commit that already landed | None; this audit's own entry appended below |
| `UI_DESIGN.md` | **Frozen historical doc** | `290884c` (2026-09-11) | Current-as-written — opens with "Planning doc only"; it's the reviewed proposal behind the 2026-09-11 redesign, not a status page | None (by design) |
| `backend/README.md` | Living reference | `7f2bed1` (2026-09-14) | Stale — HTTP API table listed 4 endpoints, code has 7; `SessionState` field list and the LLM-touchpoints section were both missing later additions | Added the 3 missing endpoints, the 3 resurface fields, LangSmith `wrap_openai` wrapping, and `flavor_word_problem`'s word-cap validation |
| `frontend/README.md` | Living reference | `5d1bec0` (2026-09-13) | Stale — file-structure listing had 7 component files and no `lib/`; actual tree has 11 components plus a 3-file `lib/` directory; `api.js` described as having 4 functions, has 7 | Updated the file tree, the function count, and added a paragraph on manipulative gating and the end-of-quest summary |
| `docs/CHECKLIST.md` | Living reference | `fb0cd24` (2026-09-16) | Stale — line 3 still referenced the old filename `docs/PLAN.md`, renamed to `docs/revision-plan.md` in commit `957ca15` (2026-09-14), which fixed the same reference everywhere except here | Fixed the reference |
| `docs/revision-plan.md` | **Frozen historical doc** | `7db616c` (2026-09-12) | Current-as-written — a day-by-day plan (`Day 1`...`Day 7`) written against a Sep-18 deadline; `CLAUDE.md` itself treats it as a plan to read, not a status to keep current | None (by design) |

## Pass 2 — 2026-09-16, after the sustained-mastery / skill-group / manipulative-remediation change

| File | Role | Verdict at audit time | Fix applied |
|---|---|---|---|
| `CLAUDE.md` | Living reference (source of truth) | Stale — described mastery as a single 0.8 crossing, quest termination as "2 skills mastered", the 0.4/0.7 bands as governing default visibility, and had no skill-group model | Added the skill-group model, the sustained-mastery gate (`is_mastered`/`MASTERY_MIN_RUN`) and its sticky-in-one-direction consequence, `mastery_run` in the `SessionState` schema, `quest_length` 16, the rewritten routing-logic table, the new `select_next_skill` signature, and three new frontend sections (manipulatives as remediation, the pinned equation, no resolved total) |
| `README.md` | Living reference | Stale — turn-flow step 4, the `bkt.py` line, the feature list's termination and manipulative-fading bullets. Two pre-existing errors surfaced in the same pass: step 4 claimed `skill_mastery`/`misconception_log` "never reach the client" (they do, as the localStorage snapshot), and the `docs/` tree carried a parenthetical about stale `PLAN.md` references that were themselves fixed in `957ca15` | Updated all four; added the parent-skill paragraph under the DAG; corrected the wire-format claim and the `PLAN.md` parenthetical; added `remediation.js` to the `lib/` listing |
| `backend/README.md` | Living reference | Stale — the branching diagram's `(>= 0.8)` label, the two routing bullets, `quest_length` (default 10), and the "single definition of mastered" paragraph; plus the same pre-existing "never reach the client" error, a tests table missing the new file and understating two others, and a response-model list missing `GroupProgress` | Rewrote the mastery-model section around `is_mastered`, added the skill-group table, corrected the diagram, routing bullets and the default; fixed the wire-format paragraph, added `test_mastery_gate.py` and widened the `test_api.py`/`test_skill_graph.py` rows, added `GroupProgress` |
| `frontend/README.md` | Living reference | Stale — its fading-bands sentence was the most complete statement of the old model in any doc and was wrong in both halves (default visibility, and force-open regardless of band); the `SkillTrailMap` line and the coupled-response-shapes list also predated grouping | Rewrote the manipulatives paragraph around the three remediation bands and the pinned equation; added `lib/remediation.js` to the file tree; corrected the `TenFrame` description, the `SkillTrailMap` line, the summary's grouping and the response-shapes list |
| `docs/CHECKLIST.md` | Living reference | Stale — section B's attempt-2 row, section G's header and its "open by default"/"above 0.7"/"number below updates"/fading-seeds rows, section H's 1024x768 row, section J's seed row, and two rows asserting `subtraction_borrow` was unreachable in one sitting | Rewrote all of them against the new behaviour and added a section E row for the curriculum-complete ending; every row left unticked per the file's convention |
| `docs/revision-plan.md`, `UI_DESIGN.md` | **Frozen historical docs** | Current-as-written — Part 4.3's band table and Part 6 item 2 ("equation is a caption underneath") now describe superseded behaviour, which is exactly what a frozen record is for | None (by design); `CLAUDE.md` carries the current rules |

## Re-running this audit

For each *living reference* row above: `git log -1 --format="%ad %h" --date=short -- <file>` gives the last-touched date; compare its claims about endpoints/components/schema fields against a fresh `grep`/`find` over the actual code (see the commands used for this pass, below), and against `CHANGELOG.md` entries dated after the doc's last touch.

```bash
grep -n '@app\.' backend/api.py                          # backend/README.md's endpoint table
find frontend/src -type f | sort                          # frontend/README.md's file tree
grep -n "pending_resurface\|resurface_progress\|resurfaced_skills" backend/models/state.py CLAUDE.md
grep -rn "PLAN.md" docs/ CLAUDE.md README.md backend frontend
```
