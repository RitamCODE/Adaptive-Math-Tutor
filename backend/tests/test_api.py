from fastapi.testclient import TestClient

from backend.api import _NARRATIVE_CONTEXT, _SESSIONS, app
from backend.logging import events
from backend.models.bkt import MASTERY_MIN_RUN
from backend.skills._arithmetic import parse_operands

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
    assert "mastery_card" not in _NARRATIVE_CONTEXT[session_id]


def _answer_current_problem_correctly(session_id: str) -> dict:
    """Submit the right answer to whatever problem the session is showing."""
    correct_answer = _SESSIONS[session_id].current_problem.correct_answer
    return client.post(
        f"/sessions/{session_id}/answer",
        json={"answer": correct_answer, "time_taken_sec": 3.0},
    ).json()


def test_reward_narrative_context_queued_on_advance_skill():
    # Mastery is sustained, not a single crossing: a skill counts as mastered
    # only once it has held at or above the threshold after each of the last
    # MASTERY_MIN_RUN signal-bearing answers. So the first two correct answers
    # stay on the same skill and only the third advances, taking the merged
    # mastery-card narrative (touchpoints 2-4) with it.
    start = client.post("/sessions", json={"student_id": "reward-gate-2"})
    session_id = start.json()["session_id"]

    for _ in range(MASTERY_MIN_RUN - 1):
        assert _answer_current_problem_correctly(session_id)["next_action"] == "new_problem"
        assert "mastery_card" not in _NARRATIVE_CONTEXT[session_id]

    body = _answer_current_problem_correctly(session_id)
    assert body["next_action"] == "advance_skill"
    assert "mastery_card" in _NARRATIVE_CONTEXT[session_id]


def test_skill_is_not_mastered_until_the_run_is_complete():
    """The UI's `mastered` flag and the router share one definition, so a
    skill that has crossed 0.8 but not held it reads as unmastered."""
    start = client.post("/sessions", json={"student_id": "run-gate-1"})
    session_id = start.json()["session_id"]
    skill = _SESSIONS[session_id].current_problem.skill_tag

    body = _answer_current_problem_correctly(session_id)
    assert body["skill_mastery"][skill] > 0.8  # crossed on answer one
    progress = {entry["skill"]: entry for entry in body["skill_progress"]}
    assert progress[skill]["mastered"] is False
    assert body["mastery_run"][skill] == 1


def test_quest_ends_only_when_both_parent_skills_are_mastered():
    """Playing a fresh session perfectly reaches subtraction and ends on
    curriculum completion, not on an "any 2 skills" count."""
    start = client.post("/sessions", json={"student_id": "full-quest-1"})
    session_id = start.json()["session_id"]

    skills_served = []
    for _ in range(40):
        skills_served.append(_SESSIONS[session_id].current_problem.skill_tag)
        body = _answer_current_problem_correctly(session_id)
        if body["next_action"] == "end_session":
            break
    else:
        assert False, "quest never ended"

    assert "subtraction_no_borrow" in skills_served
    assert "subtraction_borrow" in skills_served
    assert body["problems_completed"] < body["quest_length"]
    assert all(entry["mastered"] for entry in body["group_progress"])


def test_final_mastery_moment_still_queues_its_narrative():
    """route_after_engagement checks the quest-end conditions before the
    advance branch, so the answer that masters the last skill exits as
    end_session — it must still count as a mastery moment."""
    start = client.post("/sessions", json={"student_id": "finale-1"})
    session_id = start.json()["session_id"]

    for _ in range(40):
        body = _answer_current_problem_correctly(session_id)
        if body["next_action"] == "end_session":
            break

    assert "mastery_card" in _NARRATIVE_CONTEXT[session_id]


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


def test_seed_borrowing_starts_at_three_digit_subtraction_borrow():
    """The 'borrowing' seed's whole point is reaching multi-borrow problems
    immediately; it now sets digit_level explicitly rather than relying on
    mastery to imply digit-width (see _difficulty_ladder.py)."""
    response = client.post("/sessions/seed/borrowing", json={"student_id": "seed-borrowing"})
    assert response.status_code == 200
    body = response.json()

    assert body["current_problem"]["skill_tag"] == "subtraction_borrow"
    a, op, b = parse_operands(body["current_problem"]["question"])
    assert op == "-"
    assert max(len(str(a)), len(str(b))) == 3


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
