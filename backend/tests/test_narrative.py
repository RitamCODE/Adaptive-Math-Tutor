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
