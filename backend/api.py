"""Thin FastAPI layer wrapping the compiled LangGraph turn cycle for a browser client.

No grading/mastery/curriculum logic lives here — only wiring and response
shaping. `SessionState`'s schema (backend/models/state.py) is specified in
CLAUDE.md; anything the HTTP layer needs beyond that schema (feedback,
per-skill lock state) lives in the API-only models below. Grading itself
runs exactly once, inside the graph (`grade_and_diagnose_node` /
`build_remediation_node`) — this layer reads `last_diagnosis`/`remediation`
off the returned state rather than recomputing them.

Session state lives in an in-memory dict keyed by session_id. This matches
CLAUDE.md's non-goal of "no persistence beyond current session/local
storage" — but it means state is lost on restart and isn't shared across
processes, so run uvicorn with a single worker only.

Latency budget (CLAUDE.md constraint #6): `submit_answer` makes zero LLM
calls. The three narrative touchpoints that used to run synchronously here
now live behind a separate `GET /sessions/{id}/narrative`, which the
frontend fetches right after rendering the instant verdict.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.graph import _difficulty_for, app as graph_app
from backend.llm import narrative
from backend.logging import events
from backend.models.bkt import MASTERY_THRESHOLD
from backend.models.state import EngagementState, LastResponse, Misconception, Problem, SessionState
from backend.nodes.problem_gen import generate_problem
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
_FLAVOR_TEXT_PROBLEM_ID: dict[str, str] = {}
_ATTEMPTS: dict[str, dict[str, dict]] = {}
_NARRATIVE_CONTEXT: dict[str, dict] = {}
_NARRATIVE_CACHE: dict[str, tuple[str, "NarrativeOut"]] = {}


class StartSessionRequest(BaseModel):
    student_id: str


class RestoreRequest(BaseModel):
    """Body for POST /sessions/{id}/restore: the safe (no correct_answer)
    fields of a cached SessionResponse, sent back by the frontend when a
    GET /sessions/{id} 404s (the backend restarted and lost its in-memory
    session). See docs/CHECKLIST.md section J."""

    student_id: str
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    engagement: EngagementState
    problems_completed: int
    quest_length: int
    active_skill: str


class AnswerRequest(BaseModel):
    answer: int | None
    time_taken_sec: float


class ProblemOut(BaseModel):
    problem_id: str
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
    # Everything below is safe to expose (no correct_answer anywhere in it) and
    # exists so the frontend can cache a genuinely complete session snapshot in
    # localStorage, for both plain rehydration and restart recovery (see
    # /sessions/{id}/restore).
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    problems_completed: int
    quest_length: int
    attempt_number: int


class Feedback(BaseModel):
    problem_id: str
    correct: bool
    bug_type: str | None
    hint: str | None
    visual: str | None
    attempts_remaining: int
    reveal_answer: bool
    correct_answer: int | None = None  # never sent before attempt 3, per CLAUDE.md constraint #7
    skill_tag: str


class AnswerResponse(SessionResponse):
    feedback: Feedback


class NarrativeOut(BaseModel):
    reward_narrative: str | None = None
    mastery_narrative: str | None = None
    boss_battle_narrative: str | None = None


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
            problem_id=state.current_problem.problem_id,
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
        skill_mastery=state.skill_mastery,
        misconception_log=state.misconception_log,
        problems_completed=state.problems_completed,
        quest_length=state.quest_length,
        attempt_number=state.attempt_number,
    )


def _refresh_flavor_text(session_id: str, problem: Problem | None) -> None:
    """Touchpoint 1: cache a one-line story wrapper for the current problem.

    Off the submit-to-verdict critical path (CLAUDE.md constraint #6) —
    callers schedule this via BackgroundTasks rather than awaiting it, so
    the HTTP response never blocks on an LLM call. Skipped entirely when
    the problem hasn't changed (the retry-ladder case), since the same
    problem doesn't need a new story on every wrong attempt.
    """
    if problem is None:
        _FLAVOR_TEXT.pop(session_id, None)
        _FLAVOR_TEXT_PROBLEM_ID.pop(session_id, None)
        return
    if _FLAVOR_TEXT_PROBLEM_ID.get(session_id) == problem.problem_id:
        return
    _FLAVOR_TEXT_PROBLEM_ID[session_id] = problem.problem_id
    _FLAVOR_TEXT[session_id] = narrative.flavor_word_problem(
        problem.question, problem.correct_answer, problem.skill_tag, problem.difficulty
    )


def _get_session(session_id: str) -> SessionState:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return state


def _install_seeded_state(
    session_id: str,
    student_id: str,
    skill_mastery: dict[str, float],
    misconception_log: list[Misconception],
    engagement: EngagementState,
    problems_completed: int,
    quest_length: int,
    active_skill: str,
) -> SessionState:
    """Install a fully-formed session directly into `_SESSIONS`, without
    running it through the graph (the same "read the state back as-is"
    pattern `get_session` already relies on). Backs both the `struggling`/
    `fluent` demo seeds and post-restart recovery: a fresh, internally
    consistent `current_problem` is generated for `active_skill` so the
    session is immediately playable, but its `correct_answer` never has to
    pass through anything the client has touched.
    """
    difficulty = _difficulty_for(skill_mastery, active_skill)
    problem = generate_problem(active_skill, difficulty)
    state = SessionState(
        student_id=student_id,
        session_id=session_id,
        skill_mastery=skill_mastery,
        misconception_log=misconception_log,
        current_problem=problem,
        attempt_number=1,
        attempt_history=[],
        last_response=None,
        last_diagnosis=None,
        remediation=None,
        engagement=engagement,
        problems_completed=problems_completed,
        quest_length=quest_length,
        next_action="new_problem",
    )
    _SESSIONS[session_id] = state
    return state


# Fixed demo profiles for the `?seed=` frontend param (revision-plan Part 7.1).
# `new` needs no entry here: it's just today's ordinary blank start.
_SEED_PROFILES: dict[str, dict] = {
    "struggling": dict(
        skill_mastery={"addition_no_carry": 0.9, "addition_carry": 0.3},
        misconception_log=[
            Misconception(skill="addition_carry", bug_type="add_concat_no_carry", timestamp=datetime.now(timezone.utc))
        ],
        engagement=EngagementState(streak=0, xp=10, frustration_signal=False, consecutive_wrong=1),
        problems_completed=3,
        quest_length=10,
        active_skill="addition_carry",
    ),
    "fluent": dict(
        skill_mastery={"addition_no_carry": 1.0, "addition_carry": 0.85},
        misconception_log=[],
        engagement=EngagementState(streak=4, xp=120, frustration_signal=False, consecutive_wrong=0),
        problems_completed=6,
        quest_length=10,
        active_skill="addition_carry",
    ),
}


def _is_signal(answer: int | None, time_taken_sec: float) -> bool:
    return answer is not None and time_taken_sec >= 2.0


@app.post("/sessions", response_model=SessionResponse)
def start_session(req: StartSessionRequest, background_tasks: BackgroundTasks) -> SessionResponse:
    initial_state = SessionState(
        student_id=req.student_id,
        session_id=uuid4().hex,
        skill_mastery={},
        misconception_log=[],
        current_problem=None,
        last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
    )
    new_state = SessionState.model_validate(graph_app.invoke(initial_state.model_dump()))
    _SESSIONS[new_state.session_id] = new_state
    background_tasks.add_task(_refresh_flavor_text, new_state.session_id, new_state.current_problem)
    return _to_session_response(new_state)


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> SessionResponse:
    return _to_session_response(_get_session(session_id))


@app.post("/sessions/seed/{name}", response_model=SessionResponse)
def start_seeded_session(
    name: str, req: StartSessionRequest, background_tasks: BackgroundTasks
) -> SessionResponse:
    """`?seed=` demo entry point (revision-plan Part 7.1). `new` is just an
    ordinary blank start under its own route, so the frontend has one call
    shape regardless of which seed was requested; `struggling`/`fluent` are
    pre-populated via `_install_seeded_state`."""
    if name == "new":
        return start_session(req, background_tasks)
    profile = _SEED_PROFILES.get(name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"unknown seed profile: {name!r}")
    new_state = _install_seeded_state(session_id=uuid4().hex, student_id=req.student_id, **profile)
    background_tasks.add_task(_refresh_flavor_text, new_state.session_id, new_state.current_problem)
    return _to_session_response(new_state)


@app.post("/sessions/{session_id}/restore", response_model=SessionResponse)
def restore_session(
    session_id: str, req: RestoreRequest, background_tasks: BackgroundTasks
) -> SessionResponse:
    """Recovery path for docs/CHECKLIST.md section J: a browser holding a
    cached session snapshot hits a 404 on GET (the backend restarted and lost
    its in-memory `_SESSIONS`), and re-installs that snapshot under the same
    session_id it already has cached. Mastery, XP, streak, and misconception
    history all survive; the in-flight problem and attempt count do not,
    since the pre-restart problem's correct_answer was never sent to the
    client and can't be reconstructed (CLAUDE.md constraint #7) — a fresh
    problem on the same skill is generated instead."""
    new_state = _install_seeded_state(
        session_id=session_id,
        student_id=req.student_id,
        skill_mastery=req.skill_mastery,
        misconception_log=req.misconception_log,
        engagement=req.engagement,
        problems_completed=req.problems_completed,
        quest_length=req.quest_length,
        active_skill=req.active_skill,
    )
    background_tasks.add_task(_refresh_flavor_text, new_state.session_id, new_state.current_problem)
    return _to_session_response(new_state)


@app.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
def submit_answer(session_id: str, req: AnswerRequest, background_tasks: BackgroundTasks) -> AnswerResponse:
    state = _get_session(session_id)
    if state.current_problem is None:
        raise HTTPException(status_code=400, detail="no problem is currently active for this session")

    problem = state.current_problem

    state = state.model_copy(
        update={
            "last_response": LastResponse(answer=req.answer, correct=False, time_taken_sec=req.time_taken_sec)
        }
    )

    if not _is_signal(req.answer, req.time_taken_sec):
        # Non-signal submission: no grading call, no BKT update, no attempt consumed.
        new_state = SessionState.model_validate(graph_app.invoke(state.model_dump()))
        _SESSIONS[session_id] = new_state
        background_tasks.add_task(
            events.log_submission,
            session_id=session_id,
            student_id=state.student_id,
            problem_id=problem.problem_id,
            skill_tag=problem.skill_tag,
            question=problem.question,
            submitted_answer=req.answer,
            correct_answer=problem.correct_answer,
            attempt=state.attempt_number,
            correct=False,
            bug_type=None,
            signal=False,
            time_taken_sec=req.time_taken_sec,
        )
        feedback = Feedback(
            problem_id=problem.problem_id,
            correct=False,
            bug_type=None,
            hint=None,
            visual=None,
            attempts_remaining=max(0, 3 - state.attempt_number),
            reveal_answer=False,
            skill_tag=problem.skill_tag,
        )
        base = _to_session_response(new_state)
        return AnswerResponse(**base.model_dump(), feedback=feedback)

    new_state = SessionState.model_validate(graph_app.invoke(state.model_dump()))
    _SESSIONS[session_id] = new_state
    # grade_and_diagnose_node / build_remediation_node already ran grading
    # and remediation inside the graph above — last_diagnosis is always set
    # on a signal-bearing turn; remediation is set only when the answer was
    # wrong (None on a correct answer, since there's nothing to remediate).
    diagnosis = new_state.last_diagnosis
    remediation = new_state.remediation
    background_tasks.add_task(_refresh_flavor_text, session_id, new_state.current_problem)
    background_tasks.add_task(
        events.log_submission,
        session_id=session_id,
        student_id=state.student_id,
        problem_id=problem.problem_id,
        skill_tag=problem.skill_tag,
        question=problem.question,
        submitted_answer=req.answer,
        correct_answer=problem.correct_answer,
        attempt=state.attempt_number,
        correct=diagnosis.correct,
        bug_type=diagnosis.bug_type,
        signal=True,
        time_taken_sec=req.time_taken_sec,
    )

    skill_attempts = _ATTEMPTS.setdefault(session_id, {})
    record = skill_attempts.setdefault(problem.skill_tag, {"count": 0, "total_time_sec": 0.0})
    record["count"] += 1
    record["total_time_sec"] += req.time_taken_sec

    context_id = uuid4().hex
    narrative_context: dict = {}
    if diagnosis.correct:
        narrative_context["reward"] = {
            "skill_tag": problem.skill_tag,
            "attempt_count": record["count"],
            "avg_time_sec": record["total_time_sec"] / record["count"],
        }
    if new_state.next_action == "advance_skill":
        mastered_skill = problem.skill_tag
        narrative_context["mastery"] = {
            "skill": mastered_skill,
            "misconceptions": [m for m in new_state.misconception_log if m.skill == mastered_skill],
            "attempt_count": record["count"],
        }
        if new_state.current_problem is not None:
            narrative_context["boss_battle"] = {"skill": new_state.current_problem.skill_tag}
    _NARRATIVE_CONTEXT[session_id] = {"context_id": context_id, **narrative_context}

    base = _to_session_response(new_state)
    return AnswerResponse(
        **base.model_dump(),
        feedback=Feedback(
            problem_id=diagnosis.problem_id,
            correct=diagnosis.correct,
            bug_type=diagnosis.bug_type,
            hint=remediation.hint if remediation else None,
            visual=remediation.visual if remediation else None,
            attempts_remaining=diagnosis.attempts_remaining,
            reveal_answer=remediation.reveal_answer if remediation else False,
            correct_answer=problem.correct_answer
            if (diagnosis.correct or (remediation and remediation.reveal_answer))
            else None,
            skill_tag=problem.skill_tag,
        ),
    )


@app.get("/sessions/{session_id}/narrative", response_model=NarrativeOut)
def get_narrative(session_id: str) -> NarrativeOut:
    """Off the submit-to-verdict critical path (CLAUDE.md constraint #6).
    The frontend fetches this right after rendering the instant verdict from
    `submit_answer` and merges the result in when it resolves."""
    context = _NARRATIVE_CONTEXT.get(session_id)
    if context is None:
        return NarrativeOut()

    context_id = context["context_id"]
    cached = _NARRATIVE_CACHE.get(session_id)
    if cached is not None and cached[0] == context_id:
        return cached[1]

    result = NarrativeOut()
    if "reward" in context:
        reward = context["reward"]
        result.reward_narrative = narrative.effort_reward_narrative(
            reward["skill_tag"], reward["attempt_count"], reward["avg_time_sec"]
        )
    if "mastery" in context:
        mastery = context["mastery"]
        result.mastery_narrative = narrative.mastery_moment_narrative(
            mastery["skill"], mastery["misconceptions"], mastery["attempt_count"]
        )
    if "boss_battle" in context:
        result.boss_battle_narrative = narrative.boss_battle_narrative(context["boss_battle"]["skill"])

    _NARRATIVE_CACHE[session_id] = (context_id, result)
    return result
