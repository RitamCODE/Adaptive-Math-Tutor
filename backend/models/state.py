"""Pydantic data models for session/problem state.

`Problem` and `DiagnosisResult` are defined here — the BKT/bug-rules task
needs both (the latter is `grade_and_diagnose`'s return type, not spelled
out in CLAUDE.md's data-model list). `LastResponse`, `Misconception`,
`EngagementState`, and `SessionState` belong to the tasks that actually
consume them (engagement, LangGraph wiring) and will be added there.
"""

from pydantic import BaseModel


class Problem(BaseModel):
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float


class DiagnosisResult(BaseModel):
    correct: bool
    bug_type: str | None = None
