from dataclasses import dataclass
from typing import List, Optional
import uuid

from app.core.config import settings
from app.models.enums import MatchStatus, MismatchReason
from app.models.property_profile import PropertyProfile
from app.models.reference_property import ReferenceProperty
from app.models.validation_result import ValidationResult
from app.services.matching.name_matcher import NameMatcher
from app.services.normalization.area import AreaNormalizer
from app.services.normalization.identifier import IdentifierNormalizer


class IdentifierRule:
    """Evaluates exact cadastral and legal document identifiers."""

    IDENTIFIER_FIELDS = [
        ("survey_number", MismatchReason.SURVEY_NUMBER_MISMATCH),
        ("plot_number", MismatchReason.PLOT_NUMBER_MISMATCH),
        ("parcel_number", MismatchReason.PARCEL_NUMBER_MISMATCH),
        ("registration_number", MismatchReason.REGISTRATION_NUMBER_MISMATCH),
        ("deed_number", MismatchReason.DEED_NUMBER_MISMATCH),
    ]

    @classmethod
    def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        reference: ReferenceProperty,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        for field_name, mismatch_code in cls.IDENTIFIER_FIELDS:
            doc_val = getattr(profile, field_name, None)
            ref_val = getattr(reference, field_name, None)

            # Both null / missing -> NOT_CHECKED
            if not doc_val and not ref_val:
                continue

            # Document missing -> NOT_FOUND
            if not doc_val:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=None,
                        reference_value=str(ref_val),
                        match_status=MatchStatus.NOT_FOUND,
                        match_score=0.0,
                        mismatch_reason=MismatchReason.DOCUMENT_VALUE_NOT_FOUND.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
                continue

            # Reference missing -> NOT_FOUND
            if not ref_val:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=None,
                        match_status=MatchStatus.NOT_FOUND,
                        match_score=0.0,
                        mismatch_reason=MismatchReason.REFERENCE_RECORD_NOT_FOUND.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
                continue

            # Both present -> Normalized exact check
            norm_doc = IdentifierNormalizer.normalize(str(doc_val))
            norm_ref = IdentifierNormalizer.normalize(str(ref_val))

            if norm_doc == norm_ref:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=str(ref_val),
                        match_status=MatchStatus.MATCH,
                        match_score=1.0,
                        mismatch_reason=None,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
            else:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=str(ref_val),
                        match_status=MatchStatus.MISMATCH,
                        match_score=0.0,
                        mismatch_reason=mismatch_code.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )

        return results


class NameRule:
    """Evaluates multi-owner correspondence between document profile and reference dataset."""

    @classmethod
    def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        reference: ReferenceProperty,
    ) -> List[ValidationResult]:
        doc_owner_names = [o.name for o in profile.owners if o.name]
        ref_owner_names = [o.name for o in reference.owners if o.name]

        match_res = NameMatcher.match_owner_sets(doc_owner_names, ref_owner_names)

        doc_summary = ", ".join(doc_owner_names) if doc_owner_names else None
        ref_summary = ", ".join(ref_owner_names) if ref_owner_names else None

        mismatch_reason = None
        if match_res.overall_status == MatchStatus.MISMATCH:
            mismatch_reason = MismatchReason.OWNER_MISMATCH.value
        elif match_res.overall_status == MatchStatus.NOT_FOUND:
            mismatch_reason = (
                MismatchReason.DOCUMENT_VALUE_NOT_FOUND.value
                if not doc_owner_names
                else MismatchReason.REFERENCE_RECORD_NOT_FOUND.value
            )

        return [
            ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="owner_name",
                document_value=doc_summary,
                reference_value=ref_summary,
                match_status=match_res.overall_status,
                match_score=match_res.overall_score,
                mismatch_reason=mismatch_reason,
                source_id=reference.source_id,
                source_record_id=reference.source_record_id,
            )
        ]


