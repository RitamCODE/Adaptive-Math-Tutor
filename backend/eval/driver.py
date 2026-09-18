"""Drives one synthetic student through backend.graph.app, turn by turn,
with no FastAPI, no LLM, and no SQLite involved -- app.invoke() never touches
any of those (see the feasibility write-up this package implements). This
mirrors the calling pattern backend/tests/test_graph.py's own `_invoke`
helper already uses.

Whichever monkeypatches are active on `backend.graph` at call time (see
backend/eval/baseline.py) decide whether a call to `run_session` plays out
the real adaptive engine or the fixed-schedule, fixed-difficulty baseline --
this module is condition-agnostic and never imports baseline.py itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.eval.synthetic_learner import SKILLS, SyntheticLearner
from backend.graph import app
from backend.models.bkt import is_mastered as real_is_mastered
from backend.models.state import EngagementState, LastResponse, SessionState
from backend.skills._arithmetic import parse_operands

# A real session always ends via "end_session" well under this many turns
# (quest_length defaults to 16 problems, at most 3 attempts each, plus the
# occasional one-time resurface) -- this is only a guard against a
# misconfigured monkeypatch spinning forever.
MAX_TURNS = 500


def _digit_width(question: str) -> int:
    a, _op, b = parse_operands(question)
    return max(len(str(a)), len(str(b)))


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _initial_state(student_id: str) -> SessionState:
    return SessionState(
        student_id=student_id,
        session_id=f"sim_{student_id}",
        skill_mastery={},
        misconception_log=[],
        current_problem=None,
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
    )


@dataclass
class SessionResult:
    student_id: str
    final_state: SessionState
    turns: int
    problems_completed: int
    engine_mastered: dict[str, bool]  # the app's OWN is_mastered() verdict, per skill
    true_mastered: dict[str, bool]  # the synthetic learner's hidden ground truth, per skill


def run_session(learner: SyntheticLearner) -> SessionResult:
    state = _invoke(_initial_state(learner.student_id))
    turns = 0
    while state.next_action != "end_session" and turns < MAX_TURNS:
        problem = state.current_problem
        answer = learner.answer(problem.skill_tag, problem.correct_answer, _digit_width(problem.question))
        # `correct` is a required but provisional field the caller must not
        # rely on -- grade_and_diagnose_node is the sole source of truth and
        # overwrites it (CLAUDE.md's note on LastResponse.correct). Matches
        # the placeholder convention already used in test_graph.py.
        # time_taken_sec >= 2.0 keeps every submission signal-bearing: below
        # that, `_is_signal` in backend/graph.py routes to hold_non_signal
        # and the turn never reaches grading or BKT at all.
        response = LastResponse(answer=answer, correct=False, time_taken_sec=learner.rng.uniform(3.0, 12.0))
        state = state.model_copy(update={"last_response": response})
        state = _invoke(state)
        turns += 1

    if turns >= MAX_TURNS:
        raise RuntimeError(f"session for {learner.student_id!r} did not reach end_session within {MAX_TURNS} turns")

    engine_mastered = {skill: real_is_mastered(skill, state) for skill in SKILLS}
    true_mastered = {skill: learner.is_known(skill) for skill in SKILLS}
    return SessionResult(
        student_id=learner.student_id,
        final_state=state,
        turns=turns,
        problems_completed=state.problems_completed,
        engine_mastered=engine_mastered,
        true_mastered=true_mastered,
    )
