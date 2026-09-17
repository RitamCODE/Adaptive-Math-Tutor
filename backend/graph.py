"""LangGraph wiring for the adaptive-tutor turn cycle.

Topology (see CLAUDE.md's routing spec):

    START --[route_from_start]--> "generate_problem"     (no answer pending: bootstrap/regenerate)
    START --[route_from_start]--> "grade_and_diagnose"    (an answer is pending)

    "grade_and_diagnose" --[route_after_diagnosis]--> "hold_non_signal"     (blank/rapid-guess)
    "grade_and_diagnose" --[route_after_diagnosis]--> "build_remediation"   (signal-bearing, wrong)
    "grade_and_diagnose" --[route_after_diagnosis]--> "update_mastery"      (signal-bearing, correct)

    "build_remediation" -> "update_mastery"   (always continues on; runs for every wrong
                                                signal-bearing attempt, 1 through 3 — attempt 3's
                                                "worked solution" is just Remediation with
                                                reveal_answer=True, not a separate path)

    "update_mastery" -> "decide_engagement"   (runs on every signal-bearing submission,
                                                correct or wrong, so consecutive_wrong tracks
                                                the fatigue stop regardless of outcome)

    "decide_engagement" --[route_after_engagement]--> "end_session"      (fatigue stop, quest
                                                                          length, or both parent
                                                                          skills mastered)
    "decide_engagement" --[route_after_engagement]--> "advance_skill"    (correct, skill mastered:
                                                                          at or above threshold
                                                                          after each of the last
                                                                          3 signal-bearing answers)
    "decide_engagement" --[route_after_engagement]--> "new_problem"      (correct, otherwise, including
                                                                          progress toward a pending resurface)
    "decide_engagement" --[route_after_engagement]--> "resurface_skill"  (correct, 2nd correct answer on
                                                                          the prerequisite of a demoted skill)
    "decide_engagement" --[route_after_engagement]--> "retry_problem"    (wrong, attempt < 3)
    "decide_engagement" --[route_after_engagement]--> "demote_skill"     (wrong, attempt >= 3, not
                                                                          already resurfaced once)
    "decide_engagement" --[route_after_engagement]--> "end_session"      (wrong, attempt >= 3, on a
                                                                          skill already resurfaced once:
                                                                          end on the lower-level win
                                                                          instead of grinding further)

    "generate_problem", "hold_non_signal", "end_session", "advance_skill",
    "new_problem", "retry_problem", "demote_skill", "resurface_skill" -> END

No checkpointer/persistence: a scripted driver threads `SessionState` through
Python by calling `graph.invoke()` once per turn, feeding a fresh
`last_response` in between calls to simulate a student's answer arriving.
"""

from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from backend.models.bkt import (
    BKTParams,
    MASTERY_THRESHOLD,
    is_mastered,
    update_mastery as bkt_update_mastery,
)
from backend.models.state import LastResponse, Misconception, SessionState
from backend.nodes.curriculum import select_next_skill
from backend.nodes.diagnosis import grade_and_diagnose as pure_grade_and_diagnose
from backend.nodes.engagement import decide_engagement as pure_decide_engagement
from backend.nodes.problem_gen import generate_problem as pure_generate_problem
from backend.nodes.remediation import build_remediation as pure_build_remediation
from backend.skills._arithmetic import parse_operands
from backend.skills._difficulty_ladder import NARROWEST_TIER_SKILLS, WIDTH_LADDER, advance_digit_level
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH

# Digit-width no longer comes from raw BKT mastery (see _difficulty_ladder.py's
# module docstring for why). generate_problem's `difficulty: float` parameter
# is kept unchanged per CLAUDE.md's node spec, but it now just encodes which
# of bucket()'s three thresholds a skill's ladder tier should resolve to, so
# bucket() and every skill's own _WIDTH_BY_BUCKET table keep working
# unchanged. A flat tier-index -> float table doesn't work here: a 2-tier
# skill's (addition_carry/subtraction_borrow) tier 1 is its own top/widest
# tier and must resolve to "hard", not "medium" — so the tier is placed
# relative to its own skill's ladder length instead.
_BUCKET_DIFFICULTY = {"easy": 0.2, "medium": 0.5, "hard": 0.8}


