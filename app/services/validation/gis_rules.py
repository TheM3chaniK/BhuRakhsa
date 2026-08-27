from typing import List, Optional
import uuid

from app.core.config import settings
from app.models.enums import BoundaryType, MatchStatus, MismatchReason
from app.models.property_profile import PropertyProfile
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty
from app.models.validation_result import ValidationResult
from app.services.normalization.area import AreaNormalizer
from app.services.validation.parcel_provider import ParcelProvider


class ParcelExistsRule:
    """Evaluates whether an authoritative reference parcel record exists for the property."""

    @classmethod
    def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        parcel: Optional[ReferenceParcel],
    ) -> ValidationResult:
        if parcel is None:
            return ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="parcel_existence",
                document_value=profile.property_identifier or profile.parcel_number or profile.survey_number,
                reference_value=None,
                match_status=MatchStatus.NOT_FOUND,
                match_score=0.0,
                mismatch_reason=MismatchReason.PARCEL_NOT_FOUND.value,
            )

        return ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="parcel_existence",
            document_value=profile.property_identifier or profile.parcel_number or profile.survey_number,
            reference_value=parcel.source_record_id,
            match_status=MatchStatus.MATCH,
            match_score=1.0,
            source_id=parcel.source_id,
            source_record_id=parcel.source_record_id,
        )


class GeometryValidRule:
    """Evaluates whether the authoritative reference parcel geometry is topologically valid."""

    @classmethod
    async def evaluate(
        cls,
        run_id: uuid.UUID,
        parcel: ReferenceParcel,
        provider: ParcelProvider,
    ) -> ValidationResult:
        if parcel.geometry is None:
            return ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="parcel_geometry",
                document_value=None,
                reference_value=None,
                match_status=MatchStatus.NOT_FOUND,
                match_score=0.0,
                mismatch_reason=MismatchReason.PARCEL_GEOMETRY_NOT_FOUND.value,
                source_id=parcel.source_id,
                source_record_id=parcel.source_record_id,
            )

        is_valid = await provider.check_geometry_valid(parcel.id)
        if not is_valid:
            return ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="parcel_geometry",
                document_value=None,
                reference_value="INVALID",
                match_status=MatchStatus.MISMATCH,
                match_score=0.0,
                mismatch_reason=MismatchReason.INVALID_PARCEL_GEOMETRY.value,
                source_id=parcel.source_id,
                source_record_id=parcel.source_record_id,
            )

        return ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="parcel_geometry",
            document_value=None,
            reference_value="VALID",
            match_status=MatchStatus.MATCH,
            match_score=1.0,
            source_id=parcel.source_id,
            source_record_id=parcel.source_record_id,
        )


class PointInsideParcelRule:
    """Evaluates whether document/profile coordinate points lie inside the reference parcel boundary."""

    @classmethod
    async def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        parcel: ReferenceParcel,
        provider: ParcelProvider,
    ) -> ValidationResult:
        if profile.latitude is None or profile.longitude is None:
            return ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="point_inside_parcel",
                document_value=None,
                reference_value=parcel.source_record_id,
                match_status=MatchStatus.NOT_CHECKED,
                match_score=0.0,
                mismatch_reason=MismatchReason.LOCATION_POINT_NOT_AVAILABLE.value,
                source_id=parcel.source_id,
                source_record_id=parcel.source_record_id,
            )

        lat = profile.latitude
        lon = profile.longitude
        coord_str = f"POINT({lat:.6f}, {lon:.6f})"

        is_inside, distance_meters = await provider.check_point_containment(
            lat=lat, lon=lon, parcel_id=parcel.id
        )

        if is_inside:
            return ValidationResult(
                id=uuid.uuid4(),
                validation_run_id=run_id,
                field_name="point_inside_parcel",
                document_value=coord_str,
                reference_value=f"Inside Parcel {parcel.source_record_id}",
                match_status=MatchStatus.MATCH,
                match_score=1.0,
                geometry_distance_meters=0.0,
                coordinate_latitude=lat,
                coordinate_longitude=lon,
                source_id=parcel.source_id,
                source_record_id=parcel.source_record_id,
            )

        return ValidationResult(
            id=uuid.uuid4(),
            validation_run_id=run_id,
            field_name="point_inside_parcel",
            document_value=coord_str,
            reference_value=f"Outside Parcel {parcel.source_record_id}",
            match_status=MatchStatus.MISMATCH,
            match_score=0.0,
            geometry_distance_meters=distance_meters,
            coordinate_latitude=lat,
            coordinate_longitude=lon,
            mismatch_reason=MismatchReason.POINT_OUTSIDE_PARCEL.value,
            source_id=parcel.source_id,
            source_record_id=parcel.source_record_id,
        )


