import logging

from app.config import settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider
from app.llm.mock import MockLLM
from app.llm.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def get_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()

    if provider == "openai":
        if settings.openai_api_key:
            return OpenAIProvider()
        logger.warning("OPENAI_API_KEY is missing; falling back to MockLLM")
        return MockLLM()

    if provider == "anthropic":
        if settings.anthropic_api_key:
            return AnthropicProvider()
        logger.warning("ANTHROPIC_API_KEY is missing; falling back to MockLLM")
        return MockLLM()

    return MockLLM()
