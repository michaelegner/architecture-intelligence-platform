"""I1 spec §10 import report (v0.5.0 I5 finding F2): the versioned public shape of
`POST /api/import` and `POST /api/import/service/{serviceId}`.

The report is additive. The pre-existing `import_id`, `committed` and `sources` keys keep their
exact meaning (`sources` is the per-source reconciliation stats of the configured runs), and
`report_version` plus `runs` carry what I1 §10 requires the report to include: every source's own
result (including the rejected sources of a run that did not commit), the inventory status and
revision, removals, tombstone decisions, and diagnostics.

`runs` is the deterministic semantic projection of I1 §10: it carries no capture ids or
timestamps, and every list in it is sorted. Diagnostics are public only as a stable `code`, the
`source_instance_id`, and a sanitized `source_pointer`. Diagnostic messages are never exposed,
because they can contain absolute host paths and snippets of rejected input (the I2 §5
sanitization rule); the server log keeps them.

The committed JSON Schema (`schemas/import/v0.5/import-report.schema.json`) is generated from these
models by `app.ingestion.import_report_schema` and pinned by a test.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.architecture_intelligence.evidence_projection import sanitize_source_locator
from app.graph.importer import ImportRunStats, SourceImportStats
from app.sources.inventory import InventoryStatus
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult
from app.sources.tombstones import TombstoneRejectionReason

REPORT_VERSION = "aip-import-report/1"

RunKind = Literal["filesystem", "kubernetes"]

# Formats of the identities AIP itself computes (I1 §5.1, §6). Character classes only: the patterns
# must also compile under pydantic-core's regex engine, so no lookaround. Operator-supplied values
# (a tombstone's target and revision) are deliberately not constrained, so a malformed tombstone
# can never turn the report itself into an error.
_SOURCE_ID = r"^urn:aip:source:(filesystem|kubernetes):[0-9a-f]{64}$"
_SCOPE_ID = r"^urn:aip:discovery-scope:[0-9a-f]{64}$"
_INVENTORY_REVISION = r"^urn:aip:inventory-revision:[0-9a-f]{64}$"
_DIGEST = r"^[0-9a-f]{64}$"
# A public locator is relative: never absolute, never a Windows path, never a URL query/fragment.
_RELATIVE_LOCATOR = r"^[^/\\?#][^\\?#]*$"

SourceId = Annotated[str, Field(pattern=_SOURCE_ID)]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReportDiagnostic(_Frozen):
    code: DiagnosticCode
    source_instance_id: SourceId | None
    source_pointer: str | None


class ReportSourceResult(_Frozen):
    source_instance_id: SourceId
    locator: Annotated[str, Field(pattern=_RELATIVE_LOCATOR)] | None
    result: IngestionResult
    diagnostics: list[ReportDiagnostic]


class ReportTombstoneDecision(_Frozen):
    target_source_instance_id: str
    tombstone_revision: str
    accepted: bool
    reason: TombstoneRejectionReason | None


class ReportRun(_Frozen):
    kind: RunKind
    configured_source_id: str
    discovery_scope_id: Annotated[str, Field(pattern=_SCOPE_ID)] | None
    scope_definition_digest: Annotated[str, Field(pattern=_DIGEST)] | None
    inventory_status: InventoryStatus
    committed: bool
    inventory_revision: Annotated[str, Field(pattern=_INVENTORY_REVISION)] | None
    source_results: list[ReportSourceResult]
    removed_source_instance_ids: Annotated[
        list[SourceId], Field(json_schema_extra={"uniqueItems": True})
    ]
    tombstones: list[ReportTombstoneDecision]
    diagnostics: list[ReportDiagnostic]

    @model_validator(mode="after")
    def _deterministic(self) -> ReportRun:
        # The schema's uniqueItems, plus the ordering guarantees a JSON Schema cannot express: the
        # run is the deterministic semantic projection of I1 §10, so every list has one order.
        if len(set(self.removed_source_instance_ids)) != len(self.removed_source_instance_ids):
            raise ValueError("removed_source_instance_ids must be unique")
        if self.removed_source_instance_ids != sorted(self.removed_source_instance_ids):
            raise ValueError("removed_source_instance_ids must be sorted")
        ids = [r.source_instance_id for r in self.source_results]
        if ids != sorted(set(ids)):
            raise ValueError("source_results must be unique and sorted by source_instance_id")
        return self


class ReportSourceStats(_Frozen):
    """The pre-existing `sources` entry shape (`SourceImportStats`), unchanged."""

    source_instance_id: SourceId
    locator: str
    result: IngestionResult
    nodes_written: int
    relations_written: int
    nodes_expired: int
    relations_expired: int
    graph_revision_advanced: bool


class ImportReport(_Frozen):
    """The full `POST /api/import` response."""

    import_id: str
    committed: bool
    sources: dict[str, ReportSourceStats]
    report_version: Literal["aip-import-report/1"]
    runs: list[ReportRun]


class ServiceImportReport(ImportReport):
    """The full `POST /api/import/service/{serviceId}` response."""

    service_id: str


@dataclass(frozen=True)
class ConfiguredRun:
    """One configured source's discovery run, as the import endpoint executed it."""

    kind: RunKind
    configured_source_id: str
    root: Path
    stats: ImportRunStats