class AreaConsistencyRule:
    """Evaluates geometric area calculated by PostGIS against reference and document declared areas."""

    @classmethod
    async def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        parcel: ReferenceParcel,
        ref_prop: Optional[ReferenceProperty],
        provider: ParcelProvider,
        tolerance_percent: Optional[float] = None,
    ) -> List[ValidationResult]:
        tol = (
            tolerance_percent
            if tolerance_percent is not None
            else settings.GIS_AREA_TOLERANCE_PERCENT
        )
        results: List[ValidationResult] = []

        # Compute PostGIS geodetic area in square meters
        computed_sqm = await provider.calculate_geography_area_sqm(parcel.id)
        if computed_sqm <= 0.0 and parcel.area:
            # Fallback if stored area present
            computed_sqm = parcel.area

        computed_area_str = f"{computed_sqm:.2f} sq_meters"

        # 1. Compare Reference Record Area vs GIS Geometry Area
        if ref_prop and ref_prop.property_area is not None:
            ref_sqm = AreaNormalizer.to_square_meters(
                ref_prop.property_area, ref_prop.area_unit
            )
            if ref_sqm is not None and ref_sqm > 0:
                diff_pct = abs(computed_sqm - ref_sqm) / ref_sqm * 100.0
                is_match = diff_pct <= tol
                score = max(0.0, min(1.0, 1.0 - (diff_pct / 100.0)))
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name="reference_gis_area",
                        document_value=f"{ref_prop.property_area} {ref_prop.area_unit or ''}".strip(),
                        reference_value=computed_area_str,
                        match_status=MatchStatus.MATCH if is_match else MatchStatus.MISMATCH,
                        match_score=round(score, 2),
                        geometry_area=computed_sqm,
                        reference_area=ref_sqm,
                        mismatch_reason=None if is_match else MismatchReason.REFERENCE_GIS_AREA_MISMATCH.value,
                        source_id=parcel.source_id,
                        source_record_id=parcel.source_record_id,
                    )
                )

        # 2. Compare Document Stated Area vs GIS Geometry Area
        if profile.property_area is not None:
            doc_sqm = AreaNormalizer.to_square_meters(
                profile.property_area, profile.area_unit
            )
            if doc_sqm is not None and doc_sqm > 0:
                diff_pct = abs(computed_sqm - doc_sqm) / doc_sqm * 100.0
                is_match = diff_pct <= tol
                score = max(0.0, min(1.0, 1.0 - (diff_pct / 100.0)))
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name="document_gis_area",
                        document_value=f"{profile.property_area} {profile.area_unit or ''}".strip(),
                        reference_value=computed_area_str,
                        match_status=MatchStatus.MATCH if is_match else MatchStatus.MISMATCH,
                        match_score=round(score, 2),
                        geometry_area=computed_sqm,
                        reference_area=doc_sqm,
                        mismatch_reason=None if is_match else MismatchReason.DOCUMENT_GIS_AREA_MISMATCH.value,
                        source_id=parcel.source_id,
                        source_record_id=parcel.source_record_id,
                    )
                )

        return results


class AdministrativeBoundaryRule:
    """Evaluates whether coordinates or parcel fall within the declared administrative boundaries."""

    @classmethod
    async def evaluate(
        cls,
        run_id: uuid.UUID,
        profile: PropertyProfile,
        parcel: ReferenceParcel,
        provider: ParcelProvider,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        if profile.latitude is None or profile.longitude is None:
            return results

        # 1. District boundary check
        if profile.district:
            b_district = await provider.find_boundary_containing_point(
                profile.latitude, profile.longitude, BoundaryType.DISTRICT
            )
            if b_district:
                is_match = (
                    " ".join(profile.district.lower().split())
                    == b_district.normalized_name
                )
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name="district_boundary",
                        document_value=profile.district,
                        reference_value=b_district.name,
                        match_status=MatchStatus.MATCH if is_match else MatchStatus.MISMATCH,
                        match_score=1.0 if is_match else 0.0,
                        mismatch_reason=None if is_match else MismatchReason.DISTRICT_LOCATION_MISMATCH.value,
                        source_id=b_district.source_id,
                        source_record_id=b_district.source_record_id,
                    )
                )

        # 2. Village boundary check
        if profile.village:
            b_village = await provider.find_boundary_containing_point(
                profile.latitude, profile.longitude, BoundaryType.VILLAGE
            )
            if b_village:
                is_match = (
                    " ".join(profile.village.lower().split())
                    == b_village.normalized_name
                )
                results.append(
                    ValidationResult(
                        id=uuid.uuid4(),
                        validation_run_id=run_id,
                        field_name="village_boundary",
                        document_value=profile.village,
                        reference_value=b_village.name,
                        match_status=MatchStatus.MATCH if is_match else MatchStatus.MISMATCH,
                        match_score=1.0 if is_match else 0.0,
                        mismatch_reason=None if is_match else MismatchReason.VILLAGE_LOCATION_MISMATCH.value,
                        source_id=b_village.source_id,
                        source_record_id=b_village.source_record_id,
                    )
                )

        return results
