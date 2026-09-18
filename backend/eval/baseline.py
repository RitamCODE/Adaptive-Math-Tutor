"""The fixed-difficulty, non-adaptive comparison condition.

Swaps exactly the two mechanisms that make problem selection "adaptive" in
the real engine:

  1. WHEN to move to the next skill. The real engine waits for
     `is_mastered()` (BKT mastery: at or above the 0.8 threshold after each
     of the last 3 consecutive signal-bearing answers, `backend/models/bkt.py`).
     The baseline instead moves on after a fixed number of correctly-solved
     problems on the current skill (`PROBLEMS_PER_SKILL`), never consulting
     BKT mastery to decide pacing.
  2. HOW WIDE the operands are. The real engine escalates operand
     digit-width via its own ladder (`backend/skills/_difficulty_ladder.py`)
     based on a run of consecutive correct answers. The baseline pins one
     digit-width tier (`PINNED_TIER`, an index into that ladder) for the
     whole session.

Everything else is identical between conditions: grading, the BKT update
itself (used here only to MEASURE the outcome, never to drive it), the
3-attempt retry ladder, demotion to a prerequisite skill on a 3rd wrong
attempt, the once-only resurface, and the quest-length/fatigue-stop
session-end rules. The prerequisite lock also stays real and shared:
`SkillGraph.is_unlocked` (`backend/skills/skill_graph.py`) imports
`is_mastered` into its OWN module namespace and is never patched here, so a
skill still only unlocks once its prerequisite is GENUINELY mastered in
both conditions -- the baseline cannot skip ahead of content it hasn't
earned, it can only fail to wait for a skill it's already earned before
moving on.

This works by patching `is_mastered`, `select_next_skill`, and
`_difficulty_for` as seen from `backend.graph`'s own module namespace, which
is where its node functions (`generate_problem_node`, `advance_skill_node`,
etc.) look those names up at call time -- no engine file is edited, and
`backend.skills.skill_graph`'s own `is_mastered` import is a separate name
binding in a separate module, untouched by this.
"""

from __future__ import annotations

import contextlib
from unittest.mock import patch

import backend.graph as graph_module
from backend.models.state import SessionState
from backend.skills.skill_graph import SkillGraph

PROBLEMS_PER_SKILL = 4  # quest_length defaults to 16 problems across 4 skills
PINNED_TIER = 0  # each skill's own narrowest valid tier: 1-digit for the two
                 # non-regrouping skills, 2-digit for addition_carry/subtraction_borrow
                 # (1-digit can't carry or borrow at all) -- raise this for a harder,
                 # more demanding fixed-worksheet baseline


def _make_fixed_schedule_is_mastered(problems_served: dict[str, int], problems_per_skill: int):
    def fixed_is_mastered(skill: str, state: SessionState) -> bool:
        """Stands in for backend.models.bkt.is_mastered, but only as seen by
        route_after_engagement's "should I advance to a new skill now"
        check -- never touches the real mastery estimate used to measure
        the outcome. Counts correctly-solved problems, since this function
        is only ever called from that router's `correct` branch."""
        problems_served[skill] = problems_served.get(skill, 0) + 1
        return problems_served[skill] >= problems_per_skill
    return fixed_is_mastered


def _make_fixed_schedule_select_next_skill(problems_served: dict[str, int], problems_per_skill: int):
    def fixed_select_next_skill(state: SessionState, skill_graph: SkillGraph) -> str:
        """Same prerequisite gate as the real select_next_skill (genuinely
        BKT-locked, see module docstring), but picks the first unlocked
        skill whose fixed budget isn't used up yet, instead of the first
        unlocked skill that isn't yet really mastered. If every unlocked
        skill's budget is exhausted but the next skill in order is still
        really locked, this keeps returning the current one -- a fixed
        schedule that outpaces genuine prerequisite mastery stalls exactly
        like the adaptive engine would, rather than skipping ahead.

        Falls back to the LAST genuinely unlocked skill, not the real
        select_next_skill's "return the topologically last skill" fallback:
        that fallback means "everyone's mastered" over there, but here it
        can just as easily mean "everyone's fixed budget ran out while a
        later skill is still really locked," and returning a locked skill
        would let the fixed schedule skip content it hasn't earned."""
        order = skill_graph.topological_order()
        fallback = None
        for skill in order:
            if not skill_graph.is_unlocked(skill, state):
                continue
            if problems_served.get(skill, 0) < problems_per_skill:
                return skill
            fallback = skill
        return fallback if fallback is not None else order[0]
    return fixed_select_next_skill


def _make_fixed_difficulty_for(pinned_tier: int):
    """Only the REQUESTED difficulty is pinned. `state.digit_level` itself
    still advances for real underneath (update_mastery_node's call to
    advance_digit_level isn't patched), it's just never read for the
    difficulty passed to generate_problem. The one visible side effect: for
    the two skills with a 1-digit narrowest tier, `_combo_hint_for` (graph.py)
    checks the real `digit_level` to decide whether to keep avoiding
    repeat/trivial combos, so a long run at a pinned tier can quietly stop
    getting that pacing help once the real ladder thinks it's moved past
    tier 0 -- harmless for the mastery measurement (combo choice doesn't
    change problem difficulty), just a minor loss of combo variety.
    """
    def fixed_difficulty_for(state: SessionState, skill: str) -> float:
        return graph_module._difficulty_for_level({skill: pinned_tier}, skill)
    return fixed_difficulty_for


@contextlib.contextmanager
def non_adaptive_condition(problems_per_skill: int = PROBLEMS_PER_SKILL, pinned_tier: int = PINNED_TIER):
    """Within this block, backend.graph.app.invoke() runs the fixed-schedule,
    fixed-difficulty baseline instead of the adaptive engine. Creates a
    fresh `problems_served` counter each time it's entered -- always enter
    this once per synthetic student's session, never share one context
    across multiple students."""
    problems_served: dict[str, int] = {}
    with patch.object(graph_module, "is_mastered", _make_fixed_schedule_is_mastered(problems_served, problems_per_skill)), \
         patch.object(graph_module, "select_next_skill", _make_fixed_schedule_select_next_skill(problems_served, problems_per_skill)), \
         patch.object(graph_module, "_difficulty_for", _make_fixed_difficulty_for(pinned_tier)):
        yield
