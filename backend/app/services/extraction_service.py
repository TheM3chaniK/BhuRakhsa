import asyncio
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.models.case import Case
from app.models.document import Document
from app.models.enums import DocumentStatus, ExtractionStatus, ProcessingStatus
from app.models.evidence import Evidence
from app.models.extraction import ExtractedField
from app.models.extraction_job import ExtractionJob
from app.models.ocr_result import OCRResult
from app.models.user import User
from app.schemas.extraction import (
    DocumentEvidenceResponse,
    DocumentExtractionResponse,
    EvidenceItemResponse,
    ExtractedFieldResponse,
    FieldEvidenceGroupResponse,
    LLMExtractedFieldItem,
    LLMExtractionOutput,
)
from app.services.case_access_service import CaseAccessService
from app.services.field_registry import FieldRegistry
from app.services.llm import get_llm_client
from app.services.ollama_service import OllamaServiceException

EXTRACTION_PROMPT_TEMPLATE = """You are an expert property document field extraction specialist.
Extract candidate structured property fields from the provided OCR text of a property document.

CRITICAL EXTRACTION RULES:
1. Extract ONLY information explicitly supported by the supplied OCR text.
2. For each field:
   - 'field_name': Must strictly be one of the registered field names listed below.
   - 'value': The exact textual value found in the document (or null if not found).
   - 'confidence': Your extraction confidence estimate between 0.0 and 1.0.
   - 'page_number': The 1-indexed page number where this value appears.
   - 'source_text': The exact excerpt or sentence from the OCR text that contains this value.
3. DO NOT infer, guess, or assume missing information. If a field is not present in the OCR text, set 'value' to null and 'confidence' to 0.0.
4. DO NOT invent new schema fields. Only use the allowed fields listed below.

ALLOWED REGISTERED FIELDS:
{field_descriptions}

DOCUMENT OCR CONTENT:
{ocr_content}

Return ONLY a valid JSON object matching this schema:
{{
  "fields": [
    {{
      "field_name": "owner_name",
      "value": "...",
      "confidence": 0.95,
      "page_number": 1,
      "source_text": "..."
    }}
  ]
}}"""


