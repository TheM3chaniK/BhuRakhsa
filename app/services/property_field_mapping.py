import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.enums import OwnershipType

# Explicit mapping between ExtractedField.field_name and PropertyProfile columns
FIELD_MAPPING: Dict[str, str] = {
    "survey_number": "survey_number",
    "plot_number": "plot_number",
    "parcel_number": "parcel_number",
    "registration_number": "registration_number",
    "deed_number": "deed_number",
    "property_address": "property_address",
    "district": "district",
    "subdivision": "subdivision",
    "village": "village",
    "mouza": "mouza",
    "ward": "ward",
}


class PropertyFieldMapper:
    """Helper service mapping extracted candidate fields to canonical PropertyProfile and PropertyOwner representations."""

    @classmethod
    def parse_area_and_unit(
        cls, raw_area: Optional[str]
    ) -> Tuple[Optional[float], Optional[str]]:
        """Extract numeric value and unit string from raw property_area / land_area text."""
        if not raw_area or not raw_area.strip():
            return None, None

        cleaned = raw_area.strip()
        # Find numeric component
        match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
        if not match:
            return None, None

        numeric_val = float(match.group(1))

        # Extract unit substring after the number
        unit_part = cleaned[match.end():].strip()
        if not unit_part:
            # Check if unit is before the number
            unit_part = cleaned[:match.start()].strip()

        unit_clean = unit_part.lower().strip(",.-/ ") if unit_part else None
        return numeric_val, unit_clean or None

    @classmethod
    def parse_owners(
        cls,
        owner_name: Optional[str],
        co_owners: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Parse primary and co-owner extracted values into discrete PropertyOwner entities."""
        owners: List[Dict[str, Any]] = []

        if owner_name and owner_name.strip():
            # Check if multiple comma-separated names are in primary owner_name
            if "," in owner_name:
                parts = [p.strip() for p in owner_name.split(",") if p.strip()]
                for p in parts:
                    owners.append(
                        {
                            "name": p,
                            "normalized_name": " ".join(p.lower().split()),
                            "ownership_type": OwnershipType.JOINT,
                        }
                    )
            else:
                clean_name = owner_name.strip()
                owners.append(
                    {
                        "name": clean_name,
                        "normalized_name": " ".join(clean_name.lower().split()),
                        "ownership_type": (
                            OwnershipType.INDIVIDUAL
                            if not co_owners
                            else OwnershipType.JOINT
                        ),
                    }
                )

        if co_owners and co_owners.strip():
            # Co-owners might be comma, semicolon, or newline separated
            parts = re.split(r"[,;\n]+", co_owners)
            for p in parts:
                clean_p = p.strip()
                if clean_p and not any(o["name"].lower() == clean_p.lower() for o in owners):
                    owners.append(
                        {
                            "name": clean_p,
                            "normalized_name": " ".join(clean_p.lower().split()),
                            "ownership_type": OwnershipType.JOINT,
                        }
                    )

        return owners
