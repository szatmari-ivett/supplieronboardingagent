from typing import Any

from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.http_client import post_json
from app.tools.registry import TOOL_DEFINITIONS


class AnthropicProvider(LLMProvider):
    def plan(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")

        tools = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["parameters"],
            }
            for tool in TOOL_DEFINITIONS
        ]

        payload = post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            payload={
                "model": settings.anthropic_model,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": (history or []) + [{"role": "user", "content": message}],
                "tools": tools,
            },
        )
        for block in payload.get("content", []):
            if block.get("type") == "tool_use":
                return {
                    "intent": block["name"],
                    "tool": block["name"],
                    "arguments": block.get("input", {}),
                    "requires_confirmation": False,
                }
        text = next(
            (block.get("text") for block in payload.get("content", []) if block.get("type") == "text"),
            "",
        )
        return {"intent": "help", "tool": None, "arguments": {}, "help_text": text}