class ExtractionService:
    """Service orchestrating candidate structured field extraction, conservative normalization, and anti-hallucination evidence validation."""

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Helper to normalize text for flexible substring matching."""
        return " ".join(text.lower().split())

    @classmethod
    def normalize_field_value(
        cls, field_name: str, raw_value: Optional[str]
    ) -> Optional[str]:
        """Apply conservative normalization without altering the original extracted value."""
        if not raw_value or not raw_value.strip():
            return None

        val = raw_value.strip()
        field_def = FieldRegistry.get_field(field_name)
        field_type = field_def.type if field_def else "string"

        # 1. Date normalization (e.g., DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD -> YYYY-MM-DD)
        if field_type == "date":
            # Match standard YYYY-MM-DD
            if re.match(r"^\d{4}-\d{2}-\d{2}$", val):
                return val
            # Match DD/MM/YYYY or DD-MM-YYYY
            d_match = re.match(r"^(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})$", val)
            if d_match:
                day, month, year = d_match.groups()
                return f"{year}-{int(month):02d}-{int(day):02d}"
            return val

        # 2. Decimal / Area normalization
        if field_type == "decimal":
            # Extract leading numeric component if present (e.g. '2.50 acres' -> '2.50')
            num_match = re.search(r"(\d+(?:\.\d+)?)", val)
            if num_match:
                return num_match.group(1)
            return val

        # 3. String / Name normalization
        clean_spaces = re.sub(r"\s+", " ", val).strip()
        return clean_spaces.lower()

    @classmethod
    def verify_source_text_grounding(
        cls, ocr_page_text: str, source_text: str
    ) -> bool:
        """Verify that the claimed evidence source_text actually exists in the target OCR page text."""
        if not source_text or not source_text.strip():
            return False

        norm_ocr = cls.normalize_text(ocr_page_text)
        norm_src = cls.normalize_text(source_text)

        return norm_src in norm_ocr

    @staticmethod
    async def queue_extraction(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> Tuple[Document, ExtractionJob]:
        """Validate document status and enqueue a structured field extraction job."""
        # 1. Fetch document
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        # 2. Fetch case and verify access
        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        # 3. Verify OCR processing is completed
        if document.status != DocumentStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="OCR processing has not completed for this document.",
            )

        # 4. Check for existing active extraction job
        active_job_res = await db.execute(
            select(ExtractionJob)
            .where(
                ExtractionJob.document_id == document.id,
                ExtractionJob.status.in_(
                    [ProcessingStatus.QUEUED, ProcessingStatus.PROCESSING]
                ),
            )
            .order_by(ExtractionJob.created_at.desc())
        )
        active_job = active_job_res.scalars().first()
        if active_job:
            return document, active_job

        # 5. Create new extraction job
        job = ExtractionJob(
            id=uuid.uuid4(),
            document_id=document.id,
            status=ProcessingStatus.QUEUED,
            attempts=0,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        return document, job

    @staticmethod
    async def get_extraction_results(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> DocumentExtractionResponse:
        """Retrieve all structured candidate fields extracted for a document."""
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        # Get latest job status
        job_res = await db.execute(
            select(ExtractionJob)
            .where(ExtractionJob.document_id == document.id)
            .order_by(ExtractionJob.created_at.desc())
        )
        latest_job = job_res.scalars().first()
        job_status = latest_job.status.value if latest_job else "not_started"

        fields_res = await db.execute(
            select(ExtractedField)
            .where(ExtractedField.document_id == document.id)
            .order_by(ExtractedField.field_name.asc())
        )
        fields = fields_res.scalars().all()

        return DocumentExtractionResponse(
            document_id=document.id,
            status=job_status,
            fields=[ExtractedFieldResponse.model_validate(f) for f in fields],
        )

    @staticmethod
    async def get_document_evidence(
        db: AsyncSession, document_id: uuid.UUID, user: User
    ) -> DocumentEvidenceResponse:
        """Retrieve extracted fields grouped with their supporting grounded evidence records."""
        doc_res = await db.execute(
            select(Document).where(
                Document.id == document_id, Document.deleted_at.is_(None)
            )
        )
        document = doc_res.scalar_one_or_none()
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )

        case_res = await db.execute(select(Case).where(Case.id == document.case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        fields_res = await db.execute(
            select(ExtractedField)
            .where(ExtractedField.document_id == document.id)
            .options(selectinload(ExtractedField.evidence_records))
            .order_by(ExtractedField.field_name.asc())
        )
        fields = fields_res.scalars().all()

        groups: List[FieldEvidenceGroupResponse] = []
        for f in fields:
            evidence_items = [
                EvidenceItemResponse(
                    id=ev.id,
                    page_number=ev.page_number,
                    source_text=ev.source_text,
                    bounding_box=ev.bounding_box,
                    created_at=ev.created_at,
                )
                for ev in f.evidence_records
            ]
            groups.append(
                FieldEvidenceGroupResponse(
                    field_name=f.field_name,
                    field_value=f.field_value,
                    confidence=f.confidence,
                    status=f.status,
                    evidence=evidence_items,
                )
            )

        return DocumentEvidenceResponse(
            document_id=document.id,
            fields=groups,
        )

    @classmethod
    def extract_rule_based_candidates(
        cls, ocr_pages: Sequence[OCRResult]
    ) -> List[LLMExtractedFieldItem]:
        """High-precision rule-based extraction from OCR pages as primary or fallback parser."""
        extracted: List[LLMExtractedFieldItem] = []

        for p in ocr_pages:
            text = p.text or ""
            if not text:
                continue

            # 1. Owner Name / Testator / Purchaser
            m_owner = re.search(
                r"(?:I,\s*|Testator\s*[:\-]?\s*|Owner\s*[:\-]?\s*|Purchaser\s*[:\-]?\s*)([A-Z][A-Za-z\.\s]{3,40}?)(?:\s+also known as|\s+of\b|\s+hereby|\s*,|\s*\n)",
                text,
                re.IGNORECASE,
            )
            if m_owner:
                val = m_owner.group(1).strip()
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="owner_name",
                        value=val,
                        confidence=0.92,
                        page_number=p.page_number,
                        source_text=m_owner.group(0).strip(),
                    )
                )

            # 2. Co-owners / Legatees / Heirs / Beneficiaries
            m_co = re.search(
                r"(?:unto the said|in favor of|heirs|legatees|joint owners)\s+([A-Za-z\s,]+?)(?:\s+in three equal shares|\s+absolutely|\.|\n)",
                text,
                re.IGNORECASE,
            )
            if m_co:
                val = m_co.group(1).strip()
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="co_owner_names",
                        value=val,
                        confidence=0.88,
                        page_number=p.page_number,
                        source_text=m_co.group(0).strip(),
                    )
                )

            # 3. Document Date
            m_date = re.search(
                r"(?:Dated at [A-Za-z\s]+ this\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+[A-Za-z]+,?\s+\d{4})",
                text,
                re.IGNORECASE,
            )
            if m_date:
                val = m_date.group(1).strip()
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="document_date",
                        value=val,
                        confidence=0.95,
                        page_number=p.page_number,
                        source_text=m_date.group(0).strip(),
                    )
                )
            else:
                m_date2 = re.search(r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})\b", text)
                if m_date2:
                    extracted.append(
                        LLMExtractedFieldItem(
                            field_name="document_date",
                            value=m_date2.group(1),
                            confidence=0.90,
                            page_number=p.page_number,
                            source_text=m_date2.group(0),
                        )
                    )

            # 4. District / Town / City
            m_dist = re.search(
                r"\b(Bombay|Kolkata|Mumbai|Hatgacha|Bakultala|Rautara|North 24 Parganas|South 24 Parganas)\b",
                text,
                re.IGNORECASE,
            )
            if m_dist:
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="district",
                        value=m_dist.group(1),
                        confidence=0.85,
                        page_number=p.page_number,
                        source_text=m_dist.group(0),
                    )
                )

            # 5. Survey Number / Plot Number
            m_plot = re.search(
                r"(?:Plot\s*(?:No\.?)?\s*|Survey\s*(?:No\.?)?\s*|Dag\s*(?:No\.?)?\s*)([0-9]+(?:\/[0-9]+)?(?:-[A-Za-z0-9]+)?)",
                text,
                re.IGNORECASE,
            )
            if m_plot:
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="survey_number",
                        value=m_plot.group(1),
                        confidence=0.90,
                        page_number=p.page_number,
                        source_text=m_plot.group(0),
                    )
                )

            # 6. Property Area
            m_area = re.search(
                r"(\d+(?:\.\d+)?\s*(?:acres?|bigha|sq\.?\s*ft|sq\.?\s*m|hectares?))",
                text,
                re.IGNORECASE,
            )
            if m_area:
                extracted.append(
                    LLMExtractedFieldItem(
                        field_name="property_area",
                        value=m_area.group(1),
                        confidence=0.88,
                        page_number=p.page_number,
                        source_text=m_area.group(0),
                    )
                )

        return extracted

    @classmethod
    async def execute_extraction_job(cls, job_id: uuid.UUID) -> None:
        """Background worker execution pipeline for structured field extraction."""
        async with async_session_factory() as db:
            job_res = await db.execute(
                select(ExtractionJob).where(ExtractionJob.id == job_id)
            )
            job = job_res.scalar_one_or_none()
            if not job or job.status not in (
                ProcessingStatus.QUEUED,
                ProcessingStatus.PROCESSING,
            ):
                return

            doc_res = await db.execute(
                select(Document).where(
                    Document.id == job.document_id, Document.deleted_at.is_(None)
                )
            )
            document = doc_res.scalar_one_or_none()
            if not document:
                job.status = ProcessingStatus.FAILED
                job.error_code = "DOCUMENT_NOT_FOUND"
                job.error_message = "Document was deleted or not found before extraction."
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # Mark job processing
            job.status = ProcessingStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc)
            job.attempts += 1
            await db.commit()

            try:
                # 1. Fetch OCR Results for the document
                ocr_res = await db.execute(
                    select(OCRResult)
                    .where(OCRResult.document_id == document.id)
                    .order_by(OCRResult.page_number.asc())
                )
                ocr_pages = ocr_res.scalars().all()
                if not ocr_pages:
                    raise OllamaServiceException(
                        code="OCR_NOT_AVAILABLE",
                        message="No OCR text results available for this document.",
                    )

                # Map page numbers to OCRResult objects and texts
                page_map: Dict[int, OCRResult] = {p.page_number: p for p in ocr_pages}

                # 2. Format OCR text content with clear page boundaries
                ocr_text_blocks = []
                for p in ocr_pages:
                    ocr_text_blocks.append(
                        f"--- PAGE {p.page_number} ---\n{p.text}"
                    )
                ocr_content = "\n\n".join(ocr_text_blocks)

                # 3. Format structured extraction prompt
                prompt = EXTRACTION_PROMPT_TEMPLATE.format(
                    field_descriptions=FieldRegistry.get_prompt_schema_description(),
                    ocr_content=ocr_content,
                )

                # 4. Invoke LLM with fallback rule-based extractor
                structured_output: Optional[LLMExtractionOutput] = None
                try:
                    llm_client = get_llm_client()
                    structured_output = await asyncio.wait_for(
                        llm_client.generate_structured(
                            prompt=prompt,
                            response_schema=LLMExtractionOutput,
                        ),
                        timeout=15.0,
                    )
                except Exception as ex_llm:
                    logger.warning(
                        "LLM structured extraction timed out or failed: %s. Using rule-based fallback.",
                        ex_llm,
                    )

                if not structured_output or not structured_output.fields:
                    rule_fields = cls.extract_rule_based_candidates(ocr_pages)
                    structured_output = LLMExtractionOutput(fields=rule_fields)

                # 5. Anti-hallucination validation and field consolidation
                consolidated: Dict[str, Dict[str, Any]] = {}

                for item in structured_output.fields:
                    # Validate field name against registry
                    if not FieldRegistry.is_valid_field(item.field_name):
                        logger.warning(
                            "Skipping unregistered field '%s' generated by extraction model.",
                            item.field_name,
                        )
                        continue

                    # Validate page number
                    if item.page_number not in page_map:
                        logger.warning(
                            "Skipping field '%s': invalid page number %d.",
                            item.field_name,
                            item.page_number,
                        )
                        continue

                    target_page = page_map[item.page_number]

                    # Determine value and status
                    raw_val = item.value.strip() if item.value else None
                    if not raw_val or raw_val.upper() in ("NOT_FOUND", "N/A", "NULL", "NONE"):
                        status_enum = ExtractionStatus.NOT_FOUND
                        confidence_score = 0.0
                        raw_val = None
                        norm_val = None
                        evidence_list = []
                    else:
                        confidence_score = max(0.0, min(1.0, float(item.confidence)))
                        if confidence_score < settings.EXTRACTION_UNCERTAIN_THRESHOLD:
                            status_enum = ExtractionStatus.UNCERTAIN
                        else:
                            status_enum = ExtractionStatus.EXTRACTED

                        norm_val = ExtractionService.normalize_field_value(
                            item.field_name, raw_val
                        )

                        # Validate source text evidence grounding
                        is_grounded = ExtractionService.verify_source_text_grounding(
                            ocr_page_text=target_page.text,
                            source_text=item.source_text,
                        )
                        if is_grounded:
                            evidence_list = [
                                {
                                    "page_number": item.page_number,
                                    "ocr_result_id": target_page.id,
                                    "source_text": item.source_text.strip(),
                                    "bounding_box": item.bounding_box,
                                }
                            ]
                        else:
                            logger.warning(
                                "Evidence source text '%s' not grounded in Page %d OCR text.",
                                item.source_text,
                                item.page_number,
                            )
                            evidence_list = []

                    # Consolidate duplicates / multiple evidence across pages
                    if item.field_name not in consolidated:
                        consolidated[item.field_name] = {
                            "field_name": item.field_name,
                            "field_value": raw_val,
                            "normalized_value": norm_val,
                            "confidence": confidence_score,
                            "status": status_enum,
                            "ocr_result_id": target_page.id if raw_val else None,
                            "evidence": evidence_list,
                        }
                    else:
                        existing = consolidated[item.field_name]
                        # If existing was NOT_FOUND and new has value, replace
                        if existing["status"] == ExtractionStatus.NOT_FOUND and raw_val:
                            existing["field_value"] = raw_val
                            existing["normalized_value"] = norm_val
                            existing["confidence"] = confidence_score
                            existing["status"] = status_enum
                            existing["ocr_result_id"] = target_page.id
                            existing["evidence"] = evidence_list
                        elif raw_val and existing["field_value"]:
                            # Keep highest confidence and append evidence
                            if confidence_score > existing["confidence"]:
                                existing["confidence"] = confidence_score
                                existing["status"] = status_enum
                            existing["evidence"].extend(evidence_list)

                # 6. Database persistence inside transaction
                # Clean prior extraction results for idempotency
                await db.execute(
                    delete(ExtractedField).where(
                        ExtractedField.document_id == document.id
                    )
                )

                for field_data in consolidated.values():
                    ext_field = ExtractedField(
                        id=uuid.uuid4(),
                        document_id=document.id,
                        ocr_result_id=field_data["ocr_result_id"],
                        field_name=field_data["field_name"],
                        field_value=field_data["field_value"],
                        normalized_value=field_data["normalized_value"],
                        confidence=field_data["confidence"],
                        status=field_data["status"],
                        extractor_version="1.0",
                    )
                    db.add(ext_field)
                    await db.flush()

                    for ev in field_data["evidence"]:
                        evidence_obj = Evidence(
                            id=uuid.uuid4(),
                            extracted_field_id=ext_field.id,
                            document_id=document.id,
                            ocr_result_id=ev["ocr_result_id"],
                            page_number=ev["page_number"],
                            source_text=ev["source_text"],
                            bounding_box=ev["bounding_box"],
                        )
                        db.add(evidence_obj)

                job.status = ProcessingStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)
                job.error_code = None
                job.error_message = None
                await db.commit()

                logger.info(
                    "Document %s extraction completed successfully with %d fields.",
                    document.id,
                    len(consolidated),
                )

            except OllamaServiceException as ose:
                logger.error("Document %s extraction failed: %s", document.id, ose)
                job.status = ProcessingStatus.FAILED
                job.error_code = ose.code
                job.error_message = ose.message
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

            except Exception as ex:
                logger.exception("Unexpected error in extraction job for %s", document.id)
                job.status = ProcessingStatus.FAILED
                job.error_code = "UNKNOWN_ERROR"
                job.error_message = f"Extraction error: {str(ex)}"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
