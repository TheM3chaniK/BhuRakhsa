"""LLM integration interfaces and client implementations."""

from functools import lru_cache

from app.services.llm.base import LLMClient
from app.services.llm.ollama_client import OllamaLLMClient


@lru_cache
def get_llm_client() -> LLMClient:
    """Factory returning the default structured LLM extraction client."""
    return OllamaLLMClient()


__all__ = [
    "LLMClient",
    "OllamaLLMClient",
    "get_llm_client",
]
