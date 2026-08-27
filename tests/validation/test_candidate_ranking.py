import uuid
import pytest

from app.models.enums import OwnershipType
from app.models.property_owner import PropertyOwner
from app.models.property_profile import PropertyProfile
from app.models.reference_owner import ReferencePropertyOwner
from app.models.reference_property import ReferenceProperty
from app.services.validation.database_validator import DatabaseValidator


def test_candidate_scoring_hierarchy() -> None:
    """Verify deterministic candidate ranking scores based on identifier and attribute weights."""
    validator = DatabaseValidator(db=None)  # type: ignore

    profile = PropertyProfile(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        parcel_number="P-100",
        survey_number="123/45",
        plot_number="7",
        district="Pune",
        village="Shanti Nagar",
    )
    profile.owners = [
        PropertyOwner(
            id=uuid.uuid4(),
            property_profile_id=profile.id,
            name="Ramesh Kumar",
            ownership_type=OwnershipType.INDIVIDUAL,
        )
    ]

    # Perfect match record
    ref_perfect = ReferenceProperty(
        id=uuid.uuid4(),
        source_id="registry",
        source_record_id="R-001",
        parcel_number="P-100",
        survey_number="123/45",
        plot_number="7",
        district="Pune",
        village="Shanti Nagar",
    )
    ref_perfect.owners = [
        ReferencePropertyOwner(
            id=uuid.uuid4(),
            reference_property_id=ref_perfect.id,
            name="Ramesh Kumar",
            normalized_name="ramesh kumar",
        )
    ]

    # Partial match record (same survey, different plot, different owner)
    ref_partial = ReferenceProperty(
        id=uuid.uuid4(),
        source_id="registry",
        source_record_id="R-002",
        parcel_number="P-999",
        survey_number="123/45",
        plot_number="99",
        district="Pune",
        village="Shanti Nagar",
    )
    ref_partial.owners = [
        ReferencePropertyOwner(
            id=uuid.uuid4(),
            reference_property_id=ref_partial.id,
            name="Other Person",
            normalized_name="other person",
        )
    ]

    score_perfect = validator.calculate_candidate_score(profile, ref_perfect)
    score_partial = validator.calculate_candidate_score(profile, ref_partial)

    # Perfect: 100 (parcel) + 80 (survey) + 60 (plot) + 40 (owner) + 20 (district) + 20 (village) = 320
    assert score_perfect >= 300.0
    # Partial: 80 (survey) + 20 (district) + 20 (village) = 120
    assert score_partial <= 130.0
    assert score_perfect > score_partial
