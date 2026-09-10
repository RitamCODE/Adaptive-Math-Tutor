"""The `select_next_skill` node: picks the next skill to teach.

Pure and deterministic — no LLM in the curriculum-selection path, per the
project's hard constraints.
"""

from backend.models.bkt import MASTERY_THRESHOLD
from backend.skills.skill_graph import SkillGraph


def select_next_skill(mastery: dict[str, float], skill_graph: SkillGraph) -> str:
    """First skill (in prerequisite order) that is unlocked and not yet mastered.

    If every skill is already mastered, returns the last skill in
    topological order so the caller always gets a skill to keep generating
    problems for — the return type is `str`, not `str | None`, and nothing
    in this task defines a "curriculum complete" terminal state.
    """
    order = skill_graph.topological_order()
    for skill in order:
        if (
            skill_graph.is_unlocked(skill, mastery, threshold=MASTERY_THRESHOLD)
            and mastery.get(skill, 0.0) < MASTERY_THRESHOLD
        ):
            return skill
    return order[-1]
