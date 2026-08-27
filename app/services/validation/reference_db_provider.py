from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.reference_property import ReferenceProperty
from app.services.normalization.identifier import IdentifierNormalizer


class ReferencePropertyProvider:
    """PostgreSQL data provider accessing authoritative reference property and owner datasets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_property(self, property_id: uuid.UUID) -> Optional[ReferenceProperty]:
        """Fetch reference property by UUID with owners preloaded."""
        stmt = (
            select(ReferenceProperty)
            .where(ReferenceProperty.id == property_id)
            .options(selectinload(ReferenceProperty.owners))
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def find_by_parcel_number(
        self, parcel_number: str, source_id: Optional[str] = None
    ) -> List[ReferenceProperty]:
        """Query reference records by unique parcel number."""
        norm_parcel = IdentifierNormalizer.normalize(parcel_number)
        if not norm_parcel:
            return []

        stmt = select(ReferenceProperty).options(selectinload(ReferenceProperty.owners))
        if source_id:
            stmt = stmt.where(ReferenceProperty.source_id == source_id)
        stmt = stmt.where(ReferenceProperty.parcel_number.ilike(norm_parcel))

        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def find_by_survey_and_plot(
        self,
        survey_number: str,
        plot_number: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[ReferenceProperty]:
        """Query reference records by cadastral survey number and optional plot number."""
        norm_survey = IdentifierNormalizer.normalize(survey_number)
        if not norm_survey:
            return []

        stmt = select(ReferenceProperty).options(selectinload(ReferenceProperty.owners))
        if source_id:
            stmt = stmt.where(ReferenceProperty.source_id == source_id)
        stmt = stmt.where(ReferenceProperty.survey_number.ilike(norm_survey))

        if plot_number:
            norm_plot = IdentifierNormalizer.normalize(plot_number)
            if norm_plot:
                stmt = stmt.where(ReferenceProperty.plot_number.ilike(norm_plot))

        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def find_by_registration_number(
        self, registration_number: str, source_id: Optional[str] = None
    ) -> List[ReferenceProperty]:
        """Query reference records by official registration deed number."""
        norm_reg = IdentifierNormalizer.normalize(registration_number)
        if not norm_reg:
            return []

        stmt = select(ReferenceProperty).options(selectinload(ReferenceProperty.owners))
        if source_id:
            stmt = stmt.where(ReferenceProperty.source_id == source_id)
        stmt = stmt.where(ReferenceProperty.registration_number.ilike(norm_reg))

        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def find_by_deed_number(
        self, deed_number: str, source_id: Optional[str] = None
    ) -> List[ReferenceProperty]:
        """Query reference records by title deed instrument number."""
        norm_deed = IdentifierNormalizer.normalize(deed_number)
        if not norm_deed:
            return []

        stmt = select(ReferenceProperty).options(selectinload(ReferenceProperty.owners))
        if source_id:
            stmt = stmt.where(ReferenceProperty.source_id == source_id)
        stmt = stmt.where(ReferenceProperty.deed_number.ilike(norm_deed))

        res = await self.db.execute(stmt)
        return list(res.scalars().all())
