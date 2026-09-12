"""The `build_remediation` node: pre-authorized by CLAUDE.md.

Today this is a direct projection of DiagnosisResult's remediation-facing
fields — diagnosis.py already owns the hint/visual lookup ("detectors are
code, copy is data"). It exists as a seam so remediation-specific shaping
(manipulative-payload detail, worked-solution steps at attempt 3) has a
place to grow without touching the pure grading path.

Not wired into the LangGraph StateGraph: SessionState has no field to hold a
Remediation value, so there's nothing for a graph node to store. It's called
directly from backend/api.py to shape the HTTP response.
"""

from backend.models.state import DiagnosisResult, Remediation


def build_remediation(diagnosis: DiagnosisResult, attempt: int) -> Remediation:
    return Remediation(hint=diagnosis.hint, visual=diagnosis.visual, reveal_answer=diagnosis.reveal_answer)
