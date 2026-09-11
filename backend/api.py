"""Thin FastAPI layer wrapping the compiled LangGraph turn cycle for a browser client.

No grading/mastery/curriculum logic lives here — only wiring and response
shaping. `SessionState`'s schema (backend/models/state.py) is specified
verbatim in CLAUDE.md and is never modified; anything the HTTP layer needs
beyond that schema (feedback, per-skill lock state) lives in the API-only
models below.

Session state lives in an in-memory dict keyed by session_id. This matches
CLAUDE.md's non-goal of "no persistence beyond current session/local
storage" — but it means state is lost on restart and isn't shared across
processes, so run uvicorn with a single worker only.
"""

from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.graph import app as graph_app
from backend.llm import narrative
from backend.models.bkt import MASTERY_THRESHOLD
from backend.models.state import EngagementState, LastResponse, Problem, SessionState
from backend.nodes.diagnosis import grade_and_diagnose as pure_grade_and_diagnose
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH

app = FastAPI(title="Adaptive Math Tutor API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_SESSIONS: dict[str, SessionState] = {}

# Narrative/attempt-tracking state, same non-persistence caveat as _SESSIONS.
_FLAVOR_TEXT: dict[str, str | None] = {}
_ATTEMPTS: dict[str, dict[str, dict]] = {}


class StartSessionRequest(BaseModel):
    student_id: str


class AnswerRequest(BaseModel):
    answer: int
    time_taken_sec: float


class ProblemOut(BaseModel):
    question: str
    skill_tag: str
    difficulty: float
    flavor_text: str | None = None


class SkillProgress(BaseModel):
    skill: str
    mastery: float
    unlocked: bool
    mastered: bool


class SessionResponse(BaseModel):
    session_id: str
    student_id: str
    current_problem: ProblemOut | None
    engagement: EngagementState
    skill_progress: list[SkillProgress]
    next_action: str


class Feedback(BaseModel):
    correct: bool
    bug_type: str | None
    correct_answer: int
    skill_tag: str
    reward_narrative: str | None = None
    mastery_narrative: str | None = None
    boss_battle_narrative: str | None = None


class AnswerResponse(SessionResponse):
    feedback: Feedback


def _skill_progress(mastery: dict[str, float]) -> list[SkillProgress]:
    return [
        SkillProgress(
            skill=skill,
            mastery=mastery.get(skill, 0.0),
            unlocked=DEFAULT_SKILL_GRAPH.is_unlocked(skill, mastery, MASTERY_THRESHOLD),
            mastered=mastery.get(skill, 0.0) >= MASTERY_THRESHOLD,
        )
        for skill in DEFAULT_SKILL_GRAPH.topological_order()
    ]


def _to_session_response(state: SessionState) -> SessionResponse:
    problem = (
        ProblemOut(
            question=state.current_problem.question,
            skill_tag=state.current_problem.skill_tag,
            difficulty=state.current_problem.difficulty,
            flavor_text=_FLAVOR_TEXT.get(state.session_id),
        )
        if state.current_problem is not None
        else None
    )
    return SessionResponse(
        session_id=state.session_id,
        student_id=state.student_id,
        current_problem=problem,
        engagement=state.engagement,
        skill_progress=_skill_progress(state.skill_mastery),
        next_action=state.next_action,
    )


def _refresh_flavor_text(session_id: str, problem: Problem | None) -> None:
    """Touchpoint 1: cache a one-line story wrapper for the current problem
    so repeated GETs don't re-invoke the LLM or return a different story."""
    if problem is None:
        _FLAVOR_TEXT.pop(session_id, None)
        return
    _FLAVOR_TEXT[session_id] = narrative.flavor_word_problem(
        problem.question, problem.correct_answer, problem.skill_tag, problem.difficulty
    )


def _get_session(session_id: str) -> SessionState:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return state


@app.post("/sessions", response_model=SessionResponse)
def start_session(req: StartSessionRequest) -> SessionResponse:
    initial_state = SessionState(
        student_id=req.student_id,
        session_id=uuid4().hex,
        skill_mastery={},
        misconception_log=[],
        current_problem=None,
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False),
        next_action="new_problem",
    )
    new_state = SessionState.model_validate(graph_app.invoke(initial_state.model_dump()))
    _SESSIONS[new_state.session_id] = new_state
    _refresh_flavor_text(new_state.session_id, new_state.current_problem)
    return _to_session_response(new_state)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    return _to_session_response(_get_session(session_id))


@app.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
def submit_answer(session_id: str, req: AnswerRequest) -> AnswerResponse:
    state = _get_session(session_id)
    if state.current_problem is None:
        raise HTTPException(status_code=400, detail="no problem is currently active for this session")

    problem = state.current_problem
    diagnosis = pure_grade_and_diagnose(problem, req.answer)

    state = state.model_copy(
        update={
            "last_response": LastResponse(
                answer=req.answer, correct=False, time_taken_sec=req.time_taken_sec
            )
        }
    )
    new_state = SessionState.model_validate(graph_app.invoke(state.model_dump()))
    _SESSIONS[session_id] = new_state
    _refresh_flavor_text(session_id, new_state.current_problem)

    skill_attempts = _ATTEMPTS.setdefault(session_id, {})
    record = skill_attempts.setdefault(problem.skill_tag, {"count": 0, "total_time_sec": 0.0})
    record["count"] += 1
    record["total_time_sec"] += req.time_taken_sec

    reward_narrative = None
    if diagnosis.correct:
        reward_narrative = narrative.effort_reward_narrative(
            problem.skill_tag, record["count"], record["total_time_sec"] / record["count"]
        )

    mastery_narrative = None
    boss_battle_narrative = None
    if new_state.next_action == "advance_skill":
        mastered_skill = problem.skill_tag
        skill_misconceptions = [
            m for m in new_state.misconception_log if m.skill == mastered_skill
        ]
        mastery_narrative = narrative.mastery_moment_narrative(
            mastered_skill, skill_misconceptions, record["count"]
        )
        if new_state.current_problem is not None:
            boss_battle_narrative = narrative.boss_battle_narrative(
                new_state.current_problem.skill_tag
            )

    base = _to_session_response(new_state)
    return AnswerResponse(
        **base.model_dump(),
        feedback=Feedback(
            correct=diagnosis.correct,
            bug_type=diagnosis.bug_type,
            correct_answer=problem.correct_answer,
            skill_tag=problem.skill_tag,
            reward_narrative=reward_narrative,
            mastery_narrative=mastery_narrative,
            boss_battle_narrative=boss_battle_narrative,
        ),
    )
