from datetime import datetime, timezone
from unittest.mock import AsyncMock
import uuid

import pytest

from app.models.enums import MatchStatus, OwnershipType, ValidationStatus, ValidationType
from app.models.property_owner import PropertyOwner
from app.models.property_profile import PropertyProfile
from app.models.reference_owner import ReferencePropertyOwner
from app.models.reference_property import ReferenceProperty
from app.models.validation import ValidationRun
from app.services.validation.database_validator import DatabaseValidator


@pytest.mark.anyio
async def test_database_validation_success_match() -> None:
    """Verify that a fully matching reference record produces MATCH results and PASSED run status."""
    profile_id = uuid.uuid4()
    run_id = uuid.uuid4()
    ref_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    profile = PropertyProfile(
        id=profile_id,
        case_id=uuid.uuid4(),
        parcel_number="P-100",
        survey_number="123/45",
        plot_number="7",
        registration_number="REG-2025",
        property_area=2.50,
        area_unit="acres",
        district="Pune",
        village="Shanti Nagar",
    )
    profile.owners = [
        PropertyOwner(
            id=uuid.uuid4(),
            property_profile_id=profile_id,
            name="Ramesh Kumar",
            ownership_type=OwnershipType.INDIVIDUAL,
        )
    ]

    ref_prop = ReferenceProperty(
        id=ref_id,
        source_id="registry",
        source_record_id="R-001",
        parcel_number="P-100",
        survey_number="123/45",
        plot_number="7",
        registration_number="REG-2025",
        property_area=2.50,
        area_unit="acres",
        district="Pune",
        village="Shanti Nagar",
        dataset_version="1.0",
    )
    ref_prop.owners = [
        ReferencePropertyOwner(
            id=uuid.uuid4(),
            reference_property_id=ref_id,
            name="Ramesh Kumar",
            normalized_name="ramesh kumar",
        )
    ]

    validator = DatabaseValidator(db=AsyncMock())
    validator.find_candidates = AsyncMock(return_value=[(ref_prop, 320.0)])  # type: ignore

    run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results, candidates = await validator.validate_run(run, profile)

    assert status_outcome == ValidationStatus.PASSED
    assert len(candidates) == 1
    assert candidates[0].selection_status.value == "selected"

    field_map = {r.field_name: r for r in results}
    assert field_map["survey_number"].match_status == MatchStatus.MATCH
    assert field_map["parcel_number"].match_status == MatchStatus.MATCH
    assert field_map["owner_name"].match_status == MatchStatus.MATCH
    assert field_map["property_area"].match_status == MatchStatus.MATCH


@pytest.mark.anyio
async def test_database_validation_mismatch_fails_run() -> None:
    """Verify that an owner mismatch creates OWNER_MISMATCH result and marks run as FAILED."""
    profile_id = uuid.uuid4()
    run_id = uuid.uuid4()
    ref_id = uuid.uuid4()

    profile = PropertyProfile(
        id=profile_id,
        case_id=uuid.uuid4(),
        survey_number="123/45",
        plot_number="7",
        district="Pune",
        village="Shanti Nagar",
    )
    profile.owners = [
        PropertyOwner(
            id=uuid.uuid4(),
            property_profile_id=profile_id,
            name="Suresh Kumar",  # Document owner
            ownership_type=OwnershipType.INDIVIDUAL,
        )
    ]

    ref_prop = ReferenceProperty(
        id=ref_id,
        source_id="registry",
        source_record_id="R-001",
        survey_number="123/45",
        plot_number="7",
        district="Pune",
        village="Shanti Nagar",
        dataset_version="1.0",
    )
    ref_prop.owners = [
        ReferencePropertyOwner(
            id=uuid.uuid4(),
            reference_property_id=ref_id,
            name="Ramesh Kumar",  # Authoritative owner in reference DB
            normalized_name="ramesh kumar",
        )
    ]

    validator = DatabaseValidator(db=AsyncMock())
    validator.find_candidates = AsyncMock(return_value=[(ref_prop, 180.0)])  # type: ignore

    run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results, candidates = await validator.validate_run(run, profile)

    assert status_outcome == ValidationStatus.FAILED
    field_map = {r.field_name: r for r in results}
    assert field_map["owner_name"].match_status == MatchStatus.MISMATCH
    assert field_map["owner_name"].mismatch_reason == "OWNER_MISMATCH"


@pytest.mark.anyio
async def test_database_validation_reference_record_not_found() -> None:
    """Verify that absence of reference candidates creates REFERENCE_RECORD_NOT_FOUND and fails run."""
    profile_id = uuid.uuid4()
    run_id = uuid.uuid4()

    profile = PropertyProfile(
        id=profile_id,
        case_id=uuid.uuid4(),
        parcel_number="P-NON-EXISTENT",
        survey_number="999/99",
    )
    profile.owners = []

    validator = DatabaseValidator(db=AsyncMock())
    validator.find_candidates = AsyncMock(return_value=[])  # type: ignore

    run = ValidationRun(
        id=run_id,
        property_profile_id=profile_id,
        validation_type=ValidationType.DATABASE,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results, candidates = await validator.validate_run(run, profile)

    assert status_outcome == ValidationStatus.FAILED
    assert len(results) == 1
    assert results[0].match_status == MatchStatus.NOT_FOUND
    assert results[0].mismatch_reason == "REFERENCE_RECORD_NOT_FOUND"
