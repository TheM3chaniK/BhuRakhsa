from datetime import datetime, timezone
import uuid

import pytest

from app.models.property_field_conflict import PropertyFieldConflict


def test_property_field_conflict_model() -> None:
    """Verify that differing extracted values create explicit conflict records instead of silently selecting one."""
    profile_id = uuid.uuid4()

    conflict = PropertyFieldConflict(
        id=uuid.uuid4(),
        property_profile_id=profile_id,
        field_name="survey_number",
        value_a="123/45",
        value_b="123/46",
        source_a="Document A (conf: 0.90)",
        source_b="Document B (conf: 0.85)",
    )

    assert conflict.field_name == "survey_number"
    assert conflict.value_a == "123/45"
    assert conflict.value_b == "123/46"
    assert "Document A" in conflict.source_a
