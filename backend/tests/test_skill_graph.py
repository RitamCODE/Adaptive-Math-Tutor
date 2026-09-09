from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH, SkillGraph


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
    assert DEFAULT_SKILL_GRAPH.is_unlocked("addition_no_carry", mastery={})


def test_is_unlocked_false_when_prerequisite_below_threshold():
    mastery = {"addition_no_carry": 0.5}
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", mastery)


def test_is_unlocked_false_when_prerequisite_missing():
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", mastery={})


def test_is_unlocked_true_when_prerequisite_meets_threshold():
    mastery = {"addition_no_carry": 0.8}
    assert DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", mastery)


def test_is_unlocked_respects_custom_threshold():
    mastery = {"addition_no_carry": 0.75}
    assert DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", mastery, threshold=0.7)
    assert not DEFAULT_SKILL_GRAPH.is_unlocked("addition_carry", mastery, threshold=0.8)


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
