from unittest.mock import AsyncMock
import uuid
import pytest

from app.models.enums import BoundaryType, MatchStatus, ValidationStatus, ValidationType
from app.models.property_profile import PropertyProfile
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty
from app.models.validation import ValidationRun
from app.services.validation.gis_validator import GISValidator

SAMPLE_GEOM = "SRID=4326;MULTIPOLYGON(((73.0 20.0, 73.001 20.0, 73.001 20.001, 73.0 20.001, 73.0 20.0)))"


@pytest.mark.anyio
async def test_gis_validator_full_passed_flow() -> None:
    """Verify that a complete matching parcel and coordinate result in PASSED status."""
    profile = PropertyProfile(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        survey_number="123/45",
        plot_number="7",
        latitude=20.0005,
        longitude=73.0005,
        property_area=2.50,
        area_unit="acres",
    )
    ref_prop = ReferenceProperty(
        id=uuid.uuid4(),
        source_id="registry",
        source_record_id="R-001",
        property_area=2.50,
        area_unit="acres",
    )
    parcel = ReferenceParcel(
        id=uuid.uuid4(),
        reference_property_id=ref_prop.id,
        source_id="map_registry",
        source_record_id="P-001",
        geometry=SAMPLE_GEOM,
    )

    validator = GISValidator(db=AsyncMock())
    validator.find_parcel = AsyncMock(return_value=parcel)  # type: ignore
    validator.provider.check_geometry_valid = AsyncMock(return_value=True)  # type: ignore
    validator.provider.check_point_containment = AsyncMock(return_value=(True, 0.0))  # type: ignore
    validator.provider.calculate_geography_area_sqm = AsyncMock(return_value=10120.0)  # type: ignore
    validator.provider.find_boundary_containing_point = AsyncMock(return_value=None)  # type: ignore

    run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile.id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results = await validator.validate_run(run, profile, ref_prop)

    assert status_outcome == ValidationStatus.PASSED
    assert len(results) >= 3
    field_map = {r.field_name: r for r in results}
    assert field_map["parcel_existence"].match_status == MatchStatus.MATCH
    assert field_map["parcel_geometry"].match_status == MatchStatus.MATCH
    assert field_map["point_inside_parcel"].match_status == MatchStatus.MATCH


@pytest.mark.anyio
async def test_gis_validator_missing_coordinates_passed_with_limitations() -> None:
    """Verify that absent coordinates yield PASSED_WITH_LIMITATIONS if other checks pass."""
    profile = PropertyProfile(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        survey_number="123/45",
        plot_number="7",
        property_area=2.50,
        area_unit="acres",
    )
    parcel = ReferenceParcel(
        id=uuid.uuid4(),
        source_id="map_registry",
        source_record_id="P-001",
        geometry=SAMPLE_GEOM,
    )

    validator = GISValidator(db=AsyncMock())
    validator.find_parcel = AsyncMock(return_value=parcel)  # type: ignore
    validator.provider.check_geometry_valid = AsyncMock(return_value=True)  # type: ignore
    validator.provider.calculate_geography_area_sqm = AsyncMock(return_value=10120.0)  # type: ignore
    validator.provider.find_boundary_containing_point = AsyncMock(return_value=None)  # type: ignore

    run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile.id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results = await validator.validate_run(run, profile, None)

    assert status_outcome == ValidationStatus.PASSED_WITH_LIMITATIONS
    field_map = {r.field_name: r for r in results}
    assert field_map["point_inside_parcel"].match_status == MatchStatus.NOT_CHECKED


@pytest.mark.anyio
async def test_gis_validator_point_outside_fails_run() -> None:
    """Verify that a coordinate outside the parcel polygon causes FAILED run status."""
    profile = PropertyProfile(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        survey_number="123/45",
        latitude=20.0050,
        longitude=73.0050,
    )
    parcel = ReferenceParcel(
        id=uuid.uuid4(),
        source_id="map_registry",
        source_record_id="P-001",
        geometry=SAMPLE_GEOM,
    )

    validator = GISValidator(db=AsyncMock())
    validator.find_parcel = AsyncMock(return_value=parcel)  # type: ignore
    validator.provider.check_geometry_valid = AsyncMock(return_value=True)  # type: ignore
    validator.provider.check_point_containment = AsyncMock(return_value=(False, 250.0))  # type: ignore
    validator.provider.calculate_geography_area_sqm = AsyncMock(return_value=10120.0)  # type: ignore
    validator.provider.find_boundary_containing_point = AsyncMock(return_value=None)  # type: ignore

    run = ValidationRun(
        id=uuid.uuid4(),
        property_profile_id=profile.id,
        validation_type=ValidationType.GIS,
        status=ValidationStatus.PENDING,
    )

    status_outcome, results = await validator.validate_run(run, profile, None)

    assert status_outcome == ValidationStatus.FAILED
    field_map = {r.field_name: r for r in results}
    assert field_map["point_inside_parcel"].match_status == MatchStatus.MISMATCH
    assert field_map["point_inside_parcel"].geometry_distance_meters == 250.0
