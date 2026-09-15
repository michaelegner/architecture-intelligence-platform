import shutil
from pathlib import Path

from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.sources.model import DiagnosticCode, FilesystemSourceConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _config(root: Path, **overrides) -> FilesystemSourceConfig:
    fields = {"id": "test-source", "root": root}
    fields.update(overrides)
    return FilesystemSourceConfig(**fields)


def test_discover_finds_all_bundled_example_sources():
    discoverer = FilesystemSourceDiscoverer(_config(EXAMPLES_DIR))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is True
    assert outcome.diagnostics == ()
    locators = {
        Path(s.descriptor.locator).relative_to(EXAMPLES_DIR) for s in outcome.loaded_sources
    }
    assert locators == {
        Path("order-service/openapi.yaml"),
        Path("order-service/asyncapi.yaml"),
        Path("order-service/architecture.yaml"),
        Path("product-service/openapi.yaml"),
        Path("payment-service/asyncapi.yaml"),
        Path("invoice-service/asyncapi.yaml"),
    }


def test_discover_reports_incomplete_enumeration_for_missing_root(tmp_path):
    discoverer = FilesystemSourceDiscoverer(_config(tmp_path / "does-not-exist"))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is False
    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.SOURCE_ROOT_UNAVAILABLE


def test_discover_skips_malformed_document_with_diagnostic(tmp_path):
    service_dir = tmp_path / "broken-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text("openapi: 3.1.0\n  bad indent: [\n")

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is True
    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_discover_skips_non_mapping_document_with_diagnostic(tmp_path):
    service_dir = tmp_path / "list-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text("- just\n- a\n- list\n")

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_source_instance_id_is_independent_of_checkout_location(tmp_path):
    checkout_one = tmp_path / "checkout-one"
    checkout_two = tmp_path / "checkout-two"
    for checkout in (checkout_one, checkout_two):
        shutil.copytree(EXAMPLES_DIR / "product-service", checkout / "product-service")

    config = {"id": "aip-bundled-examples-v0.5", "stable_target_identity": "urn:aip:logical-root:x"}
    outcome_one = FilesystemSourceDiscoverer(_config(checkout_one, **config)).discover()
    outcome_two = FilesystemSourceDiscoverer(_config(checkout_two, **config)).discover()

    ids_one = {s.descriptor.source_instance_id for s in outcome_one.loaded_sources}
    ids_two = {s.descriptor.source_instance_id for s in outcome_two.loaded_sources}
    assert ids_one == ids_two
    assert len(ids_one) == 1


def test_document_dialect_version_is_captured():
    discoverer = FilesystemSourceDiscoverer(_config(EXAMPLES_DIR))
    outcome = discoverer.discover()

    openapi_source = next(
        s
        for s in outcome.loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "product-service" / "openapi.yaml"
    )
    assert openapi_source.descriptor.document_dialect_version == "3.1.0"
