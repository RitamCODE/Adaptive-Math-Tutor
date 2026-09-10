"""Pydantic data models for session/problem state.

`Problem` and `DiagnosisResult` are defined here — the BKT/bug-rules task
needs both (the latter is `grade_and_diagnose`'s return type, not spelled
out in CLAUDE.md's data-model list). `LastResponse`, `Misconception`,
`EngagementState`, and `SessionState` belong to the tasks that actually
consume them (engagement, LangGraph wiring) and will be added there.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Problem(BaseModel):
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float


class DiagnosisResult(BaseModel):
    correct: bool
    bug_type: str | None = None


class LastResponse(BaseModel):
    answer: int
    correct: bool  # provisional when submitted; grade_and_diagnose_node overwrites it
    time_taken_sec: float


class Misconception(BaseModel):
    skill: str
    bug_type: str
    timestamp: datetime


class EngagementState(BaseModel):
    streak: int
    xp: int
    frustration_signal: bool


class SessionState(BaseModel):
    student_id: str
    session_id: str
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    current_problem: Problem | None
    last_response: LastResponse | None
    engagement: EngagementState
    # "hint" is not reachable in this task — reserved for a future node
    next_action: Literal["new_problem", "repeat_skill", "advance_skill", "hint"]
