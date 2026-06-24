from app.config import settings
from app.llm.factory import get_llm_provider
from app.llm.mock import MockLLM


def test_openai_provider_falls_back_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert isinstance(get_llm_provider(), MockLLM)
