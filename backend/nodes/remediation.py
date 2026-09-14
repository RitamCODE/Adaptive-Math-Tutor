"""The `build_remediation` node: pre-authorized by CLAUDE.md.

Today this is a direct projection of DiagnosisResult's remediation-facing
fields — diagnosis.py already owns the hint/visual lookup ("detectors are
code, copy is data"). It exists as a seam so remediation-specific shaping
(manipulative-payload detail, worked-solution steps at attempt 3) has a
place to grow without touching the pure grading path.

Wired into the LangGraph StateGraph as `build_remediation_node` (see
graph.py): reached whenever `grade_and_diagnose_node` produces a wrong,
signal-bearing `DiagnosisResult` (stored on `SessionState.last_diagnosis`),
and its output is stored on `SessionState.remediation`. `backend/api.py`
reads both fields to shape the HTTP response instead of calling this
function directly.
"""

from backend.models.state import DiagnosisResult, Remediation


def build_remediation(diagnosis: DiagnosisResult, attempt: int) -> Remediation:
    return Remediation(hint=diagnosis.hint, visual=diagnosis.visual, reveal_answer=diagnosis.reveal_answer)
