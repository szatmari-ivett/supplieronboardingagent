from typing import Any

import httpx


class LLMRequestError(ValueError):
    """Raised when an upstream LLM provider request fails."""


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float = 30,
) -> dict[str, Any]:
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise LLMRequestError(f"LLM API returned {exc.response.status_code}: {detail}") from exc
    except httpx.RequestError as exc:
        raise LLMRequestError(f"LLM API request failed: {exc}") from exc
