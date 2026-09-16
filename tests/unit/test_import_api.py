from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.import_api import _run_all_configured_sources
from app.settings import AppConfig, Secrets, Settings, SourcesConfig


def _settings(*, migrations: list[Path]) -> Settings:
    config = AppConfig(sources=SourcesConfig(directories=[], migrations=migrations))
    return Settings(config=config, secrets=Secrets(neo4j_user="neo4j", neo4j_password="test"))


def test_no_configured_migrations_runs_with_no_directories_and_no_error():
    settings = _settings(migrations=[])
    import_id, run_results = _run_all_configured_sources(settings, driver=None)
    assert import_id
    assert run_results == []


def test_a_missing_configured_migration_file_raises_before_touching_the_driver(tmp_path):
    """I1 spec §5.1.1: "Missing or modified migration configuration is diagnosed and MUST NOT fall
    back to a directory slug or name-derived identity" - a broken configured migration path must
    fail the whole request loudly, not silently import with an empty/partial index. The driver is
    passed as None here and must never be touched, since the failure happens before any per-source
    loop iteration runs."""
    settings = _settings(migrations=[tmp_path / "does-not-exist.yaml"])
    with pytest.raises(HTTPException) as exc_info:
        _run_all_configured_sources(settings, driver=None)
    assert exc_info.value.status_code == 500
    assert "migration mapping configuration is invalid" in exc_info.value.detail
