from unittest.mock import AsyncMock, MagicMock
import pytest

from app.models.case import CaseSequence
from app.services.case_service import CaseService


@pytest.mark.anyio
async def test_case_number_generation_sequence() -> None:
    """Verify consecutive case number formatting (CASE-YYYY-000001, CASE-YYYY-000002)."""
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    # Case 1: Sequence does not exist yet -> starts at 1
    mock_result_empty = MagicMock()
    mock_result_empty.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result_empty

    num1 = await CaseService.generate_case_number(mock_db, 2026)
    assert num1 == "CASE-2026-000001"

    # Case 2: Existing sequence record with last_value = 1 -> increments to 2
    seq = CaseSequence(year=2026, last_value=1)
    mock_result_existing = MagicMock()
    mock_result_existing.scalar_one_or_none.return_value = seq
    mock_db.execute.return_value = mock_result_existing

    num2 = await CaseService.generate_case_number(mock_db, 2026)
    assert num2 == "CASE-2026-000002"
    assert seq.last_value == 2

    # Case 3: Increments to 3
    num3 = await CaseService.generate_case_number(mock_db, 2026)
    assert num3 == "CASE-2026-000003"
    assert seq.last_value == 3
