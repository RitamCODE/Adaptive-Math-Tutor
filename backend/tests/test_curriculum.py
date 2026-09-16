from backend.models.bkt import MASTERY_MIN_RUN
from backend.nodes.curriculum import select_next_skill
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from backend.tests.conftest import make_state, mastered_state


def test_select_next_skill_returns_first_skill_when_mastery_empty():
    assert select_next_skill(make_state(), DEFAULT_SKILL_GRAPH) == "addition_no_carry"


def test_select_next_skill_skips_mastered_skills():
    state = mastered_state("addition_no_carry")
    assert select_next_skill(state, DEFAULT_SKILL_GRAPH) == "addition_carry"


def test_select_next_skill_stays_put_when_mastery_is_high_but_the_run_is_short():
    """One correct answer lifts a fresh skill past 0.8, so without the run
    gate the curriculum would advance off a skill after a single success."""
    state = make_state({"addition_no_carry": 0.9025}, {"addition_no_carry": 1})
    assert select_next_skill(state, DEFAULT_SKILL_GRAPH) == "addition_no_carry"


def test_select_next_skill_reaches_subtraction_once_addition_is_complete():
    state = mastered_state("addition_no_carry", "addition_carry")
    assert select_next_skill(state, DEFAULT_SKILL_GRAPH) == "subtraction_no_borrow"


def test_select_next_skill_respects_prerequisite_lock():
    graph = SkillGraph(prerequisites={"a": [], "b": ["a"]})
    assert select_next_skill(make_state(), graph) == "a"


def test_select_next_skill_terminal_case_returns_last_skill_when_all_mastered():
    state = mastered_state(*DEFAULT_SKILL_GRAPH.all_skills())
    assert select_next_skill(state, DEFAULT_SKILL_GRAPH) == "subtraction_borrow"


def test_select_next_skill_ignores_a_skill_whose_run_reset():
    """A run that dropped back to zero makes the skill current again."""
    state = make_state(
        {"addition_no_carry": 0.95, "addition_carry": 0.95},
        {"addition_no_carry": MASTERY_MIN_RUN, "addition_carry": 0},
    )
    assert select_next_skill(state, DEFAULT_SKILL_GRAPH) == "addition_carry"
