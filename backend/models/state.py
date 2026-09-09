"""Pydantic data models for session/problem state.

Only `Problem` is defined here so far — it's what the skill-graph and
problem-template task (this one) needs. The remaining models from
CLAUDE.md (`LastResponse`, `Misconception`, `EngagementState`,
`SessionState`) belong to the tasks that actually consume them (BKT/bug
rules, engagement, LangGraph wiring) and will be added there.
"""

from pydantic import BaseModel


class Problem(BaseModel):
    question: str
    correct_answer: int
    skill_tag: str
    difficulty: float
