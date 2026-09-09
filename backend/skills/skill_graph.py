"""Prerequisite DAG over skills.

Consumed by the (future) curriculum node's `select_next_skill`, which needs
to know which skills are unlocked given current mastery. This module only
defines the graph structure and query helpers, not the selection policy
itself.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillGraph:
    # skill_tag -> list of skill_tags that must be mastered first
    prerequisites: dict[str, list[str]]

    def all_skills(self) -> list[str]:
        return list(self.prerequisites.keys())

    def prerequisites_of(self, skill: str) -> list[str]:
        return list(self.prerequisites[skill])

    def is_unlocked(
        self,
        skill: str,
        mastery: dict[str, float],
        threshold: float = 0.8,
    ) -> bool:
        """True if every prerequisite of `skill` meets the mastery threshold.

        A skill with no prerequisites is always unlocked. A prerequisite the
        student has no record for yet (not in `mastery`) counts as unmastered.
        """
        return all(
            mastery.get(prereq, 0.0) >= threshold
            for prereq in self.prerequisites_of(skill)
        )

    def topological_order(self) -> list[str]:
        """Skills ordered so every skill appears after all of its prerequisites."""
        order: list[str] = []
        visited: set[str] = set()

        def visit(skill: str, stack: tuple[str, ...] = ()) -> None:
            if skill in visited:
                return
            if skill in stack:
                cycle = " -> ".join([*stack, skill])
                raise ValueError(f"cycle detected in skill graph: {cycle}")
            for prereq in self.prerequisites_of(skill):
                visit(prereq, (*stack, skill))
            visited.add(skill)
            order.append(skill)

        for skill in self.all_skills():
            visit(skill)
        return order


DEFAULT_SKILL_GRAPH = SkillGraph(
    prerequisites={
        "addition_no_carry": [],
        "addition_carry": ["addition_no_carry"],
        "subtraction_no_borrow": ["addition_carry"],
        "subtraction_borrow": ["subtraction_no_borrow"],
    }
)
