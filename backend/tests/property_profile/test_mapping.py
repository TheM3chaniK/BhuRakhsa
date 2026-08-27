import pytest

from app.models.enums import OwnershipType
from app.services.property_field_mapping import PropertyFieldMapper


def test_parse_area_and_unit() -> None:
    """Verify area parsing into numeric float and clean unit string."""
    num, unit = PropertyFieldMapper.parse_area_and_unit("2.50 acres")
    assert num == 2.50
    assert unit == "acres"

    num, unit = PropertyFieldMapper.parse_area_and_unit("1200 sq. ft.")
    assert num == 1200.0
    assert "sq" in unit

    num, unit = PropertyFieldMapper.parse_area_and_unit("0.75 hectare")
    assert num == 0.75
    assert unit == "hectare"

    num, unit = PropertyFieldMapper.parse_area_and_unit(None)
    assert num is None
    assert unit is None


def test_parse_single_and_multiple_owners() -> None:
    """Verify parsing single owners, comma-separated lists, and distinct co-owner entries."""
    # Single individual owner
    owners = PropertyFieldMapper.parse_owners("Ramesh Kumar", None)
    assert len(owners) == 1
    assert owners[0]["name"] == "Ramesh Kumar"
    assert owners[0]["ownership_type"] == OwnershipType.INDIVIDUAL

    # Joint owners with co-owners
    owners_joint = PropertyFieldMapper.parse_owners(
        "Ramesh Kumar", "Suresh Kumar, Anita Kumar"
    )
    assert len(owners_joint) == 3
    assert owners_joint[0]["ownership_type"] == OwnershipType.JOINT
    assert owners_joint[1]["name"] == "Suresh Kumar"
    assert owners_joint[2]["name"] == "Anita Kumar"

    # Single string with comma in primary owner
    owners_comma = PropertyFieldMapper.parse_owners("Ramesh Kumar, Suresh Kumar", None)
    assert len(owners_comma) == 2
    assert owners_comma[0]["ownership_type"] == OwnershipType.JOINT
