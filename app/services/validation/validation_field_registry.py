from typing import List, Set


class ValidationFieldRegistry:
    """Registry defining canonical fields subject to cross-verification against government registries and GIS layers."""

    DATABASE_VALIDATION_FIELDS: Set[str] = {
        "survey_number",
        "plot_number",
        "parcel_number",
        "registration_number",
        "deed_number",
        "owner_name",
        "property_area",
        "district",
        "village",
        "mouza",
    }

    GIS_VALIDATION_FIELDS: Set[str] = {
        "survey_number",
        "plot_number",
        "parcel_number",
        "property_area",
        "village",
        "latitude",
        "longitude",
        "parcel_geometry",
    }

    @classmethod
    def get_database_fields(cls) -> List[str]:
        return sorted(list(cls.DATABASE_VALIDATION_FIELDS))

    @classmethod
    def get_gis_fields(cls) -> List[str]:
        return sorted(list(cls.GIS_VALIDATION_FIELDS))
