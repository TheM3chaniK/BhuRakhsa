import asyncio
import json
import re
from typing import Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.services.llm.base import LLMClient
from app.services.ollama_service import OllamaServiceException

T = TypeVar("T", bound=BaseModel)


class OllamaLLMClient(LLMClient):
    """Ollama implementation of LLMClient providing structured JSON extraction with schema validation."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.EXTRACTION_MODEL
        self.timeout = timeout or settings.EXTRACTION_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.EXTRACTION_MAX_RETRIES

    async def generate_text(self, prompt: str) -> str:
        """Execute text completion on Ollama."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }

        attempts = 0
        last_ex: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    if response.status_code == 404:
                        raise OllamaServiceException(
                            code="MODEL_NOT_FOUND",
                            message=f"Model '{self.model_name}' not found in Ollama.",
                        )
                    if response.status_code != 200:
                        raise OllamaServiceException(
                            code="EXTRACTION_INVALID_RESPONSE",
                            message=f"Ollama returned HTTP {response.status_code}: {response.text[:200]}",
                        )

                    data = response.json()
                    text = data.get("response", "")
                    return str(text).strip()

            except (httpx.ConnectError, httpx.TimeoutException) as err:
                last_ex = err
                if attempts <= self.max_retries:
                    await asyncio.sleep(1.0)
            except OllamaServiceException:
                raise
            except Exception as e:
                last_ex = e

        if last_ex:
            raise OllamaServiceException(
                code="EXTRACTION_UNAVAILABLE",
                message=f"LLM extraction request failed: {str(last_ex)}",
            )
        raise OllamaServiceException(code="UNKNOWN_ERROR", message="LLM request failed.")

    async def generate_structured(self, prompt: str, response_schema: Type[T]) -> T:
        """Execute inference with JSON format enforcement and validate against Pydantic schema."""
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "format": "json",
            "stream": False,
        }

        attempts = 0
        last_ex: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    if response.status_code == 404:
                        raise OllamaServiceException(
                            code="MODEL_NOT_FOUND",
                            message=f"Model '{self.model_name}' not found in Ollama.",
                        )
                    if response.status_code != 200:
                        raise OllamaServiceException(
                            code="EXTRACTION_INVALID_RESPONSE",
                            message=f"Ollama returned HTTP {response.status_code}: {response.text[:200]}",
                        )

                    data = response.json()
                    raw_content = data.get("response", "")
                    if not raw_content:
                        raise OllamaServiceException(
                            code="EXTRACTION_INVALID_RESPONSE",
                            message="Empty response received from LLM extraction.",
                        )

                    # Clean markdown codeblocks if model wraps json in ```json ... ```
                    clean_json_str = raw_content.strip()
                    if clean_json_str.startswith("```"):
                        clean_json_str = re.sub(r"^```(?:json)?\s*", "", clean_json_str)
                        clean_json_str = re.sub(r"\s*```$", "", clean_json_str)

                    try:
                        parsed_json = json.loads(clean_json_str)
                        return response_schema.model_validate(parsed_json)
                    except (json.JSONDecodeError, ValidationError) as parse_err:
                        logger.error("Structured schema validation error: %s\nRaw output: %s", parse_err, raw_content)
                        raise OllamaServiceException(
                            code="EXTRACTION_INVALID_RESPONSE",
                            message=f"LLM response failed schema validation: {str(parse_err)}",
                        )

            except (httpx.ConnectError, httpx.TimeoutException) as err:
                last_ex = err
                if attempts <= self.max_retries:
                    await asyncio.sleep(1.0)
            except OllamaServiceException:
                raise
            except Exception as e:
                last_ex = e

        if last_ex:
            raise OllamaServiceException(
                code="EXTRACTION_UNAVAILABLE",
                message=f"Structured extraction request failed: {str(last_ex)}",
            )
        raise OllamaServiceException(code="UNKNOWN_ERROR", message="Structured extraction failed.")
