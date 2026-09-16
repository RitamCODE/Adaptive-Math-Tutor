from fastapi.testclient import TestClient

from backend.api import _NARRATIVE_CONTEXT, _SESSIONS, app
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


def test_reward_narrative_context_not_queued_on_ordinary_correct_answer():
    # Touchpoint 3 ("effort-aware reward framing") must fire at the mastery
    # moment only, not per problem (CLAUDE.md). Under the real BKT constants a
    # correct answer almost always crosses the 0.8 mastery threshold outright
    # (p_init=0.3 jumps to ~0.9 on one correct answer), so to exercise the
    # "still short of mastery" branch this pins the in-memory session mastery
    # well below the ~0.153 pre-answer level that would cross 0.8, then
    # submits a correct answer and confirms next_action stays "new_problem".
    start = client.post("/sessions", json={"student_id": "reward-gate-1"})
    session_id = start.json()["session_id"]
    problem = _SESSIONS[session_id].current_problem
    correct_answer = problem.correct_answer
    _SESSIONS[session_id] = _SESSIONS[session_id].model_copy(
        update={"skill_mastery": {problem.skill_tag: 0.05}}
    )

    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": correct_answer, "time_taken_sec": 3.0},
    )
    assert response.json()["next_action"] == "new_problem"
    assert response.json()["skill_mastery"][problem.skill_tag] < 0.8
    assert "reward" not in _NARRATIVE_CONTEXT[session_id]


def test_reward_narrative_context_queued_on_advance_skill():
    # A fresh session's very first correct answer masters that skill outright
    # under the real BKT constants (see above) and, since only one of the
    # four skills is mastered so far, routes to "advance_skill" rather than
    # "end_session" (which only fires once 2 skills are mastered).
    start = client.post("/sessions", json={"student_id": "reward-gate-2"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer

    response = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": correct_answer, "time_taken_sec": 3.0},
    )
    assert response.json()["next_action"] == "advance_skill"
    assert "reward" in _NARRATIVE_CONTEXT[session_id]


def test_prior_avg_time_sec_excludes_the_current_attempt():
    start = client.post("/sessions", json={"student_id": "prior-avg-1"})
    session_id = start.json()["session_id"]
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer
    wrong_answer = correct_answer + 1

    first = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": wrong_answer, "time_taken_sec": 4.0},
    )
    # No prior attempts on this skill yet this session - nothing to compare to.
    assert first.json()["feedback"]["prior_avg_time_sec"] is None

    second = client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": correct_answer, "time_taken_sec": 2.0},
    )
    # The one prior attempt (the wrong one above) averaged 4.0s - the current
    # 2.0s submission must not be folded into that average.
    assert second.json()["feedback"]["prior_avg_time_sec"] == 4.0


def test_unknown_session_returns_404():
    response = client.get("/sessions/does-not-exist")
    assert response.status_code == 404


def test_seed_new_behaves_like_a_plain_start():
    response = client.post("/sessions/seed/new", json={"student_id": "seed-new"})
    assert response.status_code == 200
    body = response.json()
    assert body["current_problem"]["skill_tag"] == "addition_no_carry"
    assert body["skill_mastery"] == {}
    assert body["misconception_log"] == []


def test_seed_struggling_has_low_mastery_and_a_prior_misconception():
    response = client.post("/sessions/seed/struggling", json={"student_id": "seed-struggling"})
    assert response.status_code == 200
    body = response.json()

    assert body["current_problem"]["skill_tag"] == "addition_carry"
    assert "correct_answer" not in body["current_problem"]
    assert body["skill_mastery"]["addition_carry"] < 0.4
    assert len(body["misconception_log"]) == 1
    assert body["misconception_log"][0]["bug_type"] == "add_concat_no_carry"
    assert body["attempt_number"] == 1


def test_seed_fluent_has_high_mastery_above_the_fading_band():
    response = client.post("/sessions/seed/fluent", json={"student_id": "seed-fluent"})
    assert response.status_code == 200
    body = response.json()

    assert body["current_problem"]["skill_tag"] == "addition_carry"
    assert body["skill_mastery"]["addition_carry"] > 0.7
    assert body["misconception_log"] == []


def test_seed_unknown_name_returns_404():
    response = client.post("/sessions/seed/nope", json={"student_id": "s"})
    assert response.status_code == 404


def test_restore_reinstalls_state_under_the_same_session_id():
    seeded = client.post("/sessions/seed/struggling", json={"student_id": "restore-me"})
    session_id = seeded.json()["session_id"]

    restore_body = {
        "student_id": "restore-me",
        "skill_mastery": {"addition_no_carry": 0.9, "addition_carry": 0.3},
        "misconception_log": [
            {"skill": "addition_carry", "bug_type": "add_concat_no_carry", "timestamp": "2026-09-14T00:00:00Z"}
        ],
        "engagement": {"streak": 0, "xp": 10, "frustration_signal": False, "consecutive_wrong": 1},
        "problems_completed": 3,
        "quest_length": 10,
        "active_skill": "addition_carry",
    }
    response = client.post(f"/sessions/{session_id}/restore", json=restore_body)
    assert response.status_code == 200
    body = response.json()

    assert body["session_id"] == session_id
    assert body["skill_mastery"]["addition_carry"] == 0.3
    assert len(body["misconception_log"]) == 1
    # a fresh problem is generated rather than the pre-restore one recovered
    assert body["attempt_number"] == 1
    assert body["current_problem"]["skill_tag"] == "addition_carry"


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
