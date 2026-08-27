from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.db.session import async_session_factory
from app.models.case import Case
from app.models.document import Document
from app.models.enums import (
    CandidateSelectionStatus,
    CoordinateSource,
    DocumentStatus,
    ExtractionStatus,
    ProfileStatus,
    UserRole,
    ValidationStatus,
    ValidationType,
)
from app.models.extraction import ExtractedField
from app.models.property_field_conflict import PropertyFieldConflict
from app.models.property_field_source import PropertyFieldSource
from app.models.property_owner import PropertyOwner
from app.models.property_profile import PropertyProfile
from app.models.reference_property import ReferenceProperty
from app.models.user import User
from app.models.validation import ValidationRun
from app.models.validation_candidate import ValidationCandidate
from app.models.validation_result import ValidationResult
from app.services.case_access_service import CaseAccessService
from app.services.property_field_mapping import FIELD_MAPPING, PropertyFieldMapper
from app.services.validation.database_validator import DatabaseValidator
from app.services.validation.gis_validator import GISValidator
from app.services.validation.parcel_provider import ParcelProvider


class PropertyProfileService:
    """Service orchestrating the generation and retrieval of canonical Property Profiles, Validation Runs, and Spatial Map Data."""

    @staticmethod
    async def generate_profile(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: Optional[User] = None,
        force_refresh: bool = False,
    ) -> PropertyProfile:
        """Construct or refresh the canonical PropertyProfile from completed case document extractions."""
        # 1. Fetch case & verify access
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        if user is not None:
            await CaseAccessService.verify_case_access(db, user, case)

        # 2. Check for existing profile if not forcing refresh
        existing_profile_res = await db.execute(
            select(PropertyProfile)
            .where(PropertyProfile.case_id == case_id)
            .options(
                selectinload(PropertyProfile.owners),
                selectinload(PropertyProfile.field_sources),
                selectinload(PropertyProfile.conflicts),
                selectinload(PropertyProfile.validation_runs),
            )
        )
        existing_profile = existing_profile_res.scalar_one_or_none()
        if existing_profile and not force_refresh:
            return existing_profile

        # 3. Check case documents and completed extractions
        docs_res = await db.execute(
            select(Document).where(
                Document.case_id == case_id,
                Document.deleted_at.is_(None),
            )
        )
        documents = docs_res.scalars().all()
        if not documents:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No documents found for this case.",
            )

        processed_doc_ids = [
            d.id for d in documents if d.status == DocumentStatus.PROCESSED
        ]
        if not processed_doc_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Extraction has not completed for any case documents.",
            )

        # 4. Fetch all extracted fields for processed documents
        fields_res = await db.execute(
            select(ExtractedField)
            .where(
                ExtractedField.document_id.in_(processed_doc_ids),
                ExtractedField.status != ExtractionStatus.NOT_FOUND,
            )
            .order_by(ExtractedField.confidence.desc())
        )
        extracted_fields = fields_res.scalars().all()
        if not extracted_fields:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Extraction has not completed for any case documents.",
            )

        # 5. Clean prior profile if refreshing
        if existing_profile:
            await db.execute(
                delete(PropertyProfile).where(PropertyProfile.case_id == case_id)
            )
            await db.flush()

        # 6. Group extracted fields by field_name to detect conflicts and select best value
        grouped_fields: Dict[str, List[ExtractedField]] = {}
        for ef in extracted_fields:
            grouped_fields.setdefault(ef.field_name, []).append(ef)

        conflicts_to_create: List[PropertyFieldConflict] = []
        best_fields: Dict[str, ExtractedField] = {}
        has_conflicts = False

        # Identify conflicts across differing extractions
        for fname, flist in grouped_fields.items():
            best_fields[fname] = flist[0]  # Highest confidence first
            distinct_values = set(
                f.normalized_value or f.field_value.strip().lower()
                for f in flist
                if f.field_value and f.field_value.strip()
            )
            if len(distinct_values) > 1 and len(flist) >= 2:
                has_conflicts = True
                f_a = flist[0]
                f_b = flist[1]
                conflicts_to_create.append(
                    PropertyFieldConflict(
                        id=uuid.uuid4(),
                        field_name=fname,
                        value_a=f_a.field_value or "",
                        value_b=f_b.field_value or "",
                        source_a=f"Document {f_a.document_id} (conf: {f_a.confidence:.2f})",
                        source_b=f"Document {f_b.document_id} (conf: {f_b.confidence:.2f})",
                    )
                )

        # 7. Create canonical PropertyProfile entity
        profile_status = (
            ProfileStatus.DRAFT if has_conflicts else ProfileStatus.EXTRACTED
        )
        profile = PropertyProfile(
            id=uuid.uuid4(),
            case_id=case_id,
            status=profile_status,
        )

        # Map scalar fields from highest confidence extractions
        for ext_name, prof_attr in FIELD_MAPPING.items():
            if ext_name in best_fields and best_fields[ext_name].field_value:
                setattr(profile, prof_attr, best_fields[ext_name].field_value)

        # Area and unit parsing
        raw_area_field = best_fields.get("property_area") or best_fields.get("land_area")
        if raw_area_field and raw_area_field.field_value:
            num_area, unit_area = PropertyFieldMapper.parse_area_and_unit(
                raw_area_field.field_value
            )
            profile.property_area = num_area
            profile.area_unit = unit_area

        # Latitude / Longitude & PostGIS location_point
        lat_field = best_fields.get("latitude")
        lon_field = best_fields.get("longitude")
        if lat_field and lon_field and lat_field.field_value and lon_field.field_value:
            try:
                lat_val = float(lat_field.field_value.strip())
                lon_val = float(lon_field.field_value.strip())
                if -90.0 <= lat_val <= 90.0 and -180.0 <= lon_val <= 180.0:
                    profile.latitude = lat_val
                    profile.longitude = lon_val
                    profile.location_point = f"SRID=4326;POINT({lon_val} {lat_val})"
                    profile.coordinate_source = CoordinateSource.DOCUMENT
            except (ValueError, TypeError):
                pass

        # Composite property identifier
        if profile.survey_number and profile.village:
            profile.property_identifier = f"SURVEY-{profile.survey_number}-{profile.village.upper()}"
        elif profile.survey_number:
            profile.property_identifier = f"SURVEY-{profile.survey_number}"
        elif profile.parcel_number:
            profile.property_identifier = f"PARCEL-{profile.parcel_number}"

        db.add(profile)
        await db.flush()

        # 8. Create PropertyOwner records
        owner_name_val = (
            best_fields["owner_name"].field_value
            if "owner_name" in best_fields
            else None
        )
        co_owners_val = (
            best_fields["co_owner_names"].field_value
            if "co_owner_names" in best_fields
            else None
        )
        parsed_owners = PropertyFieldMapper.parse_owners(
            owner_name=owner_name_val,
            co_owners=co_owners_val,
        )
        for o_data in parsed_owners:
            owner_obj = PropertyOwner(
                id=uuid.uuid4(),
                property_profile_id=profile.id,
                name=o_data["name"],
                normalized_name=o_data["normalized_name"],
                ownership_type=o_data["ownership_type"],
            )
            db.add(owner_obj)

        # 9. Create PropertyFieldSource traceability links
        for fname, ef in best_fields.items():
            if ef.field_value:
                source_link = PropertyFieldSource(
                    id=uuid.uuid4(),
                    property_profile_id=profile.id,
                    field_name=fname,
                    extracted_field_id=ef.id,
                    confidence=ef.confidence,
                )
                db.add(source_link)

        # 10. Link conflicts if any
        for conflict in conflicts_to_create:
            conflict.property_profile_id = profile.id
            db.add(conflict)

        await db.commit()

        # Reload with all relationships
        profile_reloaded = await PropertyProfileService.get_profile(
            db=db,
            case_id=case_id,
            user=user,
        )
        return profile_reloaded

    @staticmethod
    async def get_profile(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> PropertyProfile:
        """Retrieve the canonical PropertyProfile for a case."""
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        res = await db.execute(
            select(PropertyProfile)
            .where(PropertyProfile.case_id == case_id)
            .options(
                selectinload(PropertyProfile.owners),
                selectinload(PropertyProfile.field_sources),
                selectinload(PropertyProfile.conflicts),
                selectinload(PropertyProfile.validation_runs),
            )
        )
        profile = res.scalar_one_or_none()
        if not profile:
            try:
                return await PropertyProfileService.generate_profile(
                    db=db,
                    case_id=case_id,
                    user=user,
                    force_refresh=False,
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Property profile has not been generated for this case.",
                )
        return profile

    @staticmethod
    async def create_validation_run(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
        validation_type: ValidationType,
    ) -> ValidationRun:
        """Schedule a validation run in PENDING status (restricted to Area Officers and Super Admins)."""
        if user.role == UserRole.CIVILIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Civilians cannot trigger validation runs.",
            )

        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        profile_res = await db.execute(
            select(PropertyProfile).where(PropertyProfile.case_id == case_id)
        )
        profile = profile_res.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property profile not found for case.",
            )

        run = ValidationRun(
            id=uuid.uuid4(),
            property_profile_id=profile.id,
            validation_type=validation_type,
            status=ValidationStatus.PENDING,
            validator_version="1.0",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        logger.info(
            "Created %s validation run %s for property profile %s (case %s).",
            validation_type.value,
            run.id,
            profile.id,
            case_id,
        )
        return run

    @staticmethod
    async def execute_validation_run(run_id: uuid.UUID) -> None:
        """Background asynchronous execution pipeline for a ValidationRun."""
        async with async_session_factory() as db:
            run_res = await db.execute(
                select(ValidationRun)
                .where(ValidationRun.id == run_id)
                .options(
                    selectinload(ValidationRun.property_profile).selectinload(
                        PropertyProfile.owners
                    ),
                    selectinload(ValidationRun.property_profile).selectinload(
                        PropertyProfile.field_sources
                    ),
                )
            )
            run = run_res.scalar_one_or_none()
            if not run or run.status not in (
                ValidationStatus.PENDING,
                ValidationStatus.RUNNING,
            ):
                return

            profile = run.property_profile
            if not profile:
                run.status = ValidationStatus.ERROR
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            if run.validation_type == ValidationType.DATABASE:
                validator = DatabaseValidator(db)
                status_outcome, results, candidates = await validator.validate_run(
                    run, profile
                )

                for c in candidates:
                    db.add(c)
                for r in results:
                    db.add(r)

                run.status = status_outcome
                await db.commit()
                logger.info(
                    "Database validation run %s finished with status %s and %d results.",
                    run.id,
                    run.status.value,
                    len(results),
                )

            elif run.validation_type == ValidationType.GIS:
                # Find linked reference property if exists from prior database run
                ref_prop = None
                prior_runs_res = await db.execute(
                    select(ValidationCandidate)
                    .join(ValidationCandidate.validation_run)
                    .where(
                        ValidationRun.property_profile_id == profile.id,
                        ValidationCandidate.selection_status == CandidateSelectionStatus.SELECTED,
                    )
                )
                selected_cand = prior_runs_res.scalars().first()
                if selected_cand:
                    p_res = await db.execute(
                        select(ReferenceProperty).where(
                            ReferenceProperty.source_id == selected_cand.source_id,
                            ReferenceProperty.source_record_id == selected_cand.source_record_id,
                        )
                    )
                    ref_prop = p_res.scalar_one_or_none()

                gis_validator = GISValidator(db)
                status_outcome, results = await gis_validator.validate_run(
                    run=run, profile=profile, ref_prop=ref_prop
                )

                for r in results:
                    db.add(r)

                run.status = status_outcome
                await db.commit()
                logger.info(
                    "GIS validation run %s finished with status %s and %d results.",
                    run.id,
                    run.status.value,
                    len(results),
                )

    @staticmethod
    async def list_validation_runs(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> List[ValidationRun]:
        """List validation runs for a case's property profile."""
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        profile_res = await db.execute(
            select(PropertyProfile).where(PropertyProfile.case_id == case_id)
        )
        profile = profile_res.scalar_one_or_none()
        if not profile:
            return []

        runs_res = await db.execute(
            select(ValidationRun)
            .where(ValidationRun.property_profile_id == profile.id)
            .order_by(ValidationRun.created_at.desc())
        )
        return list(runs_res.scalars().all())

    @staticmethod
    async def get_validation_run(
        db: AsyncSession,
        validation_run_id: uuid.UUID,
        user: User,
    ) -> ValidationRun:
        """Retrieve a specific validation run with results and candidates."""
        run_res = await db.execute(
            select(ValidationRun)
            .where(ValidationRun.id == validation_run_id)
            .options(
                selectinload(ValidationRun.results),
                selectinload(ValidationRun.candidates),
                selectinload(ValidationRun.property_profile),
            )
        )
        run = run_res.scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Validation run not found.",
            )

        case_res = await db.execute(
            select(Case).where(Case.id == run.property_profile.case_id)
        )
        case = case_res.scalar_one_or_none()
        if case:
            await CaseAccessService.verify_case_access(db, user, case)

        return run

    @staticmethod
    async def get_case_map_data(
        db: AsyncSession,
        case_id: uuid.UUID,
        user: User,
    ) -> Dict[str, Any]:
        """Fetch spatial map layers (point, reference parcel polygon, administrative boundaries) for authorized visualization."""
        case_res = await db.execute(select(Case).where(Case.id == case_id))
        case = case_res.scalar_one_or_none()
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found.",
            )
        await CaseAccessService.verify_case_access(db, user, case)

        profile = await PropertyProfileService.get_profile(db, case_id, user)
        provider = ParcelProvider(db)

        # 1. Document location point GeoJSON
        point_geojson = None
        if profile.latitude is not None and profile.longitude is not None:
            point_geojson = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [profile.longitude, profile.latitude],
                },
                "properties": {
                    "source": profile.coordinate_source.value if profile.coordinate_source else "document",
                    "latitude": profile.latitude,
                    "longitude": profile.longitude,
                },
            }

        # 2. Reference parcel GeoJSON
        parcel_geojson = None
        parcel = await provider.get_parcel_by_identifiers(
            survey_number=profile.survey_number,
            plot_number=profile.plot_number,
            parcel_number=profile.parcel_number,
        )
        if parcel:
            raw_geom = await provider.get_geometry_geojson(parcel.id)
            if raw_geom:
                parcel_geojson = {
                    "type": "Feature",
                    "geometry": raw_geom,
                    "properties": {
                        "source_id": parcel.source_id,
                        "source_record_id": parcel.source_record_id,
                        "area": parcel.area,
                        "area_unit": parcel.area_unit,
                    },
                }

        # 3. GIS validation status summary
        latest_gis_run_res = await db.execute(
            select(ValidationRun)
            .where(
                ValidationRun.property_profile_id == profile.id,
                ValidationRun.validation_type == ValidationType.GIS,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        latest_gis_run = latest_gis_run_res.scalars().first()

        return {
            "case_id": case_id,
            "property_identifier": profile.property_identifier,
            "property_point": point_geojson,
            "reference_parcel": parcel_geojson,
            "gis_validation_status": latest_gis_run.status.value if latest_gis_run else "not_run",
        }