def _difficulty_for_level(digit_level: dict[str, int], skill: str) -> float:
    ladder = WIDTH_LADDER.get(skill, [1, 2, 3])
    tier = max(0, min(digit_level.get(skill, 0), len(ladder) - 1))
    if len(ladder) <= 1 or tier == len(ladder) - 1:
        bucket_name = "hard"
    elif tier == 0:
        bucket_name = "easy"
    else:
        bucket_name = "medium"
    return _BUCKET_DIFFICULTY[bucket_name]


def _difficulty_for(state: SessionState, skill: str) -> float:
    return _difficulty_for_level(state.digit_level, skill)


def _combo_hint_for(state: SessionState, skill: str) -> dict | None:
    """Only meaningful for the two skills whose narrowest tier is 1-digit,
    and only while a skill is still at that tier (digit_level 0). Tells
    generate_problem whether the next 1-digit problem should be trivial (an
    operand is 0) or non-trivial."""
    if skill not in NARROWEST_TIER_SKILLS or state.digit_level.get(skill, 0) != 0:
        return None
    want_trivial = state.digit_level_run.get(skill, 0) == 0
    return {"seen": state.seen_combos.get(skill, []), "want_trivial": want_trivial}


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
        else select_next_skill(state, DEFAULT_SKILL_GRAPH)
    )
    problem = pure_generate_problem(skill, _difficulty_for(state, skill), combo_hint=_combo_hint_for(state, skill))
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
        "last_diagnosis": diagnosis,
    }


def build_remediation_node(state: SessionState) -> dict:
    """Reached only for a wrong, signal-bearing answer (see route_after_diagnosis).

    Runs for attempts 1 through 3 alike — grade_and_diagnose already bakes
    the visual in at attempt >= 2 and reveal_answer=True at attempt >= 3 into
    last_diagnosis, so the attempt-3 "worked solution" moment is just this
    same node's output with reveal_answer set, not a separate code path.
    """
    remediation = pure_build_remediation(state.last_diagnosis, state.attempt_number)
    return {"remediation": remediation}


def hold_non_signal_node(state: SessionState) -> dict:
    """Blank or rapid-guess submission: not a knowledge signal. Attempt
    counter, attempt_history, skill_mastery, and engagement all stay put."""
    return {"next_action": "retry_problem"}


