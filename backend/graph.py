"""LangGraph wiring for the adaptive-tutor turn cycle.

Topology (see CLAUDE.md's routing spec):

    START --[route_from_start]--> "generate_problem"   (no answer pending: bootstrap/regenerate)
    START --[route_from_start]--> "grade_and_diagnose"  (an answer is pending)

    "grade_and_diagnose" -> "update_mastery" -> "decide_engagement"
    "decide_engagement" --[route_after_engagement]--> "advance_skill"  (mastery >= threshold)
    "decide_engagement" --[route_after_engagement]--> "repeat_skill"   (otherwise)

    "generate_problem" -> END
    "advance_skill"    -> END
    "repeat_skill"     -> END

No checkpointer/persistence: a scripted driver threads `SessionState` through
Python by calling `graph.invoke()` once per turn, feeding a fresh
`last_response` in between calls to simulate a student's answer arriving.
"""

from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from backend.models.bkt import BKTParams, MASTERY_THRESHOLD, update_mastery as bkt_update_mastery
from backend.models.state import LastResponse, Misconception, SessionState
from backend.nodes.curriculum import select_next_skill
from backend.nodes.diagnosis import grade_and_diagnose as pure_grade_and_diagnose
from backend.nodes.engagement import decide_engagement as pure_decide_engagement
from backend.nodes.problem_gen import generate_problem as pure_generate_problem
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH


def _difficulty_for(mastery: dict[str, float], skill: str) -> float:
    return mastery.get(skill, BKTParams().p_init)


# --- node wrappers: thin adapters from LangGraph's (state) -> dict convention
#     onto the pure functions in nodes/*.py. ---


def generate_problem_node(state: SessionState) -> dict:
    """START fast path: no answer pending. Bootstraps a brand-new session
    (current_problem is None -> pick the first skill via select_next_skill)
    or re-serves a freshly generated problem for the current skill.
    """
    skill = (
        state.current_problem.skill_tag
        if state.current_problem is not None
        else select_next_skill(state.skill_mastery, DEFAULT_SKILL_GRAPH)
    )
    problem = pure_generate_problem(skill, _difficulty_for(state.skill_mastery, skill))
    return {"current_problem": problem, "next_action": "new_problem"}


def grade_and_diagnose_node(state: SessionState) -> dict:
    problem, response = state.current_problem, state.last_response
    diagnosis = pure_grade_and_diagnose(problem, response.answer)

    misconception_log = list(state.misconception_log)
    if not diagnosis.correct and diagnosis.bug_type is not None:
        misconception_log.append(
            Misconception(skill=problem.skill_tag, bug_type=diagnosis.bug_type, timestamp=datetime.now(timezone.utc))
        )

    # grade_and_diagnose is the single source of truth for correctness;
    # overwrite last_response.correct rather than trusting whatever the
    # caller supplied, so update_mastery downstream never disagrees with it.
    corrected_response = LastResponse(
        answer=response.answer, correct=diagnosis.correct, time_taken_sec=response.time_taken_sec
    )
    return {"misconception_log": misconception_log, "last_response": corrected_response}


def update_mastery_node(state: SessionState) -> dict:
    skill = state.current_problem.skill_tag
    new_mastery = bkt_update_mastery(state.skill_mastery, skill, state.last_response.correct, BKTParams())
    return {"skill_mastery": new_mastery}


def decide_engagement_node(state: SessionState) -> dict:
    return {"engagement": pure_decide_engagement(state)}


def advance_skill_node(state: SessionState) -> dict:
    """Composes select_next_skill + generate_problem in one graph node.

    SessionState (per CLAUDE.md's exact shape) has no field to carry "the
    skill select_next_skill just chose" across a separate graph-node hop to
    generate_problem, short of overloading current_problem with a throwaway
    placeholder. Rather than invent a field or a placeholder Problem, both
    pure functions are called back-to-back here — they remain independent,
    separately unit-tested pure functions; only the *wiring* combines them.
    """
    new_skill = select_next_skill(state.skill_mastery, DEFAULT_SKILL_GRAPH)
    problem = pure_generate_problem(new_skill, _difficulty_for(state.skill_mastery, new_skill))
    return {"current_problem": problem, "next_action": "advance_skill", "last_response": None}


def repeat_skill_node(state: SessionState) -> dict:
    skill = state.current_problem.skill_tag
    problem = pure_generate_problem(skill, _difficulty_for(state.skill_mastery, skill))
    return {"current_problem": problem, "next_action": "repeat_skill", "last_response": None}


# --- router functions (no state mutation; pick the next node name) ---


def route_from_start(state: SessionState) -> str:
    return "generate_problem" if state.last_response is None else "grade_and_diagnose"


def route_after_engagement(state: SessionState) -> str:
    skill = state.current_problem.skill_tag
    return "advance_skill" if state.skill_mastery.get(skill, 0.0) >= MASTERY_THRESHOLD else "repeat_skill"


def build_graph() -> StateGraph:
    graph = StateGraph(SessionState)

    graph.add_node("generate_problem", generate_problem_node)
    graph.add_node("grade_and_diagnose", grade_and_diagnose_node)
    graph.add_node("update_mastery", update_mastery_node)
    graph.add_node("decide_engagement", decide_engagement_node)
    graph.add_node("advance_skill", advance_skill_node)
    graph.add_node("repeat_skill", repeat_skill_node)

    graph.add_conditional_edges(
        START,
        route_from_start,
        {"generate_problem": "generate_problem", "grade_and_diagnose": "grade_and_diagnose"},
    )
    graph.add_edge("grade_and_diagnose", "update_mastery")
    graph.add_edge("update_mastery", "decide_engagement")
    graph.add_conditional_edges(
        "decide_engagement",
        route_after_engagement,
        {"advance_skill": "advance_skill", "repeat_skill": "repeat_skill"},
    )
    graph.add_edge("generate_problem", END)
    graph.add_edge("advance_skill", END)
    graph.add_edge("repeat_skill", END)

    return graph


app = build_graph().compile()
