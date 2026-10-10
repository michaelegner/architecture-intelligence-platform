"""`telemetry.scoped-evidence` config (v0.6.0 I2.2a, decision record D1/D10)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.settings import AppConfig, load_config

ROOT = Path(__file__).resolve().parents[2]


def test_it_is_on_with_the_default_stream_when_the_block_is_absent():
    config = AppConfig.model_validate({})

    assert config.telemetry.scoped_evidence.enabled is True
    assert config.telemetry.scoped_evidence.stream_id == "otlp-http"


def test_an_existing_telemetry_section_without_the_block_adopts_the_default():
    config = AppConfig.model_validate(
        {"telemetry": {"http-correlation": {"enabled": True}, "service_aliases": {"a": "b"}}}
    )

    assert config.telemetry.scoped_evidence.enabled is True
    assert config.telemetry.service_aliases == {"a": "b"}


def test_the_hyphenated_yaml_keys_are_read():
    config = AppConfig.model_validate(
        {"telemetry": {"scoped-evidence": {"enabled": True, "stream-id": "prod-otlp"}}}
    )

    assert config.telemetry.scoped_evidence.enabled is True
    assert config.telemetry.scoped_evidence.stream_id == "prod-otlp"


def test_the_python_field_names_work_too():
    config = AppConfig.model_validate(
        {"telemetry": {"scoped_evidence": {"enabled": True, "stream_id": "x"}}}
    )

    assert config.telemetry.scoped_evidence.stream_id == "x"


def test_an_empty_stream_id_is_rejected():
    with pytest.raises(ValidationError):
        AppConfig.model_validate({"telemetry": {"scoped-evidence": {"stream-id": ""}}})


@pytest.mark.parametrize("name", ["config.yaml", "config.demo.yaml"])
def test_the_shipped_configs_enable_scoped_evidence(name):
    assert load_config(ROOT / name).telemetry.scoped_evidence.enabled is True


def test_the_root_config_documents_the_block():
    text = (ROOT / "config.yaml").read_text(encoding="utf-8")
    assert "scoped-evidence:" in text and "enabled: true" in text


def test_explicit_false_retains_legacy_ingestion_configuration():
    config = AppConfig.model_validate({"telemetry": {"scoped-evidence": {"enabled": False}}})
    assert config.telemetry.scoped_evidence.enabled is False