def update_mastery_node(state: SessionState) -> dict:
    """Skips the BKT update for `digit_reversal`: CLAUDE.md says the
    underlying skill is intact and mastery must not be penalized, even
    though the wrong answer still consumes an attempt and goes through the
    normal retry ladder (handled elsewhere — this node only owns mastery).

    Also tracks progress toward re-surfacing a demoted skill (revision-plan
    7.3): a correct, signal-bearing answer on the prerequisite of
    `state.pending_resurface` counts toward the two answers required before
    the demoted skill comes back. This has to happen here, before
    route_after_engagement runs, so the router sees this turn's count.
    """
    updates: dict = {}
    skill = state.current_problem.skill_tag
    if not (state.attempt_history and state.attempt_history[-1][1] == "digit_reversal"):
        updated_mastery = bkt_update_mastery(
            state.skill_mastery, skill, state.last_response.correct, BKTParams()
        )
        updates["skill_mastery"] = updated_mastery

        # The sustained-mastery run: how many consecutive signal-bearing
        # answers on this skill have left it at or above the threshold. Any
        # answer that drops it back below resets the run to zero. Only
        # signal-bearing answers reach this node at all (blank and
        # rapid-guess submissions are routed to hold_non_signal), and the
        # digit_reversal branch above skips the run for the same reason it
        # skips the BKT update: the underlying skill is intact, so that
        # answer neither penalizes nor rewards mastery.
        run = state.mastery_run.get(skill, 0)
        updates["mastery_run"] = {
            **state.mastery_run,
            skill: run + 1 if updated_mastery[skill] >= MASTERY_THRESHOLD else 0,
        }

    # Digit-width tracking is a separate axis from BKT mastery (see
    # _difficulty_ladder.py), so unlike the block above it runs unconditionally
    # on every signal-bearing answer, including a digit_reversal one.
    combo = None
    if skill in NARROWEST_TIER_SKILLS:
        a, _op, b = parse_operands(state.current_problem.question)
        combo = (a, b)
    updates.update(
        advance_digit_level(
            skill=skill,
            digit_level=state.digit_level,
            digit_level_run=state.digit_level_run,
            seen_combos=state.seen_combos,
            correct=state.last_response.correct,
            combo=combo,
        )
    )

    if (
        state.pending_resurface is not None
        and state.last_response.correct
        and state.current_problem.skill_tag == DEFAULT_SKILL_GRAPH.prerequisites_of(state.pending_resurface)[0]
    ):
        updates["resurface_progress"] = state.resurface_progress + 1

    return updates


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
    new_skill = select_next_skill(state, DEFAULT_SKILL_GRAPH)
    problem = pure_generate_problem(
        new_skill, _difficulty_for(state, new_skill), combo_hint=_combo_hint_for(state, new_skill)
    )
    return {
        "current_problem": problem, "next_action": "advance_skill", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
    }


