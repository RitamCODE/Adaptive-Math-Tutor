"""Prerequisite DAG over skills, plus the skill-group model layered on it.

Consumed by the curriculum node's `select_next_skill`, which needs to know
which skills are unlocked given current mastery. This module only defines
the graph structure and query helpers, not the selection policy itself.

The four skills are also grouped into two *parent* skills — Addition and
Subtraction — each holding two sub-skills. Every sub-skill keeps its own
independent BKT mastery value and its own threshold; a parent is mastered
only when all of its sub-skills are. Grouping changes how mastery is
aggregated and reported, never the traversal order: `topological_order`
still walks the same DAG in the same sequence.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.models.bkt import is_mastered

if TYPE_CHECKING:
    from backend.models.state import SessionState

GROUP_DISPLAY_NAMES = {"addition": "Addition", "subtraction": "Subtraction"}


@dataclass(frozen=True)
class SkillGraph:
    # skill_tag -> list of skill_tags that must be mastered first
    prerequisites: dict[str, list[str]]
    # parent skill name -> its sub-skills. Defaulted so the synthetic graphs
    # built in tests still construct from prerequisites alone.
    groups: dict[str, list[str]] = field(default_factory=dict)

    def all_skills(self) -> list[str]:
        return list(self.prerequisites.keys())

    def prerequisites_of(self, skill: str) -> list[str]:
        return list(self.prerequisites[skill])

    def is_unlocked(self, skill: str, state: "SessionState") -> bool:
        """True if every prerequisite of `skill` is mastered.

        Goes through `is_mastered` rather than comparing against the
        threshold directly, so unlocking obeys the same sustained-mastery
        gate as routing and the UI and the three can never disagree.

        A skill with no prerequisites is always unlocked. A prerequisite the
        student has no record for yet counts as unmastered.
        """
        return all(is_mastered(prereq, state) for prereq in self.prerequisites_of(skill))

    def group_of(self, skill: str) -> str | None:
        """The parent skill `skill` belongs to, or None if it is ungrouped."""
        for group, members in self.groups.items():
            if skill in members:
                return group
        return None

    def skills_in_group(self, group: str) -> list[str]:
        return list(self.groups[group])

    def is_group_mastered(self, group: str, state: "SessionState") -> bool:
        """A parent skill is mastered only when every sub-skill under it is."""
        return all(is_mastered(skill, state) for skill in self.skills_in_group(group))

    def all_groups_mastered(self, state: "SessionState") -> bool:
        """Every parent skill mastered — the curriculum-complete quest ending."""
        return bool(self.groups) and all(
            self.is_group_mastered(group, state) for group in self.groups
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
    },
    groups={
        "addition": ["addition_no_carry", "addition_carry"],
        "subtraction": ["subtraction_no_borrow", "subtraction_borrow"],
    },
)
