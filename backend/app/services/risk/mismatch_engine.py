from typing import Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import MatchStatus, MismatchReason, MismatchSource, MismatchType
from app.models.evidence import Evidence
from app.models.extraction import ExtractedField
from app.models.mismatch import Mismatch
from app.models.mismatch_evidence import MismatchEvidence
from app.models.property_field_conflict import PropertyFieldConflict
from app.models.property_field_source import PropertyFieldSource
from app.models.property_profile import PropertyProfile
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.risk.severity_rules import SEVERITY_RULE_VERSION, SeverityRules


class MismatchEngine:
    """Deterministic engine transforming validation discrepancies and extraction conflicts into evidence-linked Mismatch records."""

    REASON_TO_TYPE_MAP: Dict[str, MismatchType] = {
        MismatchReason.OWNER_MISMATCH.value: MismatchType.OWNER_MISMATCH,
        MismatchReason.SURVEY_NUMBER_MISMATCH.value: MismatchType.SURVEY_NUMBER_MISMATCH,
        MismatchReason.PLOT_NUMBER_MISMATCH.value: MismatchType.PLOT_NUMBER_MISMATCH,
        MismatchReason.PARCEL_NUMBER_MISMATCH.value: MismatchType.PARCEL_NUMBER_MISMATCH,
        MismatchReason.REGISTRATION_NUMBER_MISMATCH.value: MismatchType.REGISTRATION_NUMBER_MISMATCH,
        MismatchReason.DEED_NUMBER_MISMATCH.value: MismatchType.DEED_NUMBER_MISMATCH,
        MismatchReason.AREA_MISMATCH.value: MismatchType.AREA_MISMATCH,
        MismatchReason.REFERENCE_GIS_AREA_MISMATCH.value: MismatchType.REFERENCE_GIS_AREA_MISMATCH,
        MismatchReason.DOCUMENT_GIS_AREA_MISMATCH.value: MismatchType.DOCUMENT_GIS_AREA_MISMATCH,
        MismatchReason.DISTRICT_MISMATCH.value: MismatchType.DISTRICT_MISMATCH,
        MismatchReason.VILLAGE_MISMATCH.value: MismatchType.VILLAGE_MISMATCH,
        MismatchReason.MOUZA_MISMATCH.value: MismatchType.MOUZA_MISMATCH,
        MismatchReason.WARD_MISMATCH.value: MismatchType.WARD_MISMATCH,
        MismatchReason.PARCEL_NOT_FOUND.value: MismatchType.PARCEL_NOT_FOUND,
        MismatchReason.PARCEL_GEOMETRY_NOT_FOUND.value: MismatchType.PARCEL_GEOMETRY_NOT_FOUND,
        MismatchReason.INVALID_PARCEL_GEOMETRY.value: MismatchType.INVALID_PARCEL_GEOMETRY,
        MismatchReason.POINT_OUTSIDE_PARCEL.value: MismatchType.POINT_OUTSIDE_PARCEL,
        MismatchReason.DISTRICT_LOCATION_MISMATCH.value: MismatchType.DISTRICT_LOCATION_MISMATCH,
        MismatchReason.VILLAGE_LOCATION_MISMATCH.value: MismatchType.VILLAGE_LOCATION_MISMATCH,
        MismatchReason.AMBIGUOUS_MATCH.value: MismatchType.MULTIPLE_REFERENCE_CANDIDATES,
        MismatchReason.REFERENCE_RECORD_NOT_FOUND.value: MismatchType.PARCEL_NOT_FOUND,
    }

    @classmethod
    def _generate_description(
        cls,
        m_type: MismatchType,
        field_name: Optional[str],
        doc_val: Optional[str],
        ref_val: Optional[str],
        dist_m: Optional[float] = None,
    ) -> str:
        """Deterministic human-readable explanation for discrepancy."""
        clean_field = (field_name or "attribute").replace("_", " ")

        if m_type == MismatchType.POINT_OUTSIDE_PARCEL:
            d_str = f"{dist_m:.2f} meters" if dist_m is not None else "a significant distance"
            return f"The supplied property coordinate falls outside the reference parcel boundary by {d_str}."

        if m_type == MismatchType.PARCEL_NOT_FOUND:
            return "No matching authoritative reference property record was found in the registry."

        if m_type == MismatchType.INVALID_PARCEL_GEOMETRY:
            return "The reference parcel boundary geometry contains topological or self-intersection errors."

        if m_type == MismatchType.PARCEL_GEOMETRY_NOT_FOUND:
            return "Reference property record exists, but cadastral boundary geometry is missing in the GIS layer."

        if m_type == MismatchType.EXTRACTION_CONFLICT:
            return f"Conflicting values detected for {clean_field} across uploaded case documents: '{doc_val}' vs '{ref_val}'."

        if m_type == MismatchType.MULTIPLE_REFERENCE_CANDIDATES:
            return f"Search yielded multiple candidate reference records with ambiguous identifier matching."

        if doc_val and ref_val:
            return f"{clean_field.capitalize()} on the document is '{doc_val}', while the reference registry contains '{ref_val}'."
        elif doc_val and not ref_val:
            return f"{clean_field.capitalize()} on the document is '{doc_val}', but was not found in the reference record."
        elif ref_val and not doc_val:
            return f"{clean_field.capitalize()} was not specified on the document, but exists as '{ref_val}' in the reference record."

        return f"A validation discrepancy was detected for {clean_field}."

    @classmethod
    def generate_from_validation_results(
        cls,
        case_id: uuid.UUID,
        profile_id: uuid.UUID,
        val_run: ValidationRun,
        field_source_map: Dict[str, uuid.UUID],
        extracted_field_evidence_map: Dict[uuid.UUID, uuid.UUID],
    ) -> List[Mismatch]:
        """Convert database and GIS validation results into Mismatch records with evidence links."""
        mismatches: List[Mismatch] = []
        is_gis = val_run.validation_type.value == "gis"
        source = MismatchSource.GIS if is_gis else MismatchSource.DATABASE

        for res in val_run.results:
            if res.match_status in (MatchStatus.MATCH, MatchStatus.NOT_CHECKED):
                continue

            # Resolve MismatchType
            m_type = None
            if res.mismatch_reason and res.mismatch_reason in cls.REASON_TO_TYPE_MAP:
                m_type = cls.REASON_TO_TYPE_MAP[res.mismatch_reason]
            else:
                # Default mapping from field_name
                if res.field_name == "survey_number":
                    m_type = MismatchType.SURVEY_NUMBER_MISMATCH
                elif res.field_name == "plot_number":
                    m_type = MismatchType.PLOT_NUMBER_MISMATCH
                elif res.field_name == "parcel_number":
                    m_type = MismatchType.PARCEL_NUMBER_MISMATCH
                elif res.field_name == "owner_name":
                    m_type = MismatchType.OWNER_MISMATCH
                elif res.field_name == "property_area":
                    m_type = MismatchType.AREA_MISMATCH
                elif res.field_name == "district":
                    m_type = MismatchType.DISTRICT_MISMATCH
                elif res.field_name == "village":
                    m_type = MismatchType.VILLAGE_MISMATCH
                elif res.field_name == "reference_property":
                    m_type = MismatchType.PARCEL_NOT_FOUND
                else:
                    m_type = MismatchType.SURVEY_NUMBER_MISMATCH

            severity = SeverityRules.get_severity(m_type)
            desc = cls._generate_description(
                m_type=m_type,
                field_name=res.field_name,
                doc_val=res.document_value,
                ref_val=res.reference_value,
                dist_m=res.geometry_distance_meters,
            )

            mismatch = Mismatch(
                id=uuid.uuid4(),
                case_id=case_id,
                property_profile_id=profile_id,
                validation_run_id=val_run.id,
                mismatch_type=m_type,
                mismatch_source=source,
                field_name=res.field_name,
                document_value=res.document_value,
                reference_value=res.reference_value,
                severity=severity,
                description=desc,
                rule_version=SEVERITY_RULE_VERSION,
            )

            # Traceability link
            ext_field_id = field_source_map.get(res.field_name)
            evidence_id = extracted_field_evidence_map.get(ext_field_id) if ext_field_id else None

            ev_link = MismatchEvidence(
                id=uuid.uuid4(),
                mismatch_id=mismatch.id,
                validation_result_id=res.id,
                extracted_field_id=ext_field_id,
                evidence_id=evidence_id,
            )
            mismatch.evidence_links = [ev_link]
            mismatches.append(mismatch)

        return mismatches

    @classmethod
    def generate_from_extraction_conflicts(
        cls,
        case_id: uuid.UUID,
        profile_id: uuid.UUID,
        conflicts: List[PropertyFieldConflict],
        field_source_map: Dict[str, uuid.UUID],
        extracted_field_evidence_map: Dict[uuid.UUID, uuid.UUID],
    ) -> List[Mismatch]:
        """Convert multi-document extraction conflicts into Mismatch records."""
        mismatches: List[Mismatch] = []

        for c in conflicts:
            m_type = MismatchType.EXTRACTION_CONFLICT
            severity = SeverityRules.get_severity(m_type)
            desc = cls._generate_description(
                m_type=m_type,
                field_name=c.field_name,
                doc_val=c.value_a,
                ref_val=c.value_b,
            )

            mismatch = Mismatch(
                id=uuid.uuid4(),
                case_id=case_id,
                property_profile_id=profile_id,
                validation_run_id=None,
                mismatch_type=m_type,
                mismatch_source=MismatchSource.EXTRACTION,
                field_name=c.field_name,
                document_value=c.value_a,
                reference_value=c.value_b,
                severity=severity,
                description=desc,
                rule_version=SEVERITY_RULE_VERSION,
            )

            ext_field_id = field_source_map.get(c.field_name)
            evidence_id = extracted_field_evidence_map.get(ext_field_id) if ext_field_id else None

            ev_link = MismatchEvidence(
                id=uuid.uuid4(),
                mismatch_id=mismatch.id,
                validation_result_id=None,
                extracted_field_id=ext_field_id,
                evidence_id=evidence_id,
            )
            mismatch.evidence_links = [ev_link]
            mismatches.append(mismatch)

        return mismatches