def new_problem_node(state: SessionState) -> dict:
    """Correct answer, mastery still below threshold: same skill, new problem."""
    skill = state.current_problem.skill_tag
    problem = pure_generate_problem(skill, _difficulty_for(state, skill), combo_hint=_combo_hint_for(state, skill))
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

    Queues the demoted skill for a one-time resurface (revision-plan 7.3),
    unless a resurface is already pending for a different skill — in that
    rare double-demotion case, the first pending resurface wins and this
    one is not tracked, rather than building a stack of pending resurfaces.
    """
    skill = state.current_problem.skill_tag
    prereqs = DEFAULT_SKILL_GRAPH.prerequisites_of(skill)
    if not prereqs:
        problem = pure_generate_problem(skill, _difficulty_for(state, skill), combo_hint=_combo_hint_for(state, skill))
        return {
            "current_problem": problem, "next_action": "new_problem", "last_response": None,
            "attempt_number": 1, "attempt_history": [],
            "problems_completed": state.problems_completed + 1,
            }

    target = prereqs[0]
    problem = pure_generate_problem(
        target, _difficulty_for(state, target), combo_hint=_combo_hint_for(state, target)
    )
    updates = {
        "current_problem": problem, "next_action": "demote_skill", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
    }
    if state.pending_resurface is None:
        updates["pending_resurface"] = skill
        updates["resurface_progress"] = 0
    return updates


def resurface_skill_node(state: SessionState) -> dict:
    """Two correct answers on the prerequisite since a demotion: bring the
    demoted skill back once (revision-plan 7.3). Records the skill in
    `resurfaced_skills` so a second attempt-3 failure on it ends the quest
    on the lower-level win instead of demoting-and-resurfacing again.

    `next_action` is "new_problem", not "advance_skill" — this skill's
    mastery is still below threshold, so treating this as a mastery advance
    would incorrectly fire the mastery-moment LLM narrative.
    """
    skill = state.pending_resurface
    problem = pure_generate_problem(skill, _difficulty_for(state, skill), combo_hint=_combo_hint_for(state, skill))
    return {
        "current_problem": problem, "next_action": "new_problem", "last_response": None,
        "attempt_number": 1, "attempt_history": [],
        "problems_completed": state.problems_completed + 1,
        "pending_resurface": None,
        "resurface_progress": 0,
        "resurfaced_skills": [*state.resurfaced_skills, skill],
    }


def end_session_node(state: SessionState) -> dict:
    return {"current_problem": None, "next_action": "end_session"}


# --- router functions (no state mutation; pick the next node name) ---


def route_from_start(state: SessionState) -> str:
    return "generate_problem" if state.last_response is None else "grade_and_diagnose"


def route_after_diagnosis(state: SessionState) -> str:
    if not _is_signal(state.last_response):
        return "hold_non_signal"
    return "update_mastery" if state.last_response.correct else "build_remediation"


def route_after_engagement(state: SessionState) -> str:
    if state.engagement.consecutive_wrong >= 4:
        return "end_session"

    correct = state.last_response.correct
    if not correct and state.attempt_number < 3:
        return "retry_problem"

    # The quest ends when the curriculum is genuinely finished — every
    # sub-skill of both parent skills past the sustained-mastery gate — or
    # when the session runs out of problems. (The fatigue stop above is the
    # third ending.) This deliberately replaces an older "any 2 skills
    # mastered" count, which, because the DAG unlocks strictly in order,
    # was in practice a synonym for "both addition sub-skills done" and made
    # subtraction unreachable by play.
    next_completed = state.problems_completed + 1
    if next_completed >= state.quest_length or DEFAULT_SKILL_GRAPH.all_groups_mastered(state):
        return "end_session"

    if correct:
        skill = state.current_problem.skill_tag
        if state.pending_resurface is not None and skill == DEFAULT_SKILL_GRAPH.prerequisites_of(state.pending_resurface)[0]:
            # Two correct answers on the prerequisite, regardless of its own
            # mastery, bring the demoted skill back — deliberately bypassing
            # the mastery-threshold check below, since that prerequisite is
            # typically already mastered (that's how the student reached the
            # now-demoted skill in the first place), which would otherwise
            # resurface after just one correct answer via "advance_skill".
            return "resurface_skill" if state.resurface_progress >= 2 else "new_problem"
        return "advance_skill" if is_mastered(skill, state) else "new_problem"

    if state.current_problem.skill_tag in state.resurfaced_skills:
        # Already used its one resurface chance and failed again: end the
        # quest on the lower-level win rather than demoting further.
        return "end_session"
    return "demote_skill"


def build_graph() -> StateGraph:
    graph = StateGraph(SessionState)

    graph.add_node("generate_problem", generate_problem_node)
    graph.add_node("grade_and_diagnose", grade_and_diagnose_node)
    graph.add_node("hold_non_signal", hold_non_signal_node)
    graph.add_node("build_remediation", build_remediation_node)
    graph.add_node("update_mastery", update_mastery_node)
    graph.add_node("decide_engagement", decide_engagement_node)
    graph.add_node("advance_skill", advance_skill_node)
    graph.add_node("new_problem", new_problem_node)
    graph.add_node("retry_problem", retry_problem_node)
    graph.add_node("demote_skill", demote_skill_node)
    graph.add_node("resurface_skill", resurface_skill_node)
    graph.add_node("end_session", end_session_node)

    graph.add_conditional_edges(
        START,
        route_from_start,
        {"generate_problem": "generate_problem", "grade_and_diagnose": "grade_and_diagnose"},
    )
    graph.add_conditional_edges(
        "grade_and_diagnose",
        route_after_diagnosis,
        {
            "update_mastery": "update_mastery",
            "hold_non_signal": "hold_non_signal",
            "build_remediation": "build_remediation",
        },
    )
    graph.add_edge("build_remediation", "update_mastery")
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
            "resurface_skill": "resurface_skill",
        },
    )
    graph.add_edge("generate_problem", END)
    graph.add_edge("hold_non_signal", END)
    graph.add_edge("advance_skill", END)
    graph.add_edge("new_problem", END)
    graph.add_edge("retry_problem", END)
    graph.add_edge("demote_skill", END)
    graph.add_edge("resurface_skill", END)
    graph.add_edge("end_session", END)

    return graph


app = build_graph().compile()
