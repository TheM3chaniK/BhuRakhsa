import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings
from tests.database.conftest import check_db_connectivity_sync


def test_alembic_config_and_script_directory() -> None:
    """Verify that Alembic configuration and migration directory load correctly."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0014"


def test_offline_sql_migration_generation(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that Alembic can generate SQL for upgrade and downgrade in offline mode."""
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    # Test upgrade SQL generation up to head
    command.upgrade(alembic_cfg, "base:head", sql=True)
    captured_upgrade = capsys.readouterr()
    assert "CREATE EXTENSION IF NOT EXISTS postgis;" in captured_upgrade.out
    assert "CREATE TABLE users" in captured_upgrade.out
    assert "CREATE TABLE refresh_tokens" in captured_upgrade.out
    assert "CREATE TABLE areas" in captured_upgrade.out
    assert "CREATE TABLE area_officer_assignments" in captured_upgrade.out
    assert "CREATE TABLE cases" in captured_upgrade.out
    assert "CREATE TABLE case_sequences" in captured_upgrade.out
    assert "CREATE TABLE documents" in captured_upgrade.out
    assert "CREATE TABLE document_processing_jobs" in captured_upgrade.out
    assert "CREATE TABLE ocr_results" in captured_upgrade.out
    assert "CREATE TABLE extraction_jobs" in captured_upgrade.out
    assert "CREATE TABLE extracted_fields" in captured_upgrade.out
    assert "CREATE TABLE evidence" in captured_upgrade.out
    assert "CREATE TABLE property_profiles" in captured_upgrade.out
    assert "CREATE TABLE property_owners" in captured_upgrade.out
    assert "CREATE TABLE property_field_sources" in captured_upgrade.out
    assert "CREATE TABLE property_field_conflicts" in captured_upgrade.out
    assert "CREATE TABLE validation_runs" in captured_upgrade.out
    assert "CREATE TABLE validation_results" in captured_upgrade.out
    assert "CREATE TABLE reference_properties" in captured_upgrade.out
    assert "CREATE TABLE reference_property_owners" in captured_upgrade.out
    assert "CREATE TABLE validation_candidates" in captured_upgrade.out
    assert "CREATE TABLE reference_parcels" in captured_upgrade.out
    assert "CREATE TABLE reference_boundaries" in captured_upgrade.out
    assert "CREATE TABLE mismatches" in captured_upgrade.out
    assert "CREATE TABLE mismatch_evidence" in captured_upgrade.out
    assert "CREATE TABLE risk_assessments" in captured_upgrade.out
    assert "CREATE TABLE risk_factors" in captured_upgrade.out
    assert "CREATE TABLE case_reviews" in captured_upgrade.out
    assert "CREATE TABLE review_history" in captured_upgrade.out
    assert "CREATE TABLE proof_requests" in captured_upgrade.out
    assert "CREATE TABLE proof_submissions" in captured_upgrade.out
    assert "CREATE TABLE proof_request_history" in captured_upgrade.out
    assert "CREATE TABLE final_decisions" in captured_upgrade.out
    assert "CREATE TABLE audit_events" in captured_upgrade.out
    assert "CREATE TABLE outbox_events" in captured_upgrade.out
    assert "CREATE TABLE notifications" in captured_upgrade.out
    assert "alembic_version" in captured_upgrade.out

    # Test downgrade SQL generation
    command.downgrade(alembic_cfg, "0014:base", sql=True)
    captured_downgrade = capsys.readouterr()
    assert "DROP TABLE notifications;" in captured_downgrade.out
    assert "DROP TABLE outbox_events;" in captured_downgrade.out
    assert "DROP TABLE audit_events;" in captured_downgrade.out
    assert "DROP TABLE final_decisions;" in captured_downgrade.out
    assert "DROP TABLE proof_request_history;" in captured_downgrade.out
    assert "DROP TABLE proof_submissions;" in captured_downgrade.out
    assert "DROP TABLE proof_requests;" in captured_downgrade.out
    assert "DROP TABLE review_history;" in captured_downgrade.out
    assert "DROP TABLE case_reviews;" in captured_downgrade.out
    assert "DROP TABLE risk_factors;" in captured_downgrade.out
    assert "DROP TABLE risk_assessments;" in captured_downgrade.out
    assert "DROP TABLE mismatch_evidence;" in captured_downgrade.out
    assert "DROP TABLE mismatches;" in captured_downgrade.out
    assert "DROP TABLE reference_boundaries;" in captured_downgrade.out
    assert "DROP TABLE reference_parcels;" in captured_downgrade.out
    assert "DROP TABLE validation_candidates;" in captured_downgrade.out
    assert "DROP TABLE reference_property_owners;" in captured_downgrade.out
    assert "DROP TABLE reference_properties;" in captured_downgrade.out
    assert "DROP TABLE validation_results;" in captured_downgrade.out
    assert "DROP TABLE validation_runs;" in captured_downgrade.out
    assert "DROP TABLE property_field_conflicts;" in captured_downgrade.out
    assert "DROP TABLE property_field_sources;" in captured_downgrade.out
    assert "DROP TABLE property_owners;" in captured_downgrade.out
    assert "DROP TABLE property_profiles;" in captured_downgrade.out
    assert "DROP TABLE evidence;" in captured_downgrade.out
    assert "DROP TABLE extracted_fields;" in captured_downgrade.out
    assert "DROP TABLE extraction_jobs;" in captured_downgrade.out
    assert "DROP TABLE ocr_results;" in captured_downgrade.out
    assert "DROP TABLE document_processing_jobs;" in captured_downgrade.out
    assert "DROP TABLE documents;" in captured_downgrade.out
    assert "DROP TABLE cases;" in captured_downgrade.out
    assert "DROP TABLE case_sequences;" in captured_downgrade.out
    assert "DROP TABLE area_officer_assignments;" in captured_downgrade.out
    assert "DROP TABLE areas;" in captured_downgrade.out
    assert "DROP TABLE refresh_tokens;" in captured_downgrade.out
    assert "DROP TABLE users;" in captured_downgrade.out
    assert "DROP EXTENSION IF EXISTS postgis" in captured_downgrade.out


def test_migration_cycle_upgrade_downgrade() -> None:
    """Verify that Alembic upgrade head, downgrade base, and re-upgrade work on live database."""
    if not check_db_connectivity_sync():
        pytest.skip("PostgreSQL is not running at DATABASE_URL")

    from alembic import command

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    # 3. Re-upgrade to head
    command.upgrade(alembic_cfg, "head")
