"""Running every configured source through a real import (`POST /api/import`): the configured
filesystem directories and Kubernetes clusters, each as its own discovery run, sharing one
migration-mapping index and one tombstone set per request.

Moved out of `app.api.import_api` so the route only maps outcomes to HTTP.
"""

import logging
import time
import uuid
from collections import Counter

from app.graph.importer import (
    ImportRunStats,
    import_all_sources,
    import_apisix_source,
    import_kubernetes_source,
    retire_unconfigured_gateways,
)
from app.ingestion.import_report import ConfiguredRun
from app.settings import SourcesConfig
from app.sources.identity import apisix_source_instance_id
from app.sources.migration_mappings import load_migration_mappings
from app.sources.tombstones import load_tombstones

logger = logging.getLogger("architecture_intelligence.import")


class ImportConfigurationError(Exception):
    """The operator's configured migration mappings or tombstones cannot be loaded - a
    configuration error for the whole request, never a per-source data problem."""


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
    for diagnostic in run_stats.diagnostics:
        logger.warning(
            "Import diagnostic import_id=%s source=%s code=%s pointer=%s message=%s",
            import_id,
            diagnostic.source_instance_id,
            diagnostic.code,
            diagnostic.source_pointer,
            diagnostic.message,
        )
    if run_stats.removed_source_instance_ids:
        logger.info(
            "Removed import_id=%s sources=%s",
            import_id,
            ",".join(run_stats.removed_source_instance_ids),
        )


def run_all_configured_sources(
    sources: SourcesConfig, *, driver, database: str
) -> tuple[str, list[ConfiguredRun]]:
    """Imports every configured filesystem directory and Kubernetes cluster, each as its own
    discovery run (I1 spec §6), and returns the request's import id with one `ConfiguredRun` per
    configured source. Raises `ImportConfigurationError` - before touching the driver - when the
    configured migration mappings or tombstones fail to load."""
    # I1 spec §5.1.1: "Missing or modified migration configuration is diagnosed and MUST NOT fall
    # back to a directory slug or name-derived identity" - loaded once per request (not once per
    # configured source directory) since the same shared-identity index applies uniformly across
    # every directory's own discovery run. A broken configured migration file is an operator
    # configuration error, not a per-source data problem, so it fails the whole request loudly
    # rather than silently importing with a partial/empty index.
    migration_index, migration_diagnostics = load_migration_mappings(sources.migrations)
    if migration_diagnostics:
        raise ImportConfigurationError(
            "migration mapping configuration is invalid: "
            f"{[d.message for d in migration_diagnostics]}"
        )

    # I2 Draft 0.2 §3 prerequisite slice's minimal operator-facing tombstone surface - loaded once
    # per request, mirroring the migration-mapping load above; a broken configured tombstone file is
    # an operator configuration error, not a per-source data problem.
    tombstones, tombstone_diagnostics = load_tombstones(sources.tombstones)
    if tombstone_diagnostics:
        raise ImportConfigurationError(
            f"tombstone configuration is invalid: {[d.message for d in tombstone_diagnostics]}"
        )

    import_id = uuid.uuid4().hex
    run_results = []
    # v0.7.0 I1.2 (I1 §3.6 as amended): each configured source is its own discovery run, so the
    # API-contract carriers are gated on the request's configuration, not on a run's contents.
    api_contract_associations = bool(sources.gateways)
    for source_config in sources.directories:
        start = time.perf_counter()
        run_stats = import_all_sources(
            driver,
            database=database,
            source_config=source_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
            api_contract_associations=api_contract_associations,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(
            ConfiguredRun(
                kind="filesystem",
                configured_source_id=source_config.id,
                root=source_config.root,
                stats=run_stats,
            )
        )
    for cluster_config in sources.clusters:
        start = time.perf_counter()
        run_stats = import_kubernetes_source(
            driver,
            database=database,
            source_config=cluster_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(
            ConfiguredRun(
                kind="kubernetes",
                configured_source_id=cluster_config.id,
                root=cluster_config.root,
                stats=run_stats,
            )
        )
    # v0.7.0 I1.4 (contract §1): two registrations that declare the same gateway_instance_id are
    # both rejected REJECTED_CONFLICT (GW_DUPLICATE_INSTANCE); neither commits.
    instance_counts = Counter(gateway.gateway_instance_id for gateway in sources.gateways)
    for gateway_config in sources.gateways:
        start = time.perf_counter()
        run_stats = import_apisix_source(
            driver,
            database=database,
            source_config=gateway_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
            duplicate_gateway_instance=instance_counts[gateway_config.gateway_instance_id] > 1,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(
            ConfiguredRun(
                kind="apisix",
                configured_source_id=gateway_config.id,
                root=gateway_config.root,
                stats=run_stats,
            )
        )
    # v0.7.0 I1.4 (contract §5): a dropped registration gets no run above, so its persisted
    # carriers are retired here against the request's configured registrations.
    retired = retire_unconfigured_gateways(
        driver,
        database=database,
        configured_source_instance_ids={
            apisix_source_instance_id(
                configured_apisix_source_id=gateway.id,
                gateway_instance_id=gateway.gateway_instance_id,
            )
            for gateway in sources.gateways
        },
    )
    for removal in retired:
        logger.info(
            "Removed import_id=%s sources=%s nodes_expired=%d relations_expired=%d",
            import_id,
            removal.source_instance_id,
            removal.nodes_expired,
            removal.relations_expired,
        )
    return import_id, run_results
