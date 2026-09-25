"""v0.5.0 I5 finding F2: the import report's models, sanitizer and frozen schema (unit level)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.graph.importer import ImportRunStats, SourceRunResult, TombstoneDecision
from app.ingestion.import_report import (
    ConfiguredRun,
    ReportRun,
    build_import_report,
    sanitize_locator,
    sanitize_pointer,
)
from app.ingestion.import_report_schema import (
    IMPORT_REPORT_SCHEMA_PATH,
    SERVICE_IMPORT_REPORT_SCHEMA_PATH,
    render_import_report_schema,
    render_service_import_report_schema,
)
from app.sources.inventory import InventoryStatus
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult

SID_A = "urn:aip:source:filesystem:" + "a" * 64
SID_B = "urn:aip:source:filesystem:" + "b" * 64


def test_committed_import_report_schemas_match_the_generated_schemas():
    for path, render in (
        (IMPORT_REPORT_SCHEMA_PATH, render_import_report_schema),
        (SERVICE_IMPORT_REPORT_SCHEMA_PATH, render_service_import_report_schema),
    ):
        assert path.read_text() == render(), (
            f"{path.name} is out of date - regenerate it with "
            "`uv run python -m app.ingestion.import_report_schema` after a deliberate, recorded "
            "contract change."
        )


def test_locators_under_the_configured_root_become_relative(tmp_path):
    root = tmp_path / "decl"
    root.mkdir()
    assert sanitize_locator(str(root / "svc" / "openapi.yaml"), root=root) == "svc/openapi.yaml"
    assert sanitize_locator("decl/svc/openapi.yaml", root=Path("decl")) == "svc/openapi.yaml"
    assert sanitize_locator(str(root), root=root) == "."


def test_locators_outside_the_root_are_never_absolute(tmp_path):
    root = tmp_path / "decl"
    root.mkdir()
    assert sanitize_locator("/etc/passwd", root=root) is None
    assert sanitize_locator("k8s/envelope.yaml", root=root) == "k8s/envelope.yaml"
    assert sanitize_locator(None, root=root) is None


def test_pointers_keep_json_pointers_and_ids_but_drop_host_paths(tmp_path):
    root = tmp_path / "decl"
    root.mkdir()
    (root / "svc").mkdir()
    # A locator used as a pointer is made relative to the root.
    assert sanitize_pointer(str(root / "svc"), root=root) == "svc"
    # RFC 6901 pointers and entity ids pass through unchanged.
    assert sanitize_pointer("/calls/0", root=root) == "/calls/0"
    assert sanitize_pointer("/x-aip-service-id", root=root) == "/x-aip-service-id"
    assert sanitize_pointer("schema:owned:" + "c" * 64, root=root) == "schema:owned:" + "c" * 64
    # An absolute path that names something on this host is dropped.
    assert sanitize_pointer(str(tmp_path), root=root) is None
    assert sanitize_pointer(None, root=root) is None


def _stats(**overrides) -> ImportRunStats:
    base = {
        "inventory_status": InventoryStatus.PARTIAL,
        "committed": False,
        "per_source": {},
        "removed_source_instance_ids": (),
        "diagnostics": (),
    }
    base.update(overrides)
    return ImportRunStats(**base)


def test_builder_sorts_results_diagnostics_and_runs_and_drops_messages(tmp_path):
    root = tmp_path / "decl"
    root.mkdir()
    stats = _stats(
        source_results=(
            SourceRunResult(SID_B, str(root / "b" / "openapi.yaml"), IngestionResult.ACCEPTED, ()),
            SourceRunResult(
                SID_A,
                str(root / "a" / "openapi.yaml"),
                IngestionResult.REJECTED_UNSUPPORTED,
                (
                    IngestionDiagnostic(
                        code=DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED,
                        message=f"secret detail {root}",
                        source_pointer=str(root / "a" / "openapi.yaml"),
                    ),
                ),
            ),
        ),
        tombstone_decisions=(TombstoneDecision(SID_A, "1", False, "STALE_PRIOR_REVISION"),),
    )
    report = build_import_report(
        "import-1",
        [
            ConfiguredRun(kind="kubernetes", configured_source_id="z", root=root, stats=_stats()),
            ConfiguredRun(kind="filesystem", configured_source_id="a", root=root, stats=stats),
        ],
    )

    assert [(run.kind, run.configured_source_id) for run in report.runs] == [
        ("filesystem", "a"),
        ("kubernetes", "z"),
    ]
    run = report.runs[0]
    assert [r.source_instance_id for r in run.source_results] == [SID_A, SID_B]
    assert run.source_results[0].locator == "a/openapi.yaml"
    assert run.source_results[0].diagnostics[0].source_pointer == "a/openapi.yaml"
    assert run.tombstones[0].reason.value == "STALE_PRIOR_REVISION"
    dumped = report.model_dump_json()
    assert "secret detail" not in dumped and str(root) not in dumped


def test_run_model_enforces_unique_sorted_lists_and_identity_formats():
    common = {
        "kind": "filesystem",
        "configured_source_id": "x",
        "discovery_scope_id": None,
        "scope_definition_digest": None,
        "inventory_status": "PARTIAL",
        "committed": False,
        "inventory_revision": None,
        "source_results": [],
        "tombstones": [],
        "diagnostics": [],
    }
    ReportRun(**common, removed_source_instance_ids=[SID_A, SID_B])
    with pytest.raises(ValidationError):
        ReportRun(**common, removed_source_instance_ids=[SID_A, SID_A])
    with pytest.raises(ValidationError):
        ReportRun(**common, removed_source_instance_ids=[SID_B, SID_A])
    with pytest.raises(ValidationError):
        ReportRun(**common, removed_source_instance_ids=["not-a-source-id"])
    with pytest.raises(ValidationError):
        ReportRun(**{**common, "inventory_revision": "rev-1"}, removed_source_instance_ids=[])
