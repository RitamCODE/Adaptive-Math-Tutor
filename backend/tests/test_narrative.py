import subprocess
from datetime import datetime
from pathlib import Path

from backend.llm import narrative
from backend.models.state import Misconception

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_client_returns_none_without_api_key():
    assert narrative._client() is None


def test_flavor_word_problem_returns_none_without_api_key():
    assert narrative.flavor_word_problem("2 + 3 = ?", 5, "addition_no_carry", 0.3) is None


def test_mastery_moment_narrative_returns_none_without_api_key():
    misconceptions = [
        Misconception(skill="addition_no_carry", bug_type="no_carry", timestamp=datetime.now())
    ]
    assert narrative.mastery_moment_narrative("addition_no_carry", misconceptions, 5) is None


def test_effort_reward_narrative_returns_none_without_api_key():
    assert narrative.effort_reward_narrative("addition_no_carry", 3, 12.5) is None


def test_boss_battle_narrative_returns_none_without_api_key():
    assert narrative.boss_battle_narrative("addition_carry") is None


def test_word_count_empty_string():
    assert narrative._word_count("") == 0


def test_word_count_normal_sentence():
    assert narrative._word_count("Mia has 5 apples and 3 more.") == 7


def test_word_count_ignores_irregular_spacing():
    assert narrative._word_count("  Mia   has   5   apples  ") == 4


def test_flavor_word_problem_accepts_first_attempt_under_limit(monkeypatch):
    calls = []

    def fake_complete(system, user, max_tokens=120):
        calls.append(user)
        return "Mia has 5 apples. She gets 3 more. How many now?"

    monkeypatch.setattr(narrative, "_complete", fake_complete)
    result = narrative.flavor_word_problem("5 + 3 = ?", 8, "addition_no_carry", 0.3)

    assert result == "Mia has 5 apples. She gets 3 more. How many now?"
    assert len(calls) == 1


def test_flavor_word_problem_regenerates_once_on_overrun_and_succeeds(monkeypatch):
    too_long = " ".join(["word"] * 25)
    short = "Mia has 5 apples and gets 3 more today."
    responses = [too_long, short]

    def fake_complete(system, user, max_tokens=120):
        return responses.pop(0)

    monkeypatch.setattr(narrative, "_complete", fake_complete)
    result = narrative.flavor_word_problem("5 + 3 = ?", 8, "addition_no_carry", 0.3)

    assert result == short
    assert responses == []


def test_flavor_word_problem_falls_back_to_none_if_regeneration_still_overruns(monkeypatch):
    too_long = " ".join(["word"] * 25)
    calls = []

    def fake_complete(system, user, max_tokens=120):
        calls.append(user)
        return too_long

    monkeypatch.setattr(narrative, "_complete", fake_complete)
    result = narrative.flavor_word_problem("5 + 3 = ?", 8, "addition_no_carry", 0.3)

    assert result is None
    assert len(calls) == 2


def test_flavor_word_problem_falls_back_to_none_if_regeneration_fails(monkeypatch):
    too_long = " ".join(["word"] * 25)
    responses = [too_long, None]

    def fake_complete(system, user, max_tokens=120):
        return responses.pop(0)

    monkeypatch.setattr(narrative, "_complete", fake_complete)
    result = narrative.flavor_word_problem("5 + 3 = ?", 8, "addition_no_carry", 0.3)

    assert result is None
    assert responses == []


def test_client_wraps_with_langsmith_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    client = narrative._client()

    assert client is not None
    assert callable(client.chat.completions.create)


def test_llm_client_usage_isolated_to_narrative_module():
    tracked_py_files = subprocess.run(
        ["git", "ls-files", "backend/*.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    # Match actual client imports, not incidental mentions of the word
    # "openai" (e.g. this test's own grep pattern below).
    hits = subprocess.run(
        ["grep", "-lE", r"^\s*(from openai|import openai)", *tracked_py_files],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    assert set(hits) <= {"backend/llm/narrative.py"}
