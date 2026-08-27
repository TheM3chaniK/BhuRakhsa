import asyncio
import base64
from typing import List, Optional

import httpx

from app.core.config import settings
from app.core.logging import logger


class OllamaServiceException(Exception):
    """Exception raised for Ollama API interaction failures."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class OllamaService:
    """HTTP client service communicating with local Ollama instance for DeepSeek OCR inference."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.OCR_MAX_RETRIES

    async def check_connection(self) -> bool:
        """Check if local Ollama server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    async def get_available_models(self) -> List[str]:
        """Fetch list of model tags currently pulled in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code != 200:
                    return []
                data = res.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if "name" in m]
        except Exception as e:
            logger.warning("Failed to query Ollama models: %s", e)
            return []

    async def check_model_available(self, model_name: Optional[str] = None) -> bool:
        """Verify that the target model is installed in local Ollama."""
        target = model_name or self.model_name
        models = await self.get_available_models()
        if not models:
            return False

        # Match exact name or prefix before ':latest'
        return any(
            target == m or f"{target}:latest" == m or m.startswith(f"{target}:")
            for m in models
        )

    async def run_ocr(
        self, image_bytes: bytes, prompt: str, model_name: Optional[str] = None
    ) -> str:
        """Execute DeepSeek OCR on an image byte array via Ollama /api/generate endpoint with retry support."""
        target_model = model_name or self.model_name
        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": target_model,
            "prompt": prompt,
            "images": [b64_image],
            "stream": False,
        }

        last_exception: Optional[Exception] = None
        attempts = 0

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
                            message=f"Model '{target_model}' was not found in Ollama.",
                        )

                    if response.status_code != 200:
                        raise OllamaServiceException(
                            code="OCR_INVALID_RESPONSE",
                            message=f"Ollama returned unexpected HTTP {response.status_code}: {response.text[:200]}",
                        )

                    data = response.json()
                    raw_text = data.get("response")
                    if raw_text is None:
                        raise OllamaServiceException(
                            code="OCR_INVALID_RESPONSE",
                            message="Ollama response did not contain 'response' text field.",
                        )

                    return str(raw_text).strip()

            except httpx.ConnectError as ce:
                last_exception = OllamaServiceException(
                    code="OLLAMA_UNAVAILABLE",
                    message=f"Could not connect to Ollama at {self.base_url}.",
                )
            except httpx.TimeoutException:
                last_exception = OllamaServiceException(
                    code="OLLAMA_TIMEOUT",
                    message=f"Ollama request timed out after {self.timeout}s.",
                )
            except OllamaServiceException as ose:
                # Permanent errors (e.g. MODEL_NOT_FOUND) should not be retried
                if ose.code in ("MODEL_NOT_FOUND", "OCR_INVALID_RESPONSE"):
                    raise
                last_exception = ose
            except Exception as ex:
                last_exception = OllamaServiceException(
                    code="UNKNOWN_ERROR",
                    message=f"Unexpected error calling Ollama: {str(ex)}",
                )

            if attempts <= self.max_retries:
                logger.warning(
                    "Ollama OCR attempt %d failed: %s. Retrying in 1s...",
                    attempts,
                    last_exception,
                )
                await asyncio.sleep(1.0)

        if last_exception:
            raise last_exception
        raise OllamaServiceException(code="UNKNOWN_ERROR", message="OCR failed with unknown error.")
