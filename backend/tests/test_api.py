from fastapi.testclient import TestClient

from backend.api import _SESSIONS, app

client = TestClient(app)


def test_start_session_bootstraps_first_problem():
    response = client.post("/sessions", json={"student_id": "s1"})
    assert response.status_code == 200
    body = response.json()

    assert body["current_problem"]["skill_tag"] == "addition_no_carry"
    assert "correct_answer" not in body["current_problem"]
    assert body["current_problem"]["flavor_text"] is None

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
    assert body["engagement"]["xp"] == 10
    assert body["feedback"]["reward_narrative"] is None
    assert body["feedback"]["mastery_narrative"] is None
    assert body["feedback"]["boss_battle_narrative"] is None

    progress = {entry["skill"]: entry for entry in body["skill_progress"]}
    assert progress["addition_no_carry"]["mastery"] > 0.3


def test_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404
