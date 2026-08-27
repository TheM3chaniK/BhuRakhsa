from typing import Any, Dict
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_role
from app.db.session import get_db
from app.models.enums import BoundaryType, UserRole
from app.models.user import User
from app.schemas.reference_property import ReferenceImportResponse
from app.services.reference_import_service import ReferenceImportService
from app.services.reference_spatial_import_service import ReferenceSpatialImportService

router = APIRouter(prefix="", tags=["Admin: Reference Datasets"])


@router.post(
    "/reference-properties/import",
    response_model=ReferenceImportResponse,
    status_code=status.HTTP_200_OK,
    summary="Import Reference Property Dataset",
    description="Upload authoritative property records via CSV or JSON file (Super Admin only).",
)
async def import_reference_dataset(
    file: UploadFile = File(..., description="CSV or JSON file containing authoritative property records"),
    dataset_version: str = Form("1.0", description="Version identifier for this reference snapshot"),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ReferenceImportResponse:
    """Import and upsert authoritative property reference dataset."""
    result = await ReferenceImportService.import_reference_dataset(
        db=db,
        file=file,
        user=current_user,
        dataset_version=dataset_version,
    )
    return ReferenceImportResponse(**result)


@router.post(
    "/reference-parcels/import",
    status_code=status.HTTP_200_OK,
    summary="Import Reference Parcels GeoJSON",
    description="Upload authoritative cadastral parcel geometries via GeoJSON (Super Admin only).",
)
async def import_reference_parcels(
    file: UploadFile = File(..., description="GeoJSON FeatureCollection file containing parcel polygons"),
    dataset_version: str = Form("1.0", description="Version identifier for this parcel dataset"),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Import and upsert reference parcel geometries."""
    return await ReferenceSpatialImportService.import_parcels_geojson(
        db=db,
        file=file,
        user=current_user,
        dataset_version=dataset_version,
    )


@router.post(
    "/reference-boundaries/import",
    status_code=status.HTTP_200_OK,
    summary="Import Reference Boundaries GeoJSON",
    description="Upload authoritative administrative boundary polygons via GeoJSON (Super Admin only).",
)
async def import_reference_boundaries(
    file: UploadFile = File(..., description="GeoJSON FeatureCollection file containing boundary polygons"),
    boundary_type: BoundaryType = Form(..., description="Administrative boundary level ('district', 'village', etc.)"),
    dataset_version: str = Form("1.0", description="Version identifier for this boundary dataset"),
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Import and upsert administrative boundary geometries."""
    return await ReferenceSpatialImportService.import_boundaries_geojson(
        db=db,
        file=file,
        boundary_type=boundary_type,
        user=current_user,
        dataset_version=dataset_version,
    )
