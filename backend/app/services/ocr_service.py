from io import BytesIO
from pathlib import Path
import time
from typing import List, Tuple

from PIL import Image, ImageOps
import pypdfium2

from app.core.config import settings
from app.core.logging import logger
from app.services.ollama_service import OllamaService, OllamaServiceException

DEFAULT_OCR_PROMPT = "<image>\nFree OCR."


class OcrService:
    """Service providing document page rendering, image preprocessing, and page OCR execution via Ollama."""

    @staticmethod
    def preprocess_document_to_pages(file_path: Path, extension: str) -> List[bytes]:
        """Convert a source PDF or image file into an ordered list of normalized page image byte buffers."""
        ext = extension.lower()
        page_buffers: List[bytes] = []

        if ext == ".pdf":
            try:
                pdf = pypdfium2.PdfDocument(str(file_path))
                page_count = len(pdf)

                if page_count == 0:
                    raise OllamaServiceException(
                        code="DOCUMENT_READ_ERROR",
                        message="PDF document contains 0 pages.",
                    )

                if page_count > settings.MAX_DOCUMENT_PAGES:
                    raise OllamaServiceException(
                        code="PAGE_COUNT_EXCEEDED",
                        message=f"Document contains {page_count} pages, which exceeds the limit of {settings.MAX_DOCUMENT_PAGES}.",
                    )

                for page_idx in range(page_count):
                    page = pdf[page_idx]
                    # Render page at 2.0 scale (approx 144 DPI) for clear text reading
                    bitmap = page.render(scale=2.0)
                    pil_img = bitmap.to_pil()

                    buf = BytesIO()
                    pil_img.save(buf, format="PNG")
                    page_buffers.append(buf.getvalue())

            except OllamaServiceException:
                raise
            except Exception as e:
                logger.error("Failed to render PDF pages from %s: %s", file_path, e)
                raise OllamaServiceException(
                    code="PAGE_RENDER_ERROR",
                    message=f"Failed to render PDF document pages: {str(e)}",
                )

        elif ext in (".jpg", ".jpeg", ".png"):
            try:
                with Image.open(file_path) as img:
                    # Correct EXIF orientation if present
                    transposed = ImageOps.exif_transpose(img) or img

                    if transposed.mode not in ("RGB", "L"):
                        transposed = transposed.convert("RGB")

                    buf = BytesIO()
                    transposed.save(buf, format="PNG")
                    page_buffers.append(buf.getvalue())
            except Exception as e:
                logger.error("Failed to normalize image from %s: %s", file_path, e)
                raise OllamaServiceException(
                    code="PAGE_RENDER_ERROR",
                    message=f"Failed to process image document: {str(e)}",
                )

        else:
            raise OllamaServiceException(
                code="UNSUPPORTED_FORMAT",
                message=f"Unsupported format '{ext}' for OCR processing.",
            )

        return page_buffers

    @staticmethod
    async def process_page(
        ollama_service: OllamaService,
        page_bytes: bytes,
        page_number: int,
        prompt: str = DEFAULT_OCR_PROMPT,
    ) -> Tuple[str, int]:
        """Perform OCR on a single page image and measure execution time in milliseconds."""
        start_time = time.monotonic()
        text = await ollama_service.run_ocr(page_bytes, prompt)
        duration_ms = int((time.monotonic() - start_time) * 1000)
        return text, duration_ms
