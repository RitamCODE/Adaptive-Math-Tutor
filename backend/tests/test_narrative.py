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


# --- mastery_card_narrative (touchpoints 2-4, merged) ---


def _bundle_for(response_model, mastery="Short.", reward="Nice work.", boss="New challenge!"):
    kwargs = {"mastery_narrative": mastery, "reward_narrative": reward}
    if "boss_battle_narrative" in response_model.model_fields:
        kwargs["boss_battle_narrative"] = boss
    return response_model(**kwargs)


def _fake_complete_structured(captured, **bundle_kwargs):
    def fake(system, user, response_model):
        captured["system"] = system
        captured["user"] = user
        captured["response_model"] = response_model
        return _bundle_for(response_model, **bundle_kwargs)

    return fake


def test_mastery_card_narrative_returns_none_without_api_key():
    misconceptions = [
        Misconception(skill="addition_no_carry", bug_type="no_carry", timestamp=datetime.now())
    ]
    assert narrative.mastery_card_narrative("addition_no_carry", misconceptions, 5, 12.5) is None


def test_mastery_card_narrative_falls_back_to_none_if_structured_call_fails(monkeypatch):
    monkeypatch.setattr(narrative, "_complete_structured", lambda system, user, response_model: None)
    result = narrative.mastery_card_narrative("addition_no_carry", [], 3, 4.2)
    assert result is None


def test_mastery_card_narrative_with_misconceptions_names_pattern(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    misconceptions = [
        Misconception(skill="addition_carry", bug_type="no_carry", timestamp=datetime.now()),
        Misconception(skill="addition_carry", bug_type="add_off_by_one", timestamp=datetime.now()),
    ]
    result = narrative.mastery_card_narrative("addition_carry", misconceptions, 6, 9.0)

    assert "no_carry" in captured["user"]
    assert "add_off_by_one" in captured["user"]
    assert "none logged" not in captured["user"]
    assert "clean run" not in captured["user"]
    assert captured["response_model"] is narrative._NarrativesNoBoss
    assert result.boss_battle_narrative is None


def test_mastery_card_narrative_clean_run_uses_fluency_branch(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    narrative.mastery_card_narrative("addition_carry", [], 3, 4.2)

    assert "none logged" not in captured["user"]
    assert "clean run" in captured["user"].lower()
    assert "3" in captured["user"]
    assert "4.2" in captured["user"]
    assert "fluency" in captured["system"].lower() or "speed" in captured["system"].lower()


def test_mastery_card_narrative_includes_boss_battle_when_next_skill_given(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    result = narrative.mastery_card_narrative(
        "addition_carry", [], 3, 4.2, next_skill="subtraction_borrow"
    )

    assert captured["response_model"] is narrative._NarrativesWithBoss
    assert "subtraction_borrow" in captured["user"]
    assert result.boss_battle_narrative == "New challenge!"


def test_mastery_card_narrative_omits_boss_battle_when_next_skill_none(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    result = narrative.mastery_card_narrative("addition_carry", [], 3, 4.2, next_skill=None)

    assert result.boss_battle_narrative is None
    assert "boss_battle_narrative" not in captured["response_model"].model_fields


def test_mastery_card_narrative_system_prompt_states_word_budget(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    narrative.mastery_card_narrative("addition_carry", [], 3, 4.2, next_skill="subtraction_borrow")

    assert "20 words" in captured["system"]


def test_mastery_card_narrative_system_prompt_instructs_varied_openers(monkeypatch):
    captured = {}
    monkeypatch.setattr(narrative, "_complete_structured", _fake_complete_structured(captured))
    narrative.mastery_card_narrative("addition_carry", [], 3, 4.2, next_skill="subtraction_borrow")

    assert "different sentence opener" in captured["system"]
    assert "restate" in captured["system"]


def test_mastery_card_narrative_regenerates_once_on_overrun_and_succeeds(monkeypatch):
    too_long = " ".join(["word"] * 25)
    responses = [
        {"mastery": too_long},
        {"mastery": "You beat the carrying trap that used to trip you up."},
    ]

    def fake(system, user, response_model):
        kwargs = responses.pop(0)
        return _bundle_for(response_model, mastery=kwargs["mastery"])

    monkeypatch.setattr(narrative, "_complete_structured", fake)
    result = narrative.mastery_card_narrative("addition_carry", [], 4, 8.0)

    assert result.mastery_narrative == "You beat the carrying trap that used to trip you up."
    assert responses == []


def test_mastery_card_narrative_falls_back_to_none_if_regeneration_still_overruns(monkeypatch):
    too_long = " ".join(["word"] * 25)
    calls = []

    def fake(system, user, response_model):
        calls.append(user)
        return _bundle_for(response_model, mastery=too_long)

    monkeypatch.setattr(narrative, "_complete_structured", fake)
    result = narrative.mastery_card_narrative("addition_carry", [], 4, 8.0)

    assert result is None
    assert len(calls) == 2


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
