from typing import List
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.enums import MatchStatus, UserRole, ValidationStatus, ValidationType
from app.models.user import User
from app.schemas.property_profile import PropertyProfileResponse
from app.schemas.validation import (
    CaseMapDataResponse,
    GISCheckResult,
    GISValidationRunResponse,
    ValidationResultResponse,
    ValidationRunCreate,
    ValidationRunDetailResponse,
    ValidationRunResponse,
)
from app.services.property_profile_service import PropertyProfileService
from app.workers.document_worker import DocumentWorker

router = APIRouter(tags=["Property Profiles & Validation"])


@router.post(
    "/cases/{case_id}/property-profile/generate",
    response_model=PropertyProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Canonical Property Profile",
    description="Assemble the canonical Evidence-linked Property Profile from completed document extractions.",
)
async def generate_property_profile(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PropertyProfileResponse:
    """Generate or retrieve canonical property profile for a case."""
    profile = await PropertyProfileService.generate_profile(
        db=db,
        case_id=case_id,
        user=current_user,
        force_refresh=False,
    )
    return PropertyProfileResponse.model_validate(profile)


@router.post(
    "/cases/{case_id}/property-profile/refresh",
    response_model=PropertyProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Canonical Property Profile",
    description="Force re-generation of the canonical property profile from latest extracted fields.",
)
async def refresh_property_profile(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PropertyProfileResponse:
    """Force refresh the canonical property profile."""
    profile = await PropertyProfileService.generate_profile(
        db=db,
        case_id=case_id,
        user=current_user,
        force_refresh=True,
    )
    return PropertyProfileResponse.model_validate(profile)


@router.get(
    "/cases/{case_id}/property-profile",
    response_model=PropertyProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Property Profile",
    description="Retrieve the canonical Property Profile for a case with linked owners, field sources, and conflicts.",
)
async def get_property_profile(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PropertyProfileResponse:
    """Get the canonical property profile for a case."""
    profile = await PropertyProfileService.get_profile(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return PropertyProfileResponse.model_validate(profile)


@router.get(
    "/cases/{case_id}/property-profile/map",
    response_model=CaseMapDataResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Case Map Layers",
    description="Retrieve authorized spatial GeoJSON layers for case (property point, parcel polygon, GIS status).",
)
async def get_case_map_data(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CaseMapDataResponse:
    """Retrieve spatial GeoJSON map features for authorized case reviewer."""
    map_data = await PropertyProfileService.get_case_map_data(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return CaseMapDataResponse(**map_data)


@router.post(
    "/cases/{case_id}/property-profile/validation-runs",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Validation Run",
    description="Schedule an external reference validation run (Area Officer or Super Admin only).",
)
async def create_validation_run(
    case_id: uuid.UUID,
    payload: ValidationRunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationRunResponse:
    """Create and dispatch an asynchronous validation run in PENDING status."""
    run = await PropertyProfileService.create_validation_run(
        db=db,
        case_id=case_id,
        user=current_user,
        validation_type=payload.validation_type,
    )

    if run.status == ValidationStatus.PENDING:
        background_tasks.add_task(DocumentWorker._execute_validation_run, run.id)

    return ValidationRunResponse.model_validate(run)


@router.get(
    "/cases/{case_id}/property-profile/validation-runs",
    response_model=List[ValidationRunResponse],
    status_code=status.HTTP_200_OK,
    summary="List Case Validation Runs",
    description="List all validation runs triggered for a case's property profile.",
)
async def list_case_validation_runs(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ValidationRunResponse]:
    """List validation runs for a case."""
    runs = await PropertyProfileService.list_validation_runs(
        db=db,
        case_id=case_id,
        user=current_user,
    )
    return [ValidationRunResponse.model_validate(r) for r in runs]


@router.get(
    "/validation-runs/{validation_run_id}",
    response_model=ValidationRunDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Validation Run Detail",
    description="Retrieve details, candidate matches, and field comparison results of a specific validation run.",
)
async def get_validation_run_detail(
    validation_run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ValidationRunDetailResponse:
    """Retrieve validation run details and field outcomes."""
    run = await PropertyProfileService.get_validation_run(
        db=db,
        validation_run_id=validation_run_id,
        user=current_user,
    )
    return ValidationRunDetailResponse.model_validate(run)


@router.get(
    "/validation-runs/{validation_run_id}/results",
    response_model=List[ValidationResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Validation Results",
    description="Retrieve individual field comparison outcomes for a validation run.",
)
async def get_validation_results(
    validation_run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ValidationResultResponse]:
    """Retrieve field comparison results for a validation session."""
    run = await PropertyProfileService.get_validation_run(
        db=db,
        validation_run_id=validation_run_id,
        user=current_user,
    )

    results = []
    is_privileged = current_user.role in (UserRole.AREA_OFFICER, UserRole.SUPER_ADMIN)

    for r in run.results:
        if is_privileged:
            results.append(ValidationResultResponse.model_validate(r))
        else:
            # Mask internal provider specifics for civilians
            results.append(
                ValidationResultResponse(
                    id=r.id,
                    validation_run_id=r.validation_run_id,
                    field_name=r.field_name,
                    document_value=r.document_value,
                    reference_value=None,  # Do not leak external database details
                    match_status=r.match_status,
                    match_score=r.match_score,
                    mismatch_reason=r.mismatch_reason,
                    source_id=None,
                    source_record_id=None,
                    geometry_distance_meters=r.geometry_distance_meters,
                    geometry_area=None,
                    reference_area=None,
                    coordinate_latitude=r.coordinate_latitude,
                    coordinate_longitude=r.coordinate_longitude,
                    created_at=r.created_at,
                )
            )

    return results


@router.get(
    "/validation-runs/{validation_run_id}/gis",
    response_model=GISValidationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get GIS Validation Checks",
    description="Retrieve structured GIS check outcomes (containment, distance, area consistency).",
)
async def get_gis_validation_checks(
    validation_run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GISValidationRunResponse:
    """Retrieve structured spatial checks for a GIS validation session."""
    run = await PropertyProfileService.get_validation_run(
        db=db,
        validation_run_id=validation_run_id,
        user=current_user,
    )

    if run.validation_type != ValidationType.GIS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Validation run is not a GIS validation type.",
        )

    checks = []
    for r in run.results:
        checks.append(
            GISCheckResult(
                check=r.field_name,
                status=r.match_status,
                distance_meters=r.geometry_distance_meters,
                geometry_area=r.geometry_area,
                reference_area=r.reference_area,
                mismatch_reason=r.mismatch_reason,
            )
        )

    return GISValidationRunResponse(
        validation_run_id=run.id,
        status=run.status,
        checks=checks,
    )
