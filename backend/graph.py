"""LangGraph wiring for the adaptive-tutor turn cycle.

Topology (see CLAUDE.md's routing spec):

    START --[route_from_start]--> "generate_problem"     (no answer pending: bootstrap/regenerate)
    START --[route_from_start]--> "grade_and_diagnose"    (an answer is pending)

    "grade_and_diagnose" --[route_after_diagnosis]--> "hold_non_signal"   (blank/rapid-guess)
    "grade_and_diagnose" --[route_after_diagnosis]--> "update_mastery"    (signal-bearing)

    "update_mastery" -> "decide_engagement"   (runs on every signal-bearing submission,
                                                correct or wrong, so consecutive_wrong tracks
                                                the fatigue stop regardless of outcome)

    "decide_engagement" --[route_after_engagement]--> "end_session"      (fatigue stop, or
                                                                          quest/mastery limits)
    "decide_engagement" --[route_after_engagement]--> "advance_skill"    (correct, mastery >= threshold)
    "decide_engagement" --[route_after_engagement]--> "new_problem"      (correct, otherwise)
    "decide_engagement" --[route_after_engagement]--> "retry_problem"    (wrong, attempt < 3)
    "decide_engagement" --[route_after_engagement]--> "demote_skill"     (wrong, attempt >= 3)

    "generate_problem", "hold_non_signal", "end_session", "advance_skill",
    "new_problem", "retry_problem", "demote_skill" -> END

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


def _is_signal(response: LastResponse) -> bool:
    return response.answer is not None and response.time_taken_sec >= 2.0


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
    return {
        "current_problem": problem, "next_action": "new_problem",
        "attempt_number": 1, "attempt_history": [],
    }


def grade_and_diagnose_node(state: SessionState) -> dict:
    problem, response = state.current_problem, state.last_response

    if not _is_signal(response):
        return {}

    diagnosis = pure_grade_and_diagnose(problem, response.answer, state.attempt_number)

    misconception_log = list(state.misconception_log)
    if not diagnosis.correct and diagnosis.bug_type not in (None, "unclassified"):
        misconception_log.append(
            Misconception(skill=problem.skill_tag, bug_type=diagnosis.bug_type, timestamp=datetime.now(timezone.utc))
        )

    attempt_history = [*state.attempt_history, (response.answer, diagnosis.bug_type)]

    # grade_and_diagnose is the single source of truth for correctness;
    # overwrite last_response.correct rather than trusting whatever the
    # caller supplied, so update_mastery downstream never disagrees with it.
    corrected_response = LastResponse(
        answer=response.answer, correct=diagnosis.correct, time_taken_sec=response.time_taken_sec
    )
    return {
        "misconception_log": misconception_log,
        "attempt_history": attempt_history,
        "last_response": corrected_response,
    }


def hold_non_signal_node(state: SessionState) -> dict:
    """Blank or rapid-guess submission: not a knowledge signal. Attempt
    counter, attempt_history, skill_mastery, and engagement all stay put."""
    return {"next_action": "retry_problem"}


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
    return {
        "current_problem": problem, "next_action": "advance_skill", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
    }


def new_problem_node(state: SessionState) -> dict:
    """Correct answer, mastery still below threshold: same skill, new problem."""
    skill = state.current_problem.skill_tag
    problem = pure_generate_problem(skill, _difficulty_for(state.skill_mastery, skill))
    return {
        "current_problem": problem, "next_action": "new_problem", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
    }


def retry_problem_node(state: SessionState) -> dict:
    """Wrong answer, attempt 1 or 2: same problem stays on screen."""
    return {"attempt_number": state.attempt_number + 1, "next_action": "retry_problem"}


def demote_skill_node(state: SessionState) -> dict:
    """Wrong answer, attempt 3 exhausted: demote to the prerequisite skill.

    A root skill with no prerequisite (e.g. addition_no_carry) has nothing to
    demote to; fall back to a fresh problem on the same skill instead of a
    fabricated demotion.
    """
    skill = state.current_problem.skill_tag
    prereqs = DEFAULT_SKILL_GRAPH.prerequisites_of(skill)
    if not prereqs:
        problem = pure_generate_problem(skill, _difficulty_for(state.skill_mastery, skill))
        return {
            "current_problem": problem, "next_action": "new_problem", "last_response": None,
            "attempt_number": 1, "attempt_history": [],
            "problems_completed": state.problems_completed + 1,
        }

    target = prereqs[0]
    problem = pure_generate_problem(target, _difficulty_for(state.skill_mastery, target))
    return {
        "current_problem": problem, "next_action": "demote_skill", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
    }


def end_session_node(state: SessionState) -> dict:
    return {"current_problem": None, "next_action": "end_session"}


# --- router functions (no state mutation; pick the next node name) ---


def route_from_start(state: SessionState) -> str:
    return "generate_problem" if state.last_response is None else "grade_and_diagnose"


def route_after_diagnosis(state: SessionState) -> str:
    return "update_mastery" if _is_signal(state.last_response) else "hold_non_signal"


def route_after_engagement(state: SessionState) -> str:
    if state.engagement.consecutive_wrong >= 4:
        return "end_session"

    correct = state.last_response.correct
    if not correct and state.attempt_number < 3:
        return "retry_problem"

    next_completed = state.problems_completed + 1
    mastered_count = sum(1 for m in state.skill_mastery.values() if m >= MASTERY_THRESHOLD)
    if next_completed >= state.quest_length or mastered_count >= 2:
        return "end_session"

    if correct:
        skill = state.current_problem.skill_tag
        return "advance_skill" if state.skill_mastery.get(skill, 0.0) >= MASTERY_THRESHOLD else "new_problem"
    return "demote_skill"


def build_graph() -> StateGraph:
    graph = StateGraph(SessionState)

    graph.add_node("generate_problem", generate_problem_node)
    graph.add_node("grade_and_diagnose", grade_and_diagnose_node)
    graph.add_node("hold_non_signal", hold_non_signal_node)
    graph.add_node("update_mastery", update_mastery_node)
    graph.add_node("decide_engagement", decide_engagement_node)
    graph.add_node("advance_skill", advance_skill_node)
    graph.add_node("new_problem", new_problem_node)
    graph.add_node("retry_problem", retry_problem_node)
    graph.add_node("demote_skill", demote_skill_node)
    graph.add_node("end_session", end_session_node)

    graph.add_conditional_edges(
        START,
        route_from_start,
        {"generate_problem": "generate_problem", "grade_and_diagnose": "grade_and_diagnose"},
    )
    graph.add_conditional_edges(
        "grade_and_diagnose",
        route_after_diagnosis,
        {"update_mastery": "update_mastery", "hold_non_signal": "hold_non_signal"},
    )
    graph.add_edge("update_mastery", "decide_engagement")
    graph.add_conditional_edges(
        "decide_engagement",
        route_after_engagement,
        {
            "end_session": "end_session",
            "advance_skill": "advance_skill",
            "new_problem": "new_problem",
            "retry_problem": "retry_problem",
            "demote_skill": "demote_skill",
        },
    )
    graph.add_edge("generate_problem", END)
    graph.add_edge("hold_non_signal", END)
    graph.add_edge("advance_skill", END)
    graph.add_edge("new_problem", END)
    graph.add_edge("retry_problem", END)
    graph.add_edge("demote_skill", END)
    graph.add_edge("end_session", END)

    return graph


app = build_graph().compile()
