import json
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from app.llm.base import LLMProvider
from app.llm.http_client import post_json
from app.tools.registry import TOOL_DEFINITIONS


class OpenAIProvider(LLMProvider):
    def plan(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for item in history or []:
            messages.append(item)
        messages.append({"role": "user", "content": message})

        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                },
            }
            for tool in TOOL_DEFINITIONS
        ]

        payload = post_json(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            payload={
                "model": settings.openai_model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            },
        )
        message_payload = payload["choices"][0]["message"]
        if message_payload.get("tool_calls"):
            call = message_payload["tool_calls"][0]["function"]
            return {
                "intent": call["name"],
                "tool": call["name"],
                "arguments": json.loads(call["arguments"]),
                "requires_confirmation": False,
            }
        return {
            "intent": "help",
            "tool": None,
            "arguments": {},
            "help_text": message_payload.get("content", ""),
        }
