import csv
import io
import json
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.enums import UserRole
from app.models.reference_owner import ReferencePropertyOwner
from app.models.reference_property import ReferenceProperty
from app.models.user import User
from app.services.normalization.name import NameNormalizer


class ReferenceImportService:
    """Service importing and updating authoritative property reference records from CSV and JSON datasets."""

    @classmethod
    def _parse_float(cls, val: Any) -> Optional[float]:
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @classmethod
    def _parse_csv_owners(cls, row: Dict[str, str]) -> List[Dict[str, Any]]:
        owners = []
        if "owner_names" in row and row["owner_names"]:
            for name in row["owner_names"].split(","):
                if name.strip():
                    norm = NameNormalizer.normalize(name) or name.strip().lower()
                    owners.append({"name": name.strip(), "normalized_name": norm})
        elif "owner_name" in row and row["owner_name"]:
            name = row["owner_name"].strip()
            norm = NameNormalizer.normalize(name) or name.lower()
            owners.append({"name": name, "normalized_name": norm})
        return owners

    @staticmethod
    async def import_reference_dataset(
        db: AsyncSession,
        file: UploadFile,
        user: User,
        dataset_version: str = "1.0",
    ) -> Dict[str, Any]:
        """Validate and upsert authoritative reference dataset (Super Admin only)."""
        if user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admins can import reference datasets.",
            )

        content = await file.read()
        filename = file.filename or ""

        records: List[Dict[str, Any]] = []

        if filename.endswith(".json") or file.content_type == "application/json":
            try:
                data = json.loads(content.decode("utf-8"))
                if isinstance(data, list):
                    records = data
                elif isinstance(data, dict) and "records" in data:
                    records = data["records"]
                else:
                    raise ValueError("JSON must be a list of records or contain a 'records' key.")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON file format: {str(e)}",
                )
        elif (
            filename.endswith(".csv")
            or file.content_type in ("text/csv", "application/vnd.ms-excel")
            or True
        ):
            try:
                text_stream = io.StringIO(content.decode("utf-8-sig"))
                reader = csv.DictReader(text_stream)
                for row in reader:
                    records.append(dict(row))
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid CSV file format: {str(e)}",
                )

        if not records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dataset is empty or no valid rows found.",
            )

        # Check for in-file duplicates on (source_id, source_record_id)
        seen_keys = set()
        for idx, r in enumerate(records):
            s_id = r.get("source_id", "").strip()
            sr_id = r.get("source_record_id", "").strip()
            if not s_id or not sr_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {idx + 1} missing required 'source_id' or 'source_record_id'.",
                )
            key = (s_id, sr_id)
            if key in seen_keys:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Duplicate reference key ({s_id}, {sr_id}) found in import payload at row {idx + 1}.",
                )
            seen_keys.add(key)

        inserted_count = 0
        updated_count = 0

        # Perform atomic batch upsert
        for r in records:
            source_id = r["source_id"].strip()
            source_record_id = r["source_record_id"].strip()

            stmt = select(ReferenceProperty).where(
                ReferenceProperty.source_id == source_id,
                ReferenceProperty.source_record_id == source_record_id,
            )
            existing_res = await db.execute(stmt)
            existing_prop = existing_res.scalar_one_or_none()

            prop_area = ReferenceImportService._parse_float(r.get("property_area"))

            if existing_prop:
                # Update existing record
                existing_prop.survey_number = r.get("survey_number") or None
                existing_prop.plot_number = r.get("plot_number") or None
                existing_prop.parcel_number = r.get("parcel_number") or None
                existing_prop.registration_number = r.get("registration_number") or None
                existing_prop.deed_number = r.get("deed_number") or None
                existing_prop.property_address = r.get("property_address") or None
                existing_prop.district = r.get("district") or None
                existing_prop.subdivision = r.get("subdivision") or None
                existing_prop.village = r.get("village") or None
                existing_prop.mouza = r.get("mouza") or None
                existing_prop.ward = r.get("ward") or None
                existing_prop.property_area = prop_area
                existing_prop.area_unit = r.get("area_unit") or None
                existing_prop.dataset_version = dataset_version

                # Clean prior owners
                await db.execute(
                    delete(ReferencePropertyOwner).where(
                        ReferencePropertyOwner.reference_property_id == existing_prop.id
                    )
                )
                target_id = existing_prop.id
                updated_count += 1
            else:
                # Insert new record
                target_id = uuid.uuid4()
                new_prop = ReferenceProperty(
                    id=target_id,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    survey_number=r.get("survey_number") or None,
                    plot_number=r.get("plot_number") or None,
                    parcel_number=r.get("parcel_number") or None,
                    registration_number=r.get("registration_number") or None,
                    deed_number=r.get("deed_number") or None,
                    property_address=r.get("property_address") or None,
                    district=r.get("district") or None,
                    subdivision=r.get("subdivision") or None,
                    village=r.get("village") or None,
                    mouza=r.get("mouza") or None,
                    ward=r.get("ward") or None,
                    property_area=prop_area,
                    area_unit=r.get("area_unit") or None,
                    dataset_version=dataset_version,
                )
                db.add(new_prop)
                inserted_count += 1

            # Process owners
            owners_data = []
            if "owners" in r and isinstance(r["owners"], list):
                for o in r["owners"]:
                    if isinstance(o, dict) and "name" in o:
                        norm = NameNormalizer.normalize(o["name"]) or o["name"].lower()
                        owners_data.append(
                            {
                                "name": o["name"],
                                "normalized_name": norm,
                                "ownership_share": o.get("ownership_share"),
                            }
                        )
                    elif isinstance(o, str):
                        norm = NameNormalizer.normalize(o) or o.lower()
                        owners_data.append({"name": o, "normalized_name": norm})
            else:
                owners_data = ReferenceImportService._parse_csv_owners(r)

            for od in owners_data:
                owner_obj = ReferencePropertyOwner(
                    id=uuid.uuid4(),
                    reference_property_id=target_id,
                    name=od["name"],
                    normalized_name=od["normalized_name"],
                    ownership_share=od.get("ownership_share"),
                )
                db.add(owner_obj)

        await db.commit()

        logger.info(
            "Reference dataset import completed: %d total, %d inserted, %d updated.",
            len(records),
            inserted_count,
            updated_count,
        )

        return {
            "total_records": len(records),
            "inserted": inserted_count,
            "updated": updated_count,
            "failed": 0,
        }
