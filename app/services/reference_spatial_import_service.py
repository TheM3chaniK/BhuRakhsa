import json
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.enums import BoundaryType, UserRole
from app.models.reference_boundary import ReferenceBoundary
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty
from app.models.user import User


class ReferenceSpatialImportService:
    """Service importing authoritative reference parcel and boundary geometries from GeoJSON payloads via PostGIS."""

    @classmethod
    def _validate_coordinates_range(cls, geom_dict: Dict[str, Any]) -> None:
        """Ensure coordinate numbers conform to WGS84 range."""
        def check_coords(coords: Any) -> None:
            if isinstance(coords, (list, tuple)):
                if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                    lon, lat = float(coords[0]), float(coords[1])
                    if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
                        raise ValueError(f"Coordinate ({lon}, {lat}) out of valid WGS84 range.")
                else:
                    for sub in coords:
                        check_coords(sub)

        if "coordinates" in geom_dict:
            check_coords(geom_dict["coordinates"])

    @staticmethod
    async def import_parcels_geojson(
        db: AsyncSession,
        file: UploadFile,
        user: User,
        dataset_version: str = "1.0",
    ) -> Dict[str, Any]:
        """Import authoritative parcel geometries from GeoJSON FeatureCollection (Super Admin only)."""
        if user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can import reference parcels.",
            )

        content = await file.read()
        try:
            geojson = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GeoJSON file: {str(e)}",
            )

        features = geojson.get("features", [])
        if not features and geojson.get("type") == "Feature":
            features = [geojson]

        if not features:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GeoJSON contains no features.",
            )

        inserted_count = 0
        updated_count = 0

        for idx, feat in enumerate(features):
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} missing geometry.",
                )

            geom_type = geom.get("type")
            if geom_type not in ("Polygon", "MultiPolygon"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} unsupported geometry type '{geom_type}'. Expected Polygon or MultiPolygon.",
                )

            try:
                ReferenceSpatialImportService._validate_coordinates_range(geom)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} coordinate error: {str(e)}",
                )

            source_id = props.get("source_id", "").strip() or "cadastral_map_registry"
            source_record_id = props.get("source_record_id", "").strip() or props.get("parcel_id", "").strip()
            if not source_record_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} missing 'source_record_id' or 'parcel_id' property.",
                )

            # Convert to MultiPolygon geometry expression via PostGIS ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(...), 4326))
            geom_expr = func.ST_Multi(
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geom)), 4326)
            )

            # Link to reference property if reference_property_id or survey/parcel provided
            ref_prop_id = None
            if "reference_property_id" in props and props["reference_property_id"]:
                try:
                    ref_prop_id = uuid.UUID(props["reference_property_id"])
                except ValueError:
                    ref_prop_id = None
            elif "survey_number" in props:
                stmt_prop = select(ReferenceProperty).where(
                    ReferenceProperty.survey_number == props["survey_number"].strip()
                )
                res_prop = await db.execute(stmt_prop)
                p_match = res_prop.scalar_one_or_none()
                if p_match:
                    ref_prop_id = p_match.id

            # Check existing parcel on (source_id, source_record_id)
            stmt_existing = select(ReferenceParcel).where(
                ReferenceParcel.source_id == source_id,
                ReferenceParcel.source_record_id == source_record_id,
            )
            res_existing = await db.execute(stmt_existing)
            existing_parcel = res_existing.scalar_one_or_none()

            area_val = props.get("area")
            try:
                area_num = float(area_val) if area_val is not None else None
            except (ValueError, TypeError):
                area_num = None

            if existing_parcel:
                existing_parcel.geometry = geom_expr
                existing_parcel.area = area_num
                existing_parcel.area_unit = props.get("area_unit", "sq_meters")
                existing_parcel.dataset_version = dataset_version
                if ref_prop_id:
                    existing_parcel.reference_property_id = ref_prop_id
                updated_count += 1
            else:
                new_parcel = ReferenceParcel(
                    id=uuid.uuid4(),
                    reference_property_id=ref_prop_id,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    geometry=geom_expr,
                    area=area_num,
                    area_unit=props.get("area_unit", "sq_meters"),
                    srid=4326,
                    source_srid=4326,
                    dataset_version=dataset_version,
                )
                db.add(new_parcel)
                inserted_count += 1

        await db.commit()
        logger.info(
            "Imported %d parcel features (%d inserted, %d updated).",
            len(features),
            inserted_count,
            updated_count,
        )

        return {
            "total_features": len(features),
            "inserted": inserted_count,
            "updated": updated_count,
            "failed": 0,
        }

    @staticmethod
    async def import_boundaries_geojson(
        db: AsyncSession,
        file: UploadFile,
        boundary_type: BoundaryType,
        user: User,
        dataset_version: str = "1.0",
    ) -> Dict[str, Any]:
        """Import authoritative administrative boundaries from GeoJSON (Super Admin only)."""
        if user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can import reference boundaries.",
            )

        content = await file.read()
        try:
            geojson = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GeoJSON file: {str(e)}",
            )

        features = geojson.get("features", [])
        if not features and geojson.get("type") == "Feature":
            features = [geojson]

        if not features:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GeoJSON contains no features.",
            )

        inserted_count = 0
        updated_count = 0

        for idx, feat in enumerate(features):
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not geom:
                continue

            name = props.get("name", "").strip()
            if not name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} missing required 'name' property.",
                )

            geom_type = geom.get("type")
            if geom_type not in ("Polygon", "MultiPolygon"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} unsupported geometry type '{geom_type}'.",
                )

            try:
                ReferenceSpatialImportService._validate_coordinates_range(geom)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Feature {idx + 1} coordinate error: {str(e)}",
                )

            source_id = props.get("source_id", "admin_boundary_registry").strip()
            source_record_id = props.get("source_record_id", f"{boundary_type.value}_{name}").strip()

            geom_expr = func.ST_Multi(
                func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geom)), 4326)
            )

            norm_name = " ".join(name.lower().split())

            stmt_existing = select(ReferenceBoundary).where(
                ReferenceBoundary.source_id == source_id,
                ReferenceBoundary.source_record_id == source_record_id,
            )
            res_existing = await db.execute(stmt_existing)
            existing_boundary = res_existing.scalar_one_or_none()

            if existing_boundary:
                existing_boundary.name = name
                existing_boundary.normalized_name = norm_name
                existing_boundary.geometry = geom_expr
                existing_boundary.dataset_version = dataset_version
                updated_count += 1
            else:
                new_boundary = ReferenceBoundary(
                    id=uuid.uuid4(),
                    source_id=source_id,
                    source_record_id=source_record_id,
                    boundary_type=boundary_type,
                    name=name,
                    normalized_name=norm_name,
                    geometry=geom_expr,
                    source_srid=4326,
                    dataset_version=dataset_version,
                )
                db.add(new_boundary)
                inserted_count += 1

        await db.commit()
        return {
            "total_features": len(features),
            "inserted": inserted_count,
            "updated": updated_count,
            "failed": 0,
        }
