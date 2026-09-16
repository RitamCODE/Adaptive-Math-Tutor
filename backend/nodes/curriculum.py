"""The `select_next_skill` node: picks the next skill to teach.

Pure and deterministic — no LLM in the curriculum-selection path, per the
project's hard constraints.
"""

from backend.models.bkt import is_mastered
from backend.models.state import SessionState
from backend.skills.skill_graph import SkillGraph


def select_next_skill(state: SessionState, skill_graph: SkillGraph) -> str:
    """First skill (in prerequisite order) that is unlocked and not yet mastered.

    Takes the whole `SessionState` rather than a bare mastery dict because
    "mastered" is no longer a property of the mastery number alone: it also
    depends on `state.mastery_run`, the per-skill count of consecutive
    signal-bearing answers that held the skill at or above threshold. Both
    checks below go through `is_mastered` so this node, the router and the
    HTTP layer can never disagree about what is mastered.

    If every skill is already mastered, returns the last skill in
    topological order so the caller always gets a skill to keep generating
    problems for — the return type is `str`, not `str | None`, and nothing
    in this task defines a "curriculum complete" terminal state.
    """
    order = skill_graph.topological_order()
    for skill in order:
        if skill_graph.is_unlocked(skill, state) and not is_mastered(skill, state):
            return skill
    return order[-1]
