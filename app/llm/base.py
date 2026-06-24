from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    def plan(self, message: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        raise NotImplementedError
