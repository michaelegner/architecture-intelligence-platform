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
    import_apisix_measurement_source,
    import_apisix_source,
    import_kafka_consumer_state_source,
    import_kubernetes_source,
    retire_unconfigured_gateways,
    retire_unconfigured_kafka_consumer_state,
    retire_unconfigured_measurements,
)
from app.ingestion.import_report import ConfiguredRun
from app.settings import SourcesConfig
from app.sources.identity import (
    apisix_measurement_source_instance_id,
    apisix_source_instance_id,
    kafka_consumer_state_source_instance_id,
)
from app.sources.kafka_consumer_state_contract import duplicate_registrations
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
    # v0.7.0 I2.2c (I2.1 contract §1): two or more measurement registrations for the same
    # (gateway_instance_id, environment) are all rejected REJECTED_CONFLICT (GWM_DUPLICATE_SOURCE);
    # none commits. Distinct pairs coexist.
    pair_counts = Counter(
        (m.gateway_instance_id, m.environment) for m in sources.gateway_measurements
    )
    for measurement_config in sources.gateway_measurements:
        start = time.perf_counter()
        run_stats = import_apisix_measurement_source(
            driver,
            database=database,
            source_config=measurement_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
            duplicate_measurement_source=pair_counts[
                (measurement_config.gateway_instance_id, measurement_config.environment)
            ]
            > 1,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(
            ConfiguredRun(
                kind="apisix-measurement",
                configured_source_id=measurement_config.id,
                root=measurement_config.root,
                stats=run_stats,
            )
        )
    # A dropped measurement registration gets no run above; its carriers are retired here.
    retired_measurements = retire_unconfigured_measurements(
        driver,
        database=database,
        configured_source_instance_ids={
            apisix_measurement_source_instance_id(
                configured_source_id=measurement.id,
                gateway_instance_id=measurement.gateway_instance_id,
                environment=measurement.environment,
            )
            for measurement in sources.gateway_measurements
        },
    )
    for removal in retired_measurements:
        logger.info(
            "Removed import_id=%s sources=%s nodes_expired=%d relations_expired=%d",
            import_id,
            removal.source_instance_id,
            removal.nodes_expired,
            removal.relations_expired,
        )
    # v0.7.1 I1.3 (I1.1 contract §1, §6): runs after every declaring source so the Topics a capture
    # points at are already committed. Registrations that share a broker, environment and a group
    # are all rejected (KAFKA_DUPLICATE_SOURCE); none commits.
    duplicate_kafka = duplicate_registrations(sources.kafka_consumer_state)
    uncommitted_kafka: set[str] = set()
    for kafka_config in sources.kafka_consumer_state:
        start = time.perf_counter()
        run_stats = import_kafka_consumer_state_source(
            driver,
            database=database,
            source_config=kafka_config,
            migration_mappings=migration_index,
            tombstones=tombstones,
            duplicate_registration=kafka_config.id in duplicate_kafka,
        )
        if not run_stats.committed:
            uncommitted_kafka.add(kafka_config.id)
        duration_ms = int((time.perf_counter() - start) * 1000)
        _log_run(import_id, run_stats, duration_ms)
        run_results.append(
            ConfiguredRun(
                kind="kafka-consumer-state",
                configured_source_id=kafka_config.id,
                root=kafka_config.root,
                stats=run_stats,
            )
        )
    # A dropped registration, or one whose allow-list changed (a new source instance id), gets no
    # run above; the stale source's carriers are retired here (I1.1 contract §5).
    retired_kafka = retire_unconfigured_kafka_consumer_state(
        driver,
        database=database,
        configured_source_instance_ids={
            kafka_consumer_state_source_instance_id(
                configured_source_id=kafka.id,
                broker_id=kafka.broker_id,
                environment=kafka.environment,
                consumer_groups=kafka.consumer_groups,
            )
            for kafka in sources.kafka_consumer_state
        },
        # A still-configured registration whose replacement did not commit keeps its previous
        # source until a replacement is accepted.
        protected_configured_source_ids=uncommitted_kafka,
    )
    for removal in retired_kafka:
        logger.info(
            "Removed import_id=%s sources=%s nodes_expired=%d relations_expired=%d",
            import_id,
            removal.source_instance_id,
            removal.nodes_expired,
            removal.relations_expired,
        )
    return import_id, run_results
