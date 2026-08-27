from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.enums import MatchStatus, ValidationStatus
from app.models.property_profile import PropertyProfile
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty
from app.models.validation import ValidationRun
from app.models.validation_result import ValidationResult
from app.services.validation.base import Validator
from app.services.validation.gis_rules import (
    AdministrativeBoundaryRule,
    AreaConsistencyRule,
    GeometryValidRule,
    ParcelExistsRule,
    PointInsideParcelRule,
)
from app.services.validation.parcel_provider import ParcelProvider


class GISValidator(Validator):
    """Orchestrates spatial parcel lookup, topological geometry validation, point containment, and boundary checks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.provider = ParcelProvider(db)

    async def find_parcel(
        self, profile: PropertyProfile, ref_prop: Optional[ReferenceProperty] = None
    ) -> Optional[ReferenceParcel]:
        """Lookup reference parcel geometry corresponding to the property profile."""
        if ref_prop:
            p = await self.provider.get_parcel_by_property_id(ref_prop.id)
            if p:
                return p

        return await self.provider.get_parcel_by_identifiers(
            survey_number=profile.survey_number,
            plot_number=profile.plot_number,
            parcel_number=profile.parcel_number,
        )

    async def validate(self, profile: PropertyProfile) -> List[ValidationResult]:
        """Base implementation: delegated to validate_run."""
        raise NotImplementedError("Use validate_run with a persistent ValidationRun instance.")

    async def validate_run(
        self,
        run: ValidationRun,
        profile: PropertyProfile,
        ref_prop: Optional[ReferenceProperty] = None,
    ) -> Tuple[ValidationStatus, List[ValidationResult]]:
        """Execute complete spatial / GIS validation lifecycle for a ValidationRun."""
        run.started_at = datetime.now(timezone.utc)
        run.status = ValidationStatus.RUNNING

        # 1. Parcel lookup
        parcel = await self.find_parcel(profile, ref_prop)

        # 2. Check 1 — Parcel Exists
        exists_result = ParcelExistsRule.evaluate(run.id, profile, parcel)
        if exists_result.match_status != MatchStatus.MATCH or parcel is None:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            return ValidationStatus.FAILED, [exists_result]

        results: List[ValidationResult] = [exists_result]
        run.source_id = parcel.source_id
        run.dataset_version = parcel.dataset_version
        run.validator_version = "1.0"

        # 3. Check 2 & 3 — Geometry Validity
        geom_result = await GeometryValidRule.evaluate(run.id, parcel, self.provider)
        results.append(geom_result)
        if geom_result.match_status != MatchStatus.MATCH:
            run.status = ValidationStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            return ValidationStatus.FAILED, results

        # 4. Check 4 — Point Inside Parcel
        point_result = await PointInsideParcelRule.evaluate(
            run.id, profile, parcel, self.provider
        )
        results.append(point_result)

        # 5. Check 5 — Area Consistency
        area_results = await AreaConsistencyRule.evaluate(
            run.id, profile, parcel, ref_prop, self.provider
        )
        results.extend(area_results)

        # 6. Check 6 — Administrative Boundary Validation
        boundary_results = await AdministrativeBoundaryRule.evaluate(
            run.id, profile, parcel, self.provider
        )
        results.extend(boundary_results)

        # 7. Determine overall run status
        has_mismatch = any(r.match_status == MatchStatus.MISMATCH for r in results)
        has_skipped_point = point_result.match_status == MatchStatus.NOT_CHECKED

        if has_mismatch:
            run.status = ValidationStatus.FAILED
        elif has_skipped_point:
            run.status = ValidationStatus.PASSED_WITH_LIMITATIONS
        else:
            run.status = ValidationStatus.PASSED

        run.completed_at = datetime.now(timezone.utc)
        return run.status, results
