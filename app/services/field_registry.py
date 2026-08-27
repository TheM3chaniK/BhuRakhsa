from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FieldDefinition:
    """Metadata defining a structured extractable property field."""

    name: str
    type: str  # 'string', 'string_list', 'date', 'decimal', 'integer'
    description: str
    required: bool = False


class FieldRegistry:
    """Controlled registry of all standard property fields supported by the extraction pipeline."""

    _REGISTRY: Dict[str, FieldDefinition] = {
        "owner_name": FieldDefinition(
            name="owner_name",
            type="string",
            description="Full name of the primary property owner / purchaser / claimant.",
        ),
        "co_owner_names": FieldDefinition(
            name="co_owner_names",
            type="string_list",
            description="Names of any joint owners, co-purchasers, or family claimants.",
        ),
        "property_address": FieldDefinition(
            name="property_address",
            type="string",
            description="Full property physical location, premises, street, or boundary description.",
        ),
        "survey_number": FieldDefinition(
            name="survey_number",
            type="string",
            description="Cadastral survey / CTS / survey sub-division number.",
        ),
        "plot_number": FieldDefinition(
            name="plot_number",
            type="string",
            description="Individual plot number within a layout, scheme, or block.",
        ),
        "parcel_number": FieldDefinition(
            name="parcel_number",
            type="string",
            description="Unique land parcel identification number (ULPIN / LPID / PID).",
        ),
        "registration_number": FieldDefinition(
            name="registration_number",
            type="string",
            description="Official document registration number assigned by Sub-Registrar Office.",
        ),
        "deed_number": FieldDefinition(
            name="deed_number",
            type="string",
            description="Title deed / conveyance / sale deed number.",
        ),
        "document_date": FieldDefinition(
            name="document_date",
            type="date",
            description="Date when deed or title instrument was signed / executed.",
        ),
        "registration_date": FieldDefinition(
            name="registration_date",
            type="date",
            description="Date when document was officially registered at the registry office.",
        ),
        "property_area": FieldDefinition(
            name="property_area",
            type="decimal",
            description="Total property surface or built-up area (e.g. '2.50 acres', '1200 sq ft').",
        ),
        "land_area": FieldDefinition(
            name="land_area",
            type="decimal",
            description="Land parcel extent or area measurement.",
        ),
        "district": FieldDefinition(
            name="district",
            type="string",
            description="Administrative district name.",
        ),
        "subdivision": FieldDefinition(
            name="subdivision",
            type="string",
            description="Sub-district / Taluk / Tehsil / Circle jurisdiction.",
        ),
        "village": FieldDefinition(
            name="village",
            type="string",
            description="Revenue village, locality, or town name.",
        ),
        "mouza": FieldDefinition(
            name="mouza",
            type="string",
            description="Revenue mouza name.",
        ),
        "ward": FieldDefinition(
            name="ward",
            type="string",
            description="Municipal ward number or ward identification.",
        ),
        "khaitan_number": FieldDefinition(
            name="khaitan_number",
            type="string",
            description="Khatiyan / Jamabandi / Record of Rights account number.",
        ),
        "dag_number": FieldDefinition(
            name="dag_number",
            type="string",
            description="Dag / Khasra / Cadastral sub-plot number.",
        ),
    }

    @classmethod
    def is_valid_field(cls, field_name: str) -> bool:
        """Check whether a field name exists in the registered schema."""
        return field_name in cls._REGISTRY

    @classmethod
    def get_field(cls, field_name: str) -> Optional[FieldDefinition]:
        """Retrieve definition for a specific registered field."""
        return cls._REGISTRY.get(field_name)

    @classmethod
    def get_all_fields(cls) -> Dict[str, FieldDefinition]:
        """Retrieve all registered field definitions."""
        return cls._REGISTRY.copy()

    @classmethod
    def get_field_names(cls) -> List[str]:
        """Return list of all registered field names."""
        return list(cls._REGISTRY.keys())

    @classmethod
    def get_prompt_schema_description(cls) -> str:
        """Format field definitions as a structured prompt specification for LLM extraction."""
        lines = []
        for name, field in cls._REGISTRY.items():
            lines.append(f"- `{name}` ({field.type}): {field.description}")
        return "\n".join(lines)
