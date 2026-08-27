import json
from typing import Any, Dict, List, Optional, Tuple
import uuid

import geoalchemy2
from geoalchemy2.functions import (
    ST_Area,
    ST_AsGeoJSON,
    ST_Covers,
    ST_Distance,
    ST_IsValid,
    ST_MakePoint,
    ST_SetSRID,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BoundaryType
from app.models.reference_boundary import ReferenceBoundary
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty


class ParcelProvider:
    """PostGIS spatial provider querying authoritative parcel and boundary geometries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_parcel_by_property_id(
        self, property_id: uuid.UUID
    ) -> Optional[ReferenceParcel]:
        """Fetch authoritative parcel associated with a reference property ID."""
        stmt = select(ReferenceParcel).where(
            ReferenceParcel.reference_property_id == property_id
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_parcel_by_identifiers(
        self,
        survey_number: Optional[str] = None,
        plot_number: Optional[str] = None,
        parcel_number: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> Optional[ReferenceParcel]:
        """Lookup reference parcel geometry via linked reference property identifiers."""
        stmt = (
            select(ReferenceParcel)
            .join(ReferenceParcel.reference_property)
            .where(ReferenceParcel.reference_property_id.is_not(None))
        )

        if source_id:
            stmt = stmt.where(ReferenceParcel.source_id == source_id)

        if parcel_number:
            stmt = stmt.where(ReferenceProperty.parcel_number.ilike(parcel_number.strip()))
        elif survey_number and plot_number:
            stmt = stmt.where(
                ReferenceProperty.survey_number.ilike(survey_number.strip()),
                ReferenceProperty.plot_number.ilike(plot_number.strip()),
            )
        elif survey_number:
            stmt = stmt.where(ReferenceProperty.survey_number.ilike(survey_number.strip()))
        else:
            return None

        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def check_geometry_valid(self, parcel_id: uuid.UUID) -> bool:
        """Run PostGIS ST_IsValid on parcel geometry."""
        stmt = select(ST_IsValid(ReferenceParcel.geometry)).where(
            ReferenceParcel.id == parcel_id
        )
        res = await self.db.execute(stmt)
        val = res.scalar_one_or_none()
        return bool(val)

    async def calculate_geography_area_sqm(self, parcel_id: uuid.UUID) -> float:
        """Compute geodetic surface area in square meters using ST_Area on geography."""
        stmt = select(
            func.ST_Area(func.cast(ReferenceParcel.geometry, geoalchemy2.Geography))
        ).where(ReferenceParcel.id == parcel_id)
        try:
            res = await self.db.execute(stmt)
            val = res.scalar_one_or_none()
            return float(val) if val is not None else 0.0
        except Exception:
            return 0.0

    async def check_point_containment(
        self, lat: float, lon: float, parcel_id: uuid.UUID
    ) -> Tuple[bool, float]:
        """Evaluate if geographic point lies within parcel polygon (covers) and calculate distance in meters if outside."""
        pt_geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)

        # 1. Check boundary-inclusive coverage (ST_Covers)
        covers_stmt = select(
            func.ST_Covers(ReferenceParcel.geometry, pt_geom)
        ).where(ReferenceParcel.id == parcel_id)
        covers_res = await self.db.execute(covers_stmt)
        is_covered = bool(covers_res.scalar_one_or_none())

        if is_covered:
            return True, 0.0

        # 2. Calculate geodetic distance in meters if outside
        dist_stmt = select(
            func.ST_Distance(
                func.cast(ReferenceParcel.geometry, geoalchemy2.Geography),
                func.cast(pt_geom, geoalchemy2.Geography),
            )
        ).where(ReferenceParcel.id == parcel_id)
        dist_res = await self.db.execute(dist_stmt)
        dist_val = dist_res.scalar_one_or_none()
        distance_meters = float(dist_val) if dist_val is not None else 0.0

        return False, round(distance_meters, 2)

    async def find_boundary_containing_point(
        self, lat: float, lon: float, boundary_type: BoundaryType
    ) -> Optional[ReferenceBoundary]:
        """Find administrative boundary polygon covering given point coordinates."""
        pt_geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        stmt = (
            select(ReferenceBoundary)
            .where(
                ReferenceBoundary.boundary_type == boundary_type,
                func.ST_Covers(ReferenceBoundary.geometry, pt_geom),
            )
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_geometry_geojson(self, parcel_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Retrieve geometry formatted as a GeoJSON dictionary."""
        stmt = select(func.ST_AsGeoJSON(ReferenceParcel.geometry)).where(
            ReferenceParcel.id == parcel_id
        )
        res = await self.db.execute(stmt)
        raw_json = res.scalar_one_or_none()
        if raw_json:
            return json.loads(raw_json)
        return None
