from datetime import datetime, timezone
import uuid

import pytest

from app.models.property_field_source import PropertyFieldSource


def test_property_field_source_creation() -> None:
    """Verify that PropertyFieldSource records ground canonical profile attributes back to extracted fields."""
    profile_id = uuid.uuid4()
    ext_id = uuid.uuid4()

    source = PropertyFieldSource(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        field_name="survey_number",
        extracted_field_id=ext_id,
        confidence=0.94,
    )

    assert source.field_name == "survey_number"
    assert source.extracted_field_id == ext_id
    assert source.confidence == 0.94
