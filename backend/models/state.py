"""Pydantic data models for session/problem state.

Shapes here follow CLAUDE.md's Data Models section verbatim, plus `Remediation`
(referenced by CLAUDE.md's `build_remediation` node signature but never spelled
out in that section — filled in here as a subset of `DiagnosisResult`'s
remediation-facing fields).
"""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Problem(BaseModel):
    problem_id: str = Field(default_factory=lambda: f"p_{uuid4().hex[:10]}")
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float


class DiagnosisResult(BaseModel):
    problem_id: str
    correct: bool
    bug_type: str | None = None  # None when correct; "unclassified" when no detector fires
    hint: str | None = None
    visual: str | None = None  # e.g. "base10_blocks/ones_overflow"
    attempts_remaining: int = 0
    reveal_answer: bool = False  # True only on the third failed attempt
    signal: bool = True  # False for blank and rapid-guess submissions


class Remediation(BaseModel):
    hint: str | None
    visual: str | None
    reveal_answer: bool


class LastResponse(BaseModel):
    answer: int | None  # None for a blank submission
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
    consecutive_wrong: int  # signal-bearing wrong answers in a row


class SessionState(BaseModel):
    student_id: str
    session_id: str
    skill_mastery: dict[str, float]
    misconception_log: list[Misconception]
    current_problem: Problem | None
    attempt_number: int = 1  # 1-indexed, resets only on a new problem
    attempt_history: list[tuple[int | None, str | None]] = []  # (answer, bug_type) this problem
    last_response: LastResponse | None
    last_diagnosis: DiagnosisResult | None = None  # set by grade_and_diagnose_node; feeds build_remediation_node
    remediation: Remediation | None = None  # set by build_remediation_node on a wrong signal-bearing answer
    engagement: EngagementState
    problems_completed: int = 0
    quest_length: int = 10
    next_action: Literal[
        "new_problem", "retry_problem", "remediate",
        "advance_skill", "demote_skill", "end_session",
    ]
