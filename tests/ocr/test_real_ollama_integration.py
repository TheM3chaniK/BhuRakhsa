import os
from io import BytesIO
from PIL import Image, ImageDraw
import pytest

from app.core.config import settings
from app.services.ocr_service import DEFAULT_OCR_PROMPT, OcrService
from app.services.ollama_service import OllamaService


@pytest.mark.anyio
async def test_real_ollama_deepseek_ocr_execution() -> None:
    """Optional live integration test against local Ollama running DeepSeek OCR.

    Enabled only when RUN_OLLAMA_TESTS=true is set in the environment.
    """
    if not (
        settings.RUN_OLLAMA_TESTS
        or os.getenv("RUN_OLLAMA_TESTS", "false").lower() in ("true", "1")
    ):
        pytest.skip("RUN_OLLAMA_TESTS is false. Skipping live Ollama integration test.")

    service = OllamaService()

    # 1. Verify connection
    connected = await service.check_connection()
    assert connected is True, f"Cannot connect to Ollama at {settings.OLLAMA_BASE_URL}"

    # 2. Verify model available
    model_ok = await service.check_model_available()
    assert model_ok is True, f"Model {settings.OLLAMA_MODEL} not found in Ollama"

    # 3. Create a synthetic image with clear text
    img = Image.new("RGB", (600, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 80), "PROPERTY TITLE DEED NO 12345", fill="black")

    buf = BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # 4. Execute OCR
    text, duration_ms = await OcrService.process_page(
        ollama_service=service,
        page_bytes=img_bytes,
        page_number=1,
        prompt=DEFAULT_OCR_PROMPT,
    )

    assert len(text) > 0
    assert duration_ms > 0
    print(f"\n[Real Ollama OCR Result] ({duration_ms}ms):\n{text}")
