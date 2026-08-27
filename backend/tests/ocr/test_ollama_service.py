import httpx
import pytest
import respx

from app.services.ollama_service import OllamaService, OllamaServiceException


@pytest.mark.anyio
@respx.mock
async def test_ollama_connection_and_model_check() -> None:
    """Verify Ollama health check and model availability lookup."""
    service = OllamaService(base_url="http://localhost:11434", model_name="deepseek-ocr")

    # 1. Successful connection and model list
    respx.get("http://localhost:11434/api/tags").respond(
        status_code=200,
        json={"models": [{"name": "deepseek-ocr:latest"}, {"name": "llama3:latest"}]},
    )

    assert await service.check_connection() is True
    models = await service.get_available_models()
    assert "deepseek-ocr:latest" in models
    assert await service.check_model_available("deepseek-ocr") is True
    assert await service.check_model_available("unknown-model") is False


@pytest.mark.anyio
@respx.mock
async def test_ollama_run_ocr_success() -> None:
    """Verify successful OCR text generation via Ollama /api/generate."""
    service = OllamaService(base_url="http://localhost:11434", model_name="deepseek-ocr")

    sample_ocr_text = "SALE DEED\nSurvey No: 42/1\nOwner: John Doe"

    respx.post("http://localhost:11434/api/generate").respond(
        status_code=200,
        json={"response": sample_ocr_text},
    )

    text = await service.run_ocr(b"dummy_image_bytes", prompt="Extract text")
    assert text == sample_ocr_text


@pytest.mark.anyio
@respx.mock
async def test_ollama_model_not_found() -> None:
    """Verify 404 from Ollama generates MODEL_NOT_FOUND error."""
    service = OllamaService(base_url="http://localhost:11434", model_name="missing-model", max_retries=0)

    respx.post("http://localhost:11434/api/generate").respond(
        status_code=404,
        text="model 'missing-model' not found",
    )

    with pytest.raises(OllamaServiceException) as exc:
        await service.run_ocr(b"dummy_image_bytes", prompt="Extract text")

    assert exc.value.code == "MODEL_NOT_FOUND"


@pytest.mark.anyio
@respx.mock
async def test_ollama_timeout_and_retries() -> None:
    """Verify timeout leads to transient retries and final OLLAMA_TIMEOUT error."""
    service = OllamaService(
        base_url="http://localhost:11434", model_name="deepseek-ocr", timeout=1, max_retries=1
    )

    respx.post("http://localhost:11434/api/generate").mock(
        side_effect=httpx.TimeoutException("Read timed out")
    )

    with pytest.raises(OllamaServiceException) as exc:
        await service.run_ocr(b"dummy_image_bytes", prompt="Extract text")

    assert exc.value.code == "OLLAMA_TIMEOUT"
