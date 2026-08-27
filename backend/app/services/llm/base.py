from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(ABC):
    """Abstract interface for LLM structured inference."""

    @abstractmethod
    async def generate_structured(self, prompt: str, response_schema: Type[T]) -> T:
        """Execute inference and return validated Pydantic structured output."""
        pass

    @abstractmethod
    async def generate_text(self, prompt: str) -> str:
        """Execute inference and return raw text output."""
        pass
