from unittest.mock import AsyncMock
import uuid
import pytest

from app.models.enums import BoundaryType, MatchStatus
from app.models.property_profile import PropertyProfile
from app.models.reference_boundary import ReferenceBoundary
from app.models.reference_parcel import ReferenceParcel
from app.models.reference_property import ReferenceProperty
from app.services.validation.gis_rules import (
    AdministrativeBoundaryRule,
    AreaConsistencyRule,
    GeometryValidRule,
    ParcelExistsRule,
    PointInsideParcelRule,
)
from app.services.validation.parcel_provider import ParcelProvider


@pytest.mark.anyio
async def test_parcel_exists_and_geometry_valid_rules() -> None:
    """Verify parcel existence and geometry topological validity checks."""
    run_id = uuid.uuid4()
    profile = PropertyProfile(id=uuid.uuid4(), case_id=uuid.uuid4(), survey_number="123/45")

    # 1. Parcel missing -> NOT_FOUND
    res_none = ParcelExistsRule.evaluate(run_id, profile, None)
    assert res_none.match_status == MatchStatus.NOT_FOUND
    assert res_none.mismatch_reason == "PARCEL_NOT_FOUND"

    # 2. Parcel present
    parcel = ReferenceParcel(
        id=uuid.uuid4(),
        source_id="map_registry",
        source_record_id="P-001",
        geometry="SRID=4326;MULTIPOLYGON(((73.0 20.0, 73.001 20.0, 73.001 20.001, 73.0 20.001, 73.0 20.0)))",
    )
    res_exists = ParcelExistsRule.evaluate(run_id, profile, parcel)
    assert res_exists.match_status == MatchStatus.MATCH

    # 3. Geometry validity
    mock_provider = AsyncMock(spec=ParcelProvider)
    mock_provider.check_geometry_valid.return_value = True

    res_valid = await GeometryValidRule.evaluate(run_id, parcel, mock_provider)
    assert res_valid.match_status == MatchStatus.MATCH

    # 4. Geometry invalid
    mock_provider.check_geometry_valid.return_value = False
    res_invalid = await GeometryValidRule.evaluate(run_id, parcel, mock_provider)
    assert res_invalid.match_status == MatchStatus.MISMATCH
    assert res_invalid.mismatch_reason == "INVALID_PARCEL_GEOMETRY"


@pytest.mark.anyio
async def test_point_inside_parcel_rule() -> None:
    """Verify point-in-polygon containment and distance measurement when outside."""
    run_id = uuid.uuid4()
    parcel = ReferenceParcel(
        id=uuid.uuid4(),
        source_id="map_registry",
        source_record_id="P-001",
    )

    mock_provider = AsyncMock(spec=ParcelProvider)

    # 1. Point inside parcel (ST_Covers True)
    profile_inside = PropertyProfile(
        id=uuid.uuid4(), case_id=uuid.uuid4(), latitude=20.0005, longitude=73.0005
    )
    mock_provider.check_point_containment.return_value = (True, 0.0)

    res_inside = await PointInsideParcelRule.evaluate(
        run_id, profile_inside, parcel, mock_provider
    )
    assert res_inside.match_status == MatchStatus.MATCH
    assert res_inside.geometry_distance_meters == 0.0

    # 2. Point outside parcel (ST_Covers False, distance 153.4m)
    profile_outside = PropertyProfile(
        id=uuid.uuid4(), case_id=uuid.uuid4(), latitude=20.0050, longitude=73.0050
    )
    mock_provider.check_point_containment.return_value = (False, 153.4)

    res_outside = await PointInsideParcelRule.evaluate(
        run_id, profile_outside, parcel, mock_provider
    )
    assert res_outside.match_status == MatchStatus.MISMATCH
    assert res_outside.mismatch_reason == "POINT_OUTSIDE_PARCEL"
    assert res_outside.geometry_distance_meters == 153.4

    # 3. No coordinates provided in document
    profile_no_coord = PropertyProfile(id=uuid.uuid4(), case_id=uuid.uuid4())
    res_no_coord = await PointInsideParcelRule.evaluate(
        run_id, profile_no_coord, parcel, mock_provider
    )
    assert res_no_coord.match_status == MatchStatus.NOT_CHECKED
    assert res_no_coord.mismatch_reason == "LOCATION_POINT_NOT_AVAILABLE"


@pytest.mark.anyio
async def test_area_consistency_and_boundary_rules() -> None:
    """Verify PostGIS geometry area consistency and administrative boundary matching."""
    run_id = uuid.uuid4()
    profile = PropertyProfile(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        property_area=2.50,
        area_unit="acres",
        district="Pune",
        village="Shanti Nagar",
        latitude=20.0005,
        longitude=73.0005,
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
        source_id="map_registry",
        source_record_id="P-001",
    )

    mock_provider = AsyncMock(spec=ParcelProvider)
    # 2.50 acres ~ 10117.14 sqm. Mock GIS computed area = 10120.0 sqm (within 2% tolerance)
    mock_provider.calculate_geography_area_sqm.return_value = 10120.0

    # 1. Area Consistency
    area_results = await AreaConsistencyRule.evaluate(
        run_id, profile, parcel, ref_prop, mock_provider, tolerance_percent=2.0
    )
    assert len(area_results) == 2
    for r in area_results:
        assert r.match_status == MatchStatus.MATCH

    # 2. Administrative Boundary match
    mock_boundary_pune = ReferenceBoundary(
        id=uuid.uuid4(),
        source_id="admin_boundaries",
        source_record_id="B-001",
        boundary_type=BoundaryType.DISTRICT,
        name="Pune",
        normalized_name="pune",
    )
    mock_provider.find_boundary_containing_point.return_value = mock_boundary_pune

    boundary_results = await AdministrativeBoundaryRule.evaluate(
        run_id, profile, parcel, mock_provider
    )
    assert len(boundary_results) >= 1
    assert boundary_results[0].match_status == MatchStatus.MATCH
    assert boundary_results[0].field_name == "district_boundary"