def _root_forms(root: Path) -> tuple[str, ...]:
    forms = {str(root), os.path.abspath(root)}
    try:
        forms.add(str(root.resolve()))
    except OSError:
        pass
    return tuple(sorted((form for form in forms if form), key=len, reverse=True))


def _relative_to_root(value: str, root_forms: Sequence[str]) -> str | None:
    """`value` as a relative POSIX path when it is the configured root or lies under it, else
    None. `.` stands for the root itself."""
    for root in root_forms:
        if value == root:
            return "."
        prefix = root.rstrip("/") + "/"
        if value.startswith(prefix):
            relative = PurePosixPath(value[len(prefix) :]).as_posix()
            return sanitize_source_locator(relative)
    return None


def sanitize_locator(locator: str | None, *, root: Path) -> str | None:
    """A public locator: relative to the configured root, or an already relative POSIX path, or
    None. Never an absolute host path."""
    if locator is None:
        return None
    relative = _relative_to_root(locator, _root_forms(root))
    if relative is not None:
        return relative
    return sanitize_source_locator(locator)


def sanitize_pointer(pointer: str | None, *, root: Path) -> str | None:
    """A public diagnostic pointer. Diagnostic pointers are heterogeneous (RFC 6901 JSON Pointers,
    entity or resource ids, and file locators), so the sanitizer uses the run's own context: a
    locator under the configured root becomes relative to it, an absolute path that names
    something on this host is dropped, and anything else (a JSON Pointer, an id) is kept."""
    if pointer is None:
        return None
    relative = _relative_to_root(pointer, _root_forms(root))
    if relative is not None:
        return relative
    if os.path.isabs(pointer) and os.path.lexists(pointer):
        return None
    return pointer


def _diagnostic(diagnostic: IngestionDiagnostic, *, root: Path) -> ReportDiagnostic:
    return ReportDiagnostic(
        code=diagnostic.code,
        source_instance_id=diagnostic.source_instance_id,
        source_pointer=sanitize_pointer(diagnostic.source_pointer, root=root),
    )


def _sorted_diagnostics(
    diagnostics: Sequence[IngestionDiagnostic], *, root: Path
) -> list[ReportDiagnostic]:
    rendered = {
        _diagnostic(diagnostic, root=root).model_dump_json(): _diagnostic(diagnostic, root=root)
        for diagnostic in diagnostics
    }
    return sorted(
        rendered.values(),
        key=lambda d: (d.code.value, d.source_instance_id or "", d.source_pointer or ""),
    )


def build_run(configured: ConfiguredRun) -> ReportRun:
    stats = configured.stats
    root = configured.root
    return ReportRun(
        kind=configured.kind,
        configured_source_id=configured.configured_source_id,
        discovery_scope_id=stats.discovery_scope_id,
        scope_definition_digest=stats.scope_definition_digest,
        inventory_status=stats.inventory_status,
        committed=stats.committed,
        inventory_revision=stats.inventory_revision,
        source_results=[
            ReportSourceResult(
                source_instance_id=source_result.source_instance_id,
                locator=sanitize_locator(source_result.locator, root=root),
                result=source_result.result,
                diagnostics=_sorted_diagnostics(source_result.diagnostics, root=root),
            )
            for source_result in sorted(stats.source_results, key=lambda r: r.source_instance_id)
        ],
        removed_source_instance_ids=sorted(stats.removed_source_instance_ids),
        tombstones=sorted(
            (
                ReportTombstoneDecision(
                    target_source_instance_id=decision.target_source_instance_id,
                    tombstone_revision=decision.tombstone_revision,
                    accepted=decision.accepted,
                    reason=(
                        TombstoneRejectionReason(decision.reason)
                        if decision.reason is not None
                        else None
                    ),
                )
                for decision in stats.tombstone_decisions
            ),
            key=lambda t: (t.target_source_instance_id, t.tombstone_revision),
        ),
        diagnostics=_sorted_diagnostics(stats.diagnostics, root=root),
    )


def _source_stats(stats: SourceImportStats) -> ReportSourceStats:
    return ReportSourceStats(
        source_instance_id=stats.source_instance_id,
        locator=stats.locator,
        result=stats.result,
        nodes_written=stats.nodes_written,
        relations_written=stats.relations_written,
        nodes_expired=stats.nodes_expired,
        relations_expired=stats.relations_expired,
        graph_revision_advanced=stats.graph_revision_advanced,
    )


def build_import_report(import_id: str, runs: Sequence[ConfiguredRun]) -> ImportReport:
    """The `POST /api/import` response. `sources` keeps its pre-v1 construction exactly: the
    per-source stats of every run, merged in run order."""
    combined: dict[str, SourceImportStats] = {}
    for configured in runs:
        combined.update(configured.stats.per_source)
    return ImportReport(
        import_id=import_id,
        committed=all(configured.stats.committed for configured in runs),
        sources={sid: _source_stats(stats) for sid, stats in combined.items()},
        report_version=REPORT_VERSION,
        runs=sorted(
            (build_run(configured) for configured in runs),
            key=lambda run: (run.kind, run.configured_source_id),
        ),
    )
