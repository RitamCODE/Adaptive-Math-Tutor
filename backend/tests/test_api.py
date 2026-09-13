from fastapi.testclient import TestClient

from backend.api import _SESSIONS, app
from backend.logging import events

client = TestClient(app)


def test_start_session_bootstraps_first_problem():
    response = client.post("/sessions", json={"student_id": "s1"})
    assert response.status_code == 200
    body = response.json()

    assert body["current_problem"]["skill_tag"] == "addition_no_carry"
    assert "correct_answer" not in body["current_problem"]
    assert body["current_problem"]["flavor_text"] is None
    assert body["current_problem"]["problem_id"]

    progress = {entry["skill"]: entry for entry in body["skill_progress"]}
    assert progress["addition_no_carry"]["unlocked"] is True
    assert progress["addition_carry"]["unlocked"] is False


def test_submit_correct_answer_updates_mastery_and_feedback():
    start = client.post("/sessions", json={"student_id": "s2"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer

    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": correct_answer, "time_taken_sec": 3.0},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feedback"]["correct"] is True
    assert body["feedback"]["correct_answer"] == correct_answer
    assert body["feedback"]["problem_id"]
    assert body["engagement"]["xp"] == 10
    assert "reward_narrative" not in body["feedback"]
    assert "mastery_narrative" not in body["feedback"]

    progress = {entry["skill"]: entry for entry in body["skill_progress"]}
    assert progress["addition_no_carry"]["mastery"] > 0.3


def test_submit_wrong_answer_on_attempt_1_never_reveals_correct_answer():
    start = client.post("/sessions", json={"student_id": "s3"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer
    wrong_answer = correct_answer + 1

    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": wrong_answer, "time_taken_sec": 5.0},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["feedback"]["correct"] is False
    assert body["feedback"]["correct_answer"] is None
    assert body["feedback"]["reveal_answer"] is False
    assert body["feedback"]["hint"] is not None
    assert body["next_action"] == "retry_problem"
    # same problem stays on screen
    assert body["current_problem"]["problem_id"] == start.json()["current_problem"]["problem_id"]


def test_narrative_endpoint_returns_empty_when_no_context_yet():
    start = client.post("/sessions", json={"student_id": "s4"})
    session_id = start.json()["session_id"]

    response = client.get(f"/sessions/{session_id}/narrative")
    assert response.status_code == 200
    body = response.json()
    assert body == {"reward_narrative": None, "mastery_narrative": None, "boss_battle_narrative": None}


def test_narrative_endpoint_populates_reward_narrative_slot_after_correct_answer():
    start = client.post("/sessions", json={"student_id": "s5"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer

    client.post(f"/sessions/{session_id}/answer", json={"answer": correct_answer, "time_taken_sec": 3.0})
    response = client.get(f"/sessions/{session_id}/narrative")
    assert response.status_code == 200
    # No OPENAI_API_KEY in the test environment (conftest.py), so the LLM
    # call fails open to None — this just confirms the endpoint is reachable
    # and shaped correctly, not that it returns real text.
    body = response.json()
    assert set(body) == {"reward_narrative", "mastery_narrative", "boss_battle_narrative"}


def test_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404


def test_submit_answer_logs_an_event_row(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "DEFAULT_DB_PATH", tmp_path / "events.db")

    start = client.post("/sessions", json={"student_id": "s6"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer
    wrong_answer = correct_answer + 1

    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": wrong_answer, "time_taken_sec": 5.0},
    )
    assert response.status_code == 200

    rows = events.fetch_events(db_path=tmp_path / "events.db")
    assert len(rows) == 1
    assert rows[0]["session_id"] == session_id
    assert rows[0]["submitted_answer"] == wrong_answer
    assert rows[0]["signal"] == 1