class AreaRule:
    """Evaluates property area measurements converting across standard units within tolerance."""

    @classmethod
    def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        reference: ReferenceProperty,
        tolerance_percent: Optional[float] = None,
    ) -> List[ValidationResult]:
        tol = (
            tolerance_percent
            if tolerance_percent is not None
            else settings.AREA_MATCH_TOLERANCE_PERCENT
        )

        doc_area_str = (
            f"{profile.property_area} {profile.area_unit or ''}".strip()
            if profile.property_area is not None
            else None
        )
        ref_area_str = (
            f"{reference.property_area} {reference.area_unit or ''}".strip()
            if reference.property_area is not None
            else None
        )

        if profile.property_area is None and reference.property_area is None:
            return []

        if profile.property_area is None:
            return [
                ValidationResult(
                    id=uuid.uuid4(),
                    validation_run_id=run_id,
                    field_name="property_area",
                    document_value=None,
                    reference_value=ref_area_str,
                    match_status=MatchStatus.NOT_FOUND,
                    match_score=0.0,
                    mismatch_reason=MismatchReason.DOCUMENT_VALUE_NOT_FOUND.value,
                    source_id=reference.source_id,
                    source_record_id=reference.source_record_id,
                )
            ]

        if reference.property_area is None:
            return [
                ValidationResult(
                    id=uuid.uuid4(),
                    validation_run_id=run_id,
                    field_name="property_area",
                    document_value=doc_area_str,
                    reference_value=None,
                    match_status=MatchStatus.NOT_FOUND,
                    match_score=0.0,
                    mismatch_reason=MismatchReason.REFERENCE_RECORD_NOT_FOUND.value,
                    source_id=reference.source_id,
                    source_record_id=reference.source_record_id,
                )
            ]

        is_match, score, err_reason = AreaNormalizer.compare_areas(
            val_doc=profile.property_area,
            unit_doc=profile.area_unit,
            val_ref=reference.property_area,
            unit_ref=reference.area_unit,
            tolerance_percent=tol,
        )

        return [
            ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="property_area",
                document_value=doc_area_str,
                reference_value=ref_area_str,
                match_status=MatchStatus.MATCH if is_match else MatchStatus.MISMATCH,
                match_score=score or 0.0,
                mismatch_reason=err_reason,
                source_id=reference.source_id,
                source_record_id=reference.source_record_id,
            )
        ]


class AdministrativeLocationRule:
    """Evaluates district, village, and administrative jurisdiction alignments."""

    LOCATION_FIELDS = [
        ("district", MismatchReason.DISTRICT_MISMATCH),
        ("village", MismatchReason.VILLAGE_MISMATCH),
        ("mouza", MismatchReason.MOUZA_MISMATCH),
        ("ward", MismatchReason.WARD_MISMATCH),
    ]

    @classmethod
    def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        reference: ReferenceProperty,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        for field_name, mismatch_code in cls.LOCATION_FIELDS:
            doc_val = getattr(profile, field_name, None)
            ref_val = getattr(reference, field_name, None)

            if not doc_val and not ref_val:
                continue

            if not doc_val:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=None,
                        reference_value=str(ref_val),
                        match_status=MatchStatus.NOT_FOUND,
                        match_score=0.0,
                        mismatch_reason=MismatchReason.DOCUMENT_VALUE_NOT_FOUND.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
                continue

            if not ref_val:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=None,
                        match_status=MatchStatus.NOT_FOUND,
                        match_score=0.0,
                        mismatch_reason=MismatchReason.REFERENCE_RECORD_NOT_FOUND.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
                continue

            # Normalized case/space comparison
            clean_doc = " ".join(str(doc_val).lower().split())
            clean_ref = " ".join(str(ref_val).lower().split())

            if clean_doc == clean_ref:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=str(ref_val),
                        match_status=MatchStatus.MATCH,
                        match_score=1.0,
                        mismatch_reason=None,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )
            else:
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name=field_name,
                        document_value=str(doc_val),
                        reference_value=str(ref_val),
                        match_status=MatchStatus.MISMATCH,
                        match_score=0.0,
                        mismatch_reason=mismatch_code.value,
                        source_id=reference.source_id,
                        source_record_id=reference.source_record_id,
                    )
                )

        return results
