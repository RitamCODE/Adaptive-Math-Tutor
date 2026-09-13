from backend.logging import events


def test_log_submission_writes_a_signal_bearing_row(tmp_path):
    db_path = tmp_path / "events.db"

    events.log_submission(
        session_id="sess1",
        student_id="s1",
        problem_id="p_1",
        skill_tag="addition_carry",
        question="86 + 94",
        submitted_answer=1017,
        correct_answer=180,
        attempt=1,
        correct=False,
        bug_type="add_concat_no_carry",
        signal=True,
        time_taken_sec=6.2,
        db_path=db_path,
    )

    rows = events.fetch_events(db_path=db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["session_id"] == "sess1"
    assert row["submitted_answer"] == 1017
    assert row["bug_type"] == "add_concat_no_carry"
    assert row["correct"] == 0
    assert row["signal"] == 1


def test_log_submission_writes_a_non_signal_row_flagged_not_dropped(tmp_path):
    db_path = tmp_path / "events.db"

    events.log_submission(
        session_id="sess1",
        student_id="s1",
        problem_id="p_1",
        skill_tag="addition_carry",
        question="86 + 94",
        submitted_answer=None,
        correct_answer=180,
        attempt=1,
        correct=False,
        bug_type=None,
        signal=False,
        time_taken_sec=0.3,
        db_path=db_path,
    )

    rows = events.fetch_events(db_path=db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["submitted_answer"] is None
    assert row["bug_type"] is None
    assert row["signal"] == 0


def test_unclassified_diagnosis_is_logged_with_submitted_answer_intact(tmp_path):
    db_path = tmp_path / "events.db"

    events.log_submission(
        session_id="sess1",
        student_id="s1",
        problem_id="p_2",
        skill_tag="subtraction_borrow",
        question="72 - 48",
        submitted_answer=999,
        correct_answer=24,
        attempt=1,
        correct=False,
        bug_type="unclassified",
        signal=True,
        time_taken_sec=4.0,
        db_path=db_path,
    )

    rows = events.fetch_events(db_path=db_path)
    assert rows[0]["bug_type"] == "unclassified"
    assert rows[0]["submitted_answer"] == 999


def test_multiple_submissions_append_rather_than_overwrite(tmp_path):
    db_path = tmp_path / "events.db"
    for i in range(3):
        events.log_submission(
            session_id="sess1",
            student_id="s1",
            problem_id=f"p_{i}",
            skill_tag="addition_carry",
            question="1 + 1",
            submitted_answer=2,
            correct_answer=2,
            attempt=1,
            correct=True,
            bug_type=None,
            signal=True,
            time_taken_sec=1.0,
            db_path=db_path,
        )

    rows = events.fetch_events(db_path=db_path)
    assert [row["problem_id"] for row in rows] == ["p_0", "p_1", "p_2"]
