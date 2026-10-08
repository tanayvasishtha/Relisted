import pytest


@pytest.fixture(autouse=True)
def never_spend_credits(monkeypatch):
    """Even with a real key in .env, tests run in replay mode."""
    monkeypatch.setenv("RELISTED_REPLAY", "1")
