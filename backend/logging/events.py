"""The event log: one SQLite row per submission (revision-plan 7.5).

Separate from LangSmith, which only traces the four LLM touchpoints.
`UNCLASSIFIED` rows in particular are what let the misconception catalog
grow from real data later (revision-plan Part 3). Not part of the
grading/mastery/curriculum path — this is pure I/O, called from `api.py` via
`BackgroundTasks` so it never sits on the submit-to-verdict critical path.

`DEFAULT_DB_PATH` is a module attribute rather than a bound default so tests
can `monkeypatch.setattr(events, "DEFAULT_DB_PATH", tmp_path / "events.db")`
without threading a path parameter through every caller.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "event_log.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    problem_id TEXT NOT NULL,
    skill_tag TEXT NOT NULL,
    question TEXT NOT NULL,
    submitted_answer INTEGER,
    correct_answer INTEGER NOT NULL,
    attempt INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    bug_type TEXT,
    signal INTEGER NOT NULL,
    time_taken_sec REAL NOT NULL
)
"""


def log_submission(
    *,
    session_id: str,
    student_id: str,
    problem_id: str,
    skill_tag: str,
    question: str,
    submitted_answer: int | None,
    correct_answer: int,
    attempt: int,
    correct: bool,
    bug_type: str | None,
    signal: bool,
    time_taken_sec: float,
    db_path: Path | None = None,
) -> None:
    """Append one row. Opens and closes its own connection — simplest safe
    option under uvicorn's threadpool, and cheap enough (a few ms) not to
    matter now that it's dispatched off the critical path regardless."""
    path = db_path if db_path is not None else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    try:
        conn.execute(_CREATE_TABLE)
        conn.execute(
            """
            INSERT INTO events (
                timestamp, session_id, student_id, problem_id, skill_tag, question,
                submitted_answer, correct_answer, attempt, correct, bug_type, signal, time_taken_sec
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                session_id,
                student_id,
                problem_id,
                skill_tag,
                question,
                submitted_answer,
                correct_answer,
                attempt,
                int(correct),
                bug_type,
                int(signal),
                time_taken_sec,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def fetch_events(db_path: Path | None = None) -> list[sqlite3.Row]:
    """Read back every logged row, oldest first. Test/inspection helper."""
    path = db_path if db_path is not None else DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_CREATE_TABLE)
        return conn.execute("SELECT * FROM events ORDER BY id").fetchall()
    finally:
        conn.close()
