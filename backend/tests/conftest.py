import pytest


@pytest.fixture(autouse=True)
def _no_llm_api_key(monkeypatch):
    """Keep the whole suite deterministic and network-free: every narrative
    touchpoint falls back to None unless a test explicitly sets a key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
