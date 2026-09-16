import shutil
from pathlib import Path

from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.sources.identity import EMPTY_CLOSURE_DIGEST
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
    """A parse failure must never be silently treated as "this candidate is legitimately absent" -
    unlike a file that doesn't exist, bytes were read here but couldn't be understood, so
    `enumeration_complete` must be False (I1 spec §6's FAILED trigger), blocking the whole run's
    commit rather than letting a corrupted/mid-edit file authorize deleting prior committed facts
    for that source."""
    service_dir = tmp_path / "broken-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text("openapi: 3.1.0\n  bad indent: [\n")

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is False
    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_discover_skips_non_mapping_document_with_diagnostic(tmp_path):
    service_dir = tmp_path / "list-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text("- just\n- a\n- list\n")

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is False
    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_a_parse_failure_does_not_prevent_other_valid_sources_from_being_discovered(tmp_path):
    """`enumeration_complete=False` still reports every source it could successfully parse - the
    orchestrator is what refuses to commit anything for a FAILED run (I1 spec §6), not the
    discoverer silently hiding the sources it did understand."""
    broken_dir = tmp_path / "broken-service"
    broken_dir.mkdir()
    (broken_dir / "openapi.yaml").write_text("openapi: 3.1.0\n  bad indent: [\n")

    ok_dir = tmp_path / "ok-service"
    ok_dir.mkdir()
    (ok_dir / "openapi.yaml").write_text(
        'openapi: 3.1.0\ninfo:\n  title: OkService\n  version: "1.0"\npaths: {}\n'
    )

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is False
    assert len(outcome.loaded_sources) == 1
    assert Path(outcome.loaded_sources[0].descriptor.locator) == ok_dir / "openapi.yaml"


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


def test_unquoted_yaml_timestamp_in_an_example_value_is_normalized_to_a_string(tmp_path):
    """YAML's default schema auto-converts an unquoted date/timestamp-shaped scalar into a native
    `datetime.date`/`datetime.datetime` - a type RFC 8785 canonicalization (used deep inside every
    adapter's identity/digest computation) has no representation for and would otherwise crash on
    with an opaque library error instead of a clean diagnostic."""
    service_dir = tmp_path / "dated-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text(
        "openapi: 3.1.0\n"
        'info:\n  title: DatedService\n  version: "1.0"\n'
        "paths:\n"
        "  /events:\n"
        "    get:\n"
        "      operationId: getEvent\n"
        "      responses:\n"
        '        "200":\n'
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                type: object\n"
        "              examples:\n"
        "                sample:\n"
        "                  value:\n"
        "                    eventDate: 2075-10-27 16:51:41.787000+00:00\n"
    )

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.diagnostics == ()
    [source] = outcome.loaded_sources
    example_value = source.document["paths"]["/events"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["examples"]["sample"]["value"]
    assert isinstance(example_value["eventDate"], str)
    assert example_value["eventDate"] == "2075-10-27T16:51:41.787000+00:00"


def test_loaded_source_carries_the_configured_root_as_source_root():
    discoverer = FilesystemSourceDiscoverer(_config(EXAMPLES_DIR))
    outcome = discoverer.discover()

    assert outcome.loaded_sources
    for source in outcome.loaded_sources:
        assert source.source_root == str(EXAMPLES_DIR)


def test_a_source_with_no_refs_gets_the_empty_closure_digest():
    discoverer = FilesystemSourceDiscoverer(_config(EXAMPLES_DIR))
    outcome = discoverer.discover()

    product_service_source = next(
        s
        for s in outcome.loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "product-service" / "openapi.yaml"
    )
    assert product_service_source.descriptor.dependency_closure_digest == EMPTY_CLOSURE_DIGEST


def test_a_source_with_a_real_cross_file_ref_gets_a_non_empty_closure_digest(tmp_path):
    service_dir = tmp_path / "cross-file-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text(
        "openapi: 3.1.0\n"
        'info:\n  title: CrossFileService\n  version: "1.0"\n'
        "paths:\n"
        "  /widgets:\n"
        "    get:\n"
        "      operationId: getWidget\n"
        "      responses:\n"
        '        "200":\n'
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: schemas/widget.yaml#/Widget\n"
    )
    (service_dir / "schemas").mkdir()
    (service_dir / "schemas" / "widget.yaml").write_text("Widget:\n  type: object\n")

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is True
    [source] = outcome.loaded_sources
    assert source.descriptor.dependency_closure_digest is not None
    assert source.descriptor.dependency_closure_digest != EMPTY_CLOSURE_DIGEST


def test_a_ref_that_would_fail_resolution_does_not_fail_discovery(tmp_path):
    """The discoverer's closure walk is best-effort: a bad/cyclic/over-limit `$ref` graph is left
    for the adapter's own authoritative resolution (at map() time) to reject with the real
    diagnostic - discovery itself must never fail just because a closure walk couldn't complete."""
    service_dir = tmp_path / "dangling-ref-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text(
        "openapi: 3.1.0\n"
        'info:\n  title: DanglingRefService\n  version: "1.0"\n'
        "paths:\n"
        "  /widgets:\n"
        "    get:\n"
        "      operationId: getWidget\n"
        "      responses:\n"
        '        "200":\n'
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        "              schema:\n"
        "                $ref: schemas/missing.yaml#/Widget\n"
    )

    discoverer = FilesystemSourceDiscoverer(_config(tmp_path))
    outcome = discoverer.discover()

    assert outcome.enumeration_complete is True
    [source] = outcome.loaded_sources
    assert source.descriptor.dependency_closure_digest is None
