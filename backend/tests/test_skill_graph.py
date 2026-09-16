from backend.models.bkt import MASTERY_MIN_RUN
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph
from backend.tests.conftest import make_state, mastered_state


def test_all_skills_returns_the_four_skills():
    assert set(DEFAULT_SKILL_GRAPH.all_skills()) == {
        "addition_no_carry",
        "addition_carry",
        "subtraction_no_borrow",
        "subtraction_borrow",
    }


def test_prerequisites_of_root_skill_is_empty():
    assert DEFAULT_SKILL_GRAPH.prerequisites_of("addition_no_carry") == []


def test_prerequisites_of_chained_skill():
    assert DEFAULT_SKILL_GRAPH.prerequisites_of("addition_carry") == ["addition_no_carry"]
    assert DEFAULT_SKILL_GRAPH.prerequisites_of("subtraction_no_borrow") == ["addition_carry"]
    assert DEFAULT_SKILL_GRAPH.prerequisites_of("subtraction_borrow") == ["subtraction_no_borrow"]


def test_is_unlocked_true_with_no_prerequisites():
    assert DEFAULT_SKILL_GRAPH.is_unlocked("addition_no_carry", make_state())


def test_is_unlocked_false_when_prerequisite_below_threshold():
    state = make_state({"addition_no_carry": 0.5}, {"addition_no_carry": MASTERY_MIN_RUN})
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", state)


def test_is_unlocked_false_when_prerequisite_missing():
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", make_state())


def test_is_unlocked_true_when_prerequisite_meets_threshold():
    state = make_state({"addition_no_carry": 0.8}, {"addition_no_carry": MASTERY_MIN_RUN})
    assert DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", state)


def test_is_unlocked_false_when_prerequisite_is_above_threshold_but_run_is_short():
    """Replaces the old custom-threshold test: unlocking now obeys the same
    sustained-mastery gate as routing, so a prerequisite that has only just
    crossed 0.8 does not unlock the next skill yet."""
    state = make_state({"addition_no_carry": 0.95}, {"addition_no_carry": MASTERY_MIN_RUN - 1})
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", state)


def test_group_of_maps_each_sub_skill_to_its_parent():
    assert DEFAULT_SKILL_GRAPH.group_of("addition_no_carry") == "addition"
    assert DEFAULT_SKILL_GRAPH.group_of("addition_carry") == "addition"
    assert DEFAULT_SKILL_GRAPH.group_of("subtraction_no_borrow") == "subtraction"
    assert DEFAULT_SKILL_GRAPH.group_of("subtraction_borrow") == "subtraction"
    assert DEFAULT_SKILL_GRAPH.group_of("not_a_skill") is None


def test_skills_in_group():
    assert DEFAULT_SKILL_GRAPH.skills_in_group("addition") == ["addition_no_carry", "addition_carry"]
    assert DEFAULT_SKILL_GRAPH.skills_in_group("subtraction") == [
        "subtraction_no_borrow",
        "subtraction_borrow",
    ]


def test_group_is_mastered_only_when_every_sub_skill_is():
    one_of_two = mastered_state("addition_no_carry")
    assert not DEFAULT_SKILL_GRAPH.is_group_mastered("addition", one_of_two)

    both = mastered_state("addition_no_carry", "addition_carry")
    assert DEFAULT_SKILL_GRAPH.is_group_mastered("addition", both)


def test_all_groups_mastered_requires_all_four_sub_skills():
    three = mastered_state("addition_no_carry", "addition_carry", "subtraction_no_borrow")
    assert not DEFAULT_SKILL_GRAPH.all_groups_mastered(three)

    four = mastered_state(*DEFAULT_SKILL_GRAPH.all_skills())
    assert DEFAULT_SKILL_GRAPH.all_groups_mastered(four)


def test_all_groups_mastered_is_false_for_an_ungrouped_graph():
    """A synthetic graph with no groups declared must not read as complete."""
    graph = SkillGraph(prerequisites={"a": [], "b": ["a"]})
    assert not graph.all_groups_mastered(mastered_state("a", "b"))


def test_topological_order_respects_prerequisites():
    order = DEFAULT_SKILL_GRAPH.topological_order()
    positions = {skill: i for i, skill in enumerate(order)}
    for skill in DEFAULT_SKILL_GRAPH.all_skills():
        for prereq in DEFAULT_SKILL_GRAPH.prerequisites_of(skill):
            assert positions[prereq] < positions[skill]


def test_topological_order_detects_cycles():
    cyclic = SkillGraph(prerequisites={"a": ["b"], "b": ["a"]})
    try:
        cyclic.topological_order()
        assert False, "expected ValueError for cyclic graph"
    except ValueError:
        pass
