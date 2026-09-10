from backend.nodes.curriculum import select_next_skill
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph


def test_select_next_skill_returns_first_skill_when_mastery_empty():
    assert select_next_skill({}, DEFAULT_SKILL_GRAPH) == "addition_no_carry"


def test_select_next_skill_skips_mastered_skills():
    mastery = {"addition_no_carry": 0.9}
    assert select_next_skill(mastery, DEFAULT_SKILL_GRAPH) == "addition_carry"


def test_select_next_skill_respects_prerequisite_lock():
    graph = SkillGraph(prerequisites={"a": [], "b": ["a"]})
    assert select_next_skill({}, graph) == "a"


def test_select_next_skill_terminal_case_returns_last_skill_when_all_mastered():
    mastery = {skill: 0.9 for skill in DEFAULT_SKILL_GRAPH.all_skills()}
    assert select_next_skill(mastery, DEFAULT_SKILL_GRAPH) == "subtraction_borrow"
