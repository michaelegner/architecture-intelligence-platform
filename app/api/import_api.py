import logging
import time
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_driver, get_settings
from app.graph.importer import ImportRunStats, SourceImportStats, import_all_sources
from app.graph.repository import open_session
from app.settings import Settings
from app.sources.migration_mappings import load_migration_mappings
from app.sources.tombstones import load_tombstones

router = APIRouter(prefix="/api/import", tags=["import"])
logger = logging.getLogger("architecture_intelligence.import")


def _log_run(import_id: str, run_stats: ImportRunStats, duration_ms: int) -> None:
    for source_instance_id, stats in run_stats.per_source.items():
        logger.info(
            "Imported import_id=%s source=%s locator=%s result=%s nodes_written=%d "
            "relations_written=%d nodes_expired=%d relations_expired=%d "
            "graph_revision_advanced=%s duration_ms=%d",
            import_id,
            source_instance_id,
            stats.locator,
            stats.result,
            stats.nodes_written,
            stats.relations_written,
            stats.nodes_expired,
            stats.relations_expired,
            stats.graph_revision_advanced,
            duration_ms,
        )
    if run_stats.removed_source_instance_ids:
        logger.info(
            "Removed import_id=%s sources=%s",
            import_id,
            ",".join(run_stats.removed_source_instance_ids),
        )


def _run_all_configured_sources(settings: Settings, driver) -> tuple[str, list[ImportRunStats]]:
    # I1 spec §5.1.1: "Missing or modified migration configuration is diagnosed and MUST NOT fall
    # back to a directory slug or name-derived identity" - loaded once per request (not once per
    # configured source directory) since the same shared-identity index applies uniformly across
    # every directory's own discovery run. A broken configured migration file is an operator
    # configuration error, not a per-source data problem, so it fails the whole request loudly
    # rather than silently importing with a partial/empty index.
    migration_index, migration_diagnostics = load_migration_mappings(
        settings.config.sources.migrations
    )
    if migration_diagnostics:
        raise HTTPException(
            status_code=500,
            detail=(
                "migration mapping configuration is invalid: "
                f"{[d.message for d in migration_diagnostics]}"
            ),
        )

    # I2 Draft 0.2 §3 prerequisite slice's minimal operator-facing tombstone surface - loaded once
    # per request, mirroring the migration-mapping load above; a broken configured tombstone file is
    # an operator configuration error, not a per-source data problem.
    tombstones, tombstone_diagnostics = load_tombstones(settings.config.sources.tombstones)
    if tombstone_diagnostics:
        raise HTTPException(
            status_code=500,
            detail=(
                f"tombstone configuration is invalid: {[d.message for d in tombstone_diagnostics]}"
            ),
        )

    import_id = uuid.uuid4().hex
    run_results = []
    for source_config in settings.config.sources.directories:
        start = time.perf_counter()
        run_stats = import_all_sources(
            driver,
            database=settings.config.graph.database,
            source_config=source_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(run_stats)
    return import_id, run_results


@router.post("")
def import_all(settings: Settings = Depends(get_settings), driver=Depends(get_driver)) -> dict:
    """POST /api/import - imports every configured source (I1 spec §14). Each configured
    directory is its own atomic discovery run (I1 spec §6): one run's PARTIAL/FAILED status never
    blocks another's commit."""
    import_id, run_results = _run_all_configured_sources(settings, driver)
    combined_per_source: dict[str, SourceImportStats] = {}
    for run_stats in run_results:
        combined_per_source.update(run_stats.per_source)
    return {
        "import_id": import_id,
        "committed": all(run_stats.committed for run_stats in run_results),
        "sources": {sid: asdict(s) for sid, s in combined_per_source.items()},
    }


@router.post("/service/{service_id}")
def import_one_service(
    service_id: str, settings: Settings = Depends(get_settings), driver=Depends(get_driver)
) -> dict:
    """POST /api/import/service/{serviceId} reimports every configured source and reports the
    resulting stats, then confirms the requested canonical Service ID (e.g. "service:order-
    service") now exists. Under I1, a service may be declared by more than one source and a source
    may declare more than one service (ADR 0009), so a single-source-scoped reimport is no longer
    a meaningful unit - the whole configured scope is always reimported."""
    import_id, run_results = _run_all_configured_sources(settings, driver)
    combined_per_source: dict[str, SourceImportStats] = {}
    for run_stats in run_results:
        combined_per_source.update(run_stats.per_source)

    with open_session(driver, database=settings.config.graph.database) as session:
        exists = (
            session.run("MATCH (s:Service {id: $id}) RETURN count(s) AS c", id=service_id).single()[
                "c"
            ]
            > 0
        )
    if not exists:
        raise HTTPException(status_code=404, detail=f"no known service: {service_id}")

    return {
        "import_id": import_id,
        "service_id": service_id,
        "committed": all(run_stats.committed for run_stats in run_results),
        "sources": {sid: asdict(s) for sid, s in combined_per_source.items()},
    }
