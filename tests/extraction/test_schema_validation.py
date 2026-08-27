from pydantic import ValidationError
import pytest

from app.schemas.extraction import LLMExtractedFieldItem, LLMExtractionOutput
from app.services.field_registry import FieldRegistry


def test_field_registry_validation() -> None:
    """Verify registered property fields lookup and reject unregistered fields."""
    assert FieldRegistry.is_valid_field("owner_name") is True
    assert FieldRegistry.is_valid_field("survey_number") is True
    assert FieldRegistry.is_valid_field("property_area") is True
    assert FieldRegistry.is_valid_field("registration_date") is True

    # Hallucinated or non-standard field names
    assert FieldRegistry.is_valid_field("imaginary_field") is False
    assert FieldRegistry.is_valid_field("owner_is_definitely_legal") is False

    fields = FieldRegistry.get_all_fields()
    assert len(fields) >= 15
    assert "owner_name" in fields


def test_llm_extraction_output_pydantic_validation() -> None:
    """Verify parsing and validation of structured LLM JSON outputs."""
    valid_data = {
        "fields": [
            {
                "field_name": "owner_name",
                "value": "Ramesh Kumar",
                "confidence": 0.95,
                "page_number": 1,
                "source_text": "Owner: Ramesh Kumar",
            },
            {
                "field_name": "survey_number",
                "value": None,
                "confidence": 0.0,
                "page_number": 1,
                "source_text": "",
            },
        ]
    }

    parsed = LLMExtractionOutput.model_validate(valid_data)
    assert len(parsed.fields) == 2
    assert parsed.fields[0].field_name == "owner_name"
    assert parsed.fields[0].confidence == 0.95
    assert parsed.fields[1].value is None

    # Invalid confidence range (> 1.0)
    with pytest.raises(ValidationError):
        LLMExtractedFieldItem(
            field_name="owner_name",
            value="John",
            confidence=1.5,
            page_number=1,
            source_text="John",
        )
