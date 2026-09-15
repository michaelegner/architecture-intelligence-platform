from dataclasses import dataclass

import neo4j

from app.canonical.model import ArchitectureModel
from app.graph.repository import open_session
from app.graph.revision_fence import bump_revision
from app.graph.schema import ensure_schema
from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.claim_reconciliation import plan_source_claim_reconciliation
from app.sources.inventory import InventoryStatus
from app.sources.model import FilesystemSourceConfig, IngestionDiagnostic, IngestionResult
from app.sources.removal_authority import authorize_source_removal
from app.sources.replay import ReplayCase, classify_replay_case
from app.validation.canonical_validation import validate_canonical_model

NODE_LABELS = {
    "services": "Service",
    "operations": "Operation",
    "queues": "Queue",
    "messages": "Message",
    "schemas": "Schema",
    "provenance": "Evidence",
}

# I1 spec §4/§7: this is the source-adapter seam's own frozen relation vocabulary, unchanged from
# the PoC-era value in the now-deleted app.graph.reconciliation - relocated here since that module
# is deleted (its node/relation-id set diffing is superseded by source-instance-scoped,
# multi-owner-aware reconciliation below).
KNOWN_RELATION_TYPES = {
    "PROVIDES",
    "CALLS",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "SENDS",
    "RECEIVES_FROM",
    "CARRIES",
    "CONFORMS_TO",
    "DEAD_LETTERS_TO",
}


def relation_key(relation) -> str:
    return f"{relation.type}:{relation.source_id}:{relation.target_id}"


def _model_node_ids(model: ArchitectureModel) -> set[str]:
    return {
        *(s.id for s in model.services),
        *(o.id for o in model.operations),
        *(q.id for q in model.queues),
        *(m.id for m in model.messages),
        *(sc.id for sc in model.schemas),
        *(p.id for p in model.provenance),
    }


def _model_relation_keys(model: ArchitectureModel) -> set[str]:
    return {relation_key(r) for r in model.relations}


# Ownership is now tracked per SOURCE INSTANCE, not per service-directory slug (ADR 0009): one
# source may declare many services, and a service may be declared by more than one source. A full
# reimport rewrites every `.owner_source_ids` value, so no data migration from the old `.sources`
# property name is required (a fresh graph never has both).
_MERGE_NODE_TEMPLATE = (
    "MERGE (n:{label} {{id: $id}}) "
    "SET n += $props "
    "SET n.owner_source_ids = CASE WHEN $source_instance_id IN coalesce(n.owner_source_ids, []) "
    "THEN n.owner_source_ids ELSE coalesce(n.owner_source_ids, []) + $source_instance_id END"
)

_MERGE_RELATION_TEMPLATE = (
    "MATCH (a {{id: $source_id}}), (b {{id: $target_id}}) "
    "MERGE (a)-[r:{relation_type}]->(b) "
    "SET r.key = $key "
    "SET r.owner_source_ids = CASE WHEN $source_instance_id IN coalesce(r.owner_source_ids, []) "
    "THEN r.owner_source_ids ELSE coalesce(r.owner_source_ids, []) + $source_instance_id END "
    "SET r.evidence_ids = reduce(acc = coalesce(r.evidence_ids, []), eid IN $evidence_ids | "
    "CASE WHEN eid IN acc THEN acc ELSE acc + eid END)"
)

_OWNED_NODE_IDS_QUERY = (
    "MATCH (n) WHERE $source_instance_id IN coalesce(n.owner_source_ids, []) RETURN n.id AS id"
)
_OWNED_RELATION_KEYS_QUERY = "MATCH ()-[r]->() WHERE $source_instance_id IN coalesce(r.owner_source_ids, []) RETURN r.key AS key"

_STRIP_STALE_EVIDENCE_QUERY = (
    "UNWIND $ids AS eid "
    "MATCH ()-[r]->() WHERE eid IN coalesce(r.evidence_ids, []) "
    "SET r.evidence_ids = [x IN r.evidence_ids WHERE x <> eid]"
)
_EXPIRE_NODES_QUERY = (
    "UNWIND $ids AS nid "
    "MATCH (n {id: nid}) "
    "SET n.owner_source_ids = [x IN n.owner_source_ids WHERE x <> $source_instance_id] "
    "WITH n WHERE size(n.owner_source_ids) = 0 "
    "DETACH DELETE n"
)
_REMOVE_NODE_OWNERSHIP_QUERY = (
    "UNWIND $ids AS nid "
    "MATCH (n {id: nid}) "
    "SET n.owner_source_ids = [x IN n.owner_source_ids WHERE x <> $source_instance_id]"
)
# A stale relation key must not be deleted outright just because its declaring source stopped
# declaring it - it may still carry OBSERVED evidence (the H4 telemetry pipeline) or DECLARED
# evidence from another declaring source (shared-evidence case). This strips $source_instance_id
# from r.owner_source_ids, recomputes r.evidence_ids by removing only ids that are (a) DECLARED and
# (b) actually attributed to $source_instance_id via that Evidence node's own owner_source_ids -
# never touching another source's DECLARED evidence or any OBSERVED evidence - and only deletes the
# relation once evidence_ids is truly empty.
_EXPIRE_RELATIONS_QUERY = (
    "UNWIND $keys AS rkey "
    "MATCH ()-[r {key: rkey}]->() "
    "SET r.owner_source_ids = [x IN r.owner_source_ids WHERE x <> $source_instance_id] "
    "WITH r, [eid IN r.evidence_ids WHERE NOT EXISTS { "
    "MATCH (e:Evidence {id: eid}) "
    "WHERE e.evidence_type = 'DECLARED' AND $source_instance_id IN coalesce(e.owner_source_ids, []) "
    "} ] AS remaining_evidence_ids "
    "SET r.evidence_ids = remaining_evidence_ids "
    "WITH r WHERE size(r.evidence_ids) = 0 "
    "DELETE r"
)
_REMOVE_RELATION_OWNERSHIP_QUERY = (
    "UNWIND $keys AS rkey "
    "MATCH ()-[r {key: rkey}]->() "
    "SET r.owner_source_ids = [x IN r.owner_source_ids WHERE x <> $source_instance_id]"
)

_READ_SOURCE_STATE_QUERY = (
    "MATCH (s:SourceState {source_instance_id: $source_instance_id}) "
    "RETURN s.semantic_input_digest AS semantic_input_digest, "
    "s.scope_definition_digest AS scope_definition_digest"
)
_WRITE_SOURCE_STATE_QUERY = (
    "MERGE (s:SourceState {source_instance_id: $source_instance_id}) "
    "SET s.semantic_input_digest = $semantic_input_digest, "
    "s.scope_definition_digest = $scope_definition_digest, "
    "s.discovery_scope_id = $discovery_scope_id"
)
_READ_SOURCE_STATES_FOR_SCOPE_QUERY = (
    "MATCH (s:SourceState {discovery_scope_id: $discovery_scope_id}) "
    "RETURN s.source_instance_id AS source_instance_id, "
    "s.scope_definition_digest AS scope_definition_digest"
)
_DELETE_SOURCE_STATE_QUERY = (
    "MATCH (s:SourceState {source_instance_id: $source_instance_id}) DELETE s"
)


@dataclass(frozen=True)
class SourceImportStats:
    source_instance_id: str
    locator: str
    result: IngestionResult
    nodes_written: int
    relations_written: int
    nodes_expired: int
    relations_expired: int
    graph_revision_advanced: bool


@dataclass(frozen=True)
class ImportRunStats:
    inventory_status: InventoryStatus
    committed: bool
    per_source: dict[str, SourceImportStats]
    removed_source_instance_ids: tuple[str, ...]
    diagnostics: tuple[IngestionDiagnostic, ...]


def _write_nodes(
    tx: neo4j.ManagedTransaction, source_instance_id: str, model: ArchitectureModel
) -> int:
    count = 0
    for field_name, label in NODE_LABELS.items():
        query = _MERGE_NODE_TEMPLATE.format(label=label)
        for entity in getattr(model, field_name):
            tx.run(
                query,
                id=entity.id,
                props=entity.model_dump(exclude={"id"}),
                source_instance_id=source_instance_id,
            )
            count += 1
    return count


def _write_relations(
    tx: neo4j.ManagedTransaction, source_instance_id: str, model: ArchitectureModel
) -> int:
    for relation in model.relations:
        query = _MERGE_RELATION_TEMPLATE.format(relation_type=relation.type)
        tx.run(
            query,
            source_id=relation.source_id,
            target_id=relation.target_id,
            key=relation_key(relation),
            source_instance_id=source_instance_id,
            evidence_ids=relation.evidence_ids,
        )
    return len(model.relations)


def import_source(
    session: neo4j.Session,
    *,
    source_instance_id: str,
    locator: str,
    model: ArchitectureModel,
    result: IngestionResult = IngestionResult.ACCEPTED,
    semantic_input_digest: str,
    discovery_scope_id: str,
    scope_definition_digest: str,
) -> SourceImportStats:
    """Transactionally MERGEs one source instance's facts and expires its stale ones, applying the
    I1 spec §5.4 replay decision against this source's own previously committed state. Public
    (unlike the transaction function it wraps) so callers - tests included - can drive one source's
    import directly without needing a full filesystem discovery run.
    """
    return session.execute_write(
        _import_source_tx,
        source_instance_id=source_instance_id,
        locator=locator,
        model=model,
        result=result,
        semantic_input_digest=semantic_input_digest,
        discovery_scope_id=discovery_scope_id,
        scope_definition_digest=scope_definition_digest,
    )


def _import_source_tx(
    tx: neo4j.ManagedTransaction,
    *,
    source_instance_id: str,
    locator: str,
    model: ArchitectureModel,
    result: IngestionResult,
    semantic_input_digest: str,
    discovery_scope_id: str,
    scope_definition_digest: str,
) -> SourceImportStats:
    for relation in model.relations:
        if relation.type not in KNOWN_RELATION_TYPES:
            raise ValueError(f"Unknown relation type: {relation.type}")

    committed = tx.run(_READ_SOURCE_STATE_QUERY, source_instance_id=source_instance_id).single()
    committed_semantic_input_digest = committed["semantic_input_digest"] if committed else None
    committed_scope_definition_digest = committed["scope_definition_digest"] if committed else None

    replay_decision = classify_replay_case(
        load_or_reevaluation_successful=True,
        committed_semantic_input_digest=committed_semantic_input_digest,
        new_semantic_input_digest=semantic_input_digest,
        committed_scope_definition_digest=committed_scope_definition_digest,
        new_scope_definition_digest=scope_definition_digest,
    )

    existing_node_ids = {
        record["id"]
        for record in tx.run(_OWNED_NODE_IDS_QUERY, source_instance_id=source_instance_id)
    }
    existing_relation_keys = {
        record["key"]
        for record in tx.run(_OWNED_RELATION_KEYS_QUERY, source_instance_id=source_instance_id)
    }

    new_node_ids = _model_node_ids(model)
    new_relation_keys = _model_relation_keys(model)
    if replay_decision.case is ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE:
        # I1 spec §5.4/§6: a scope change must not itself authorize expiring claims absent from the
        # new scope - only an explicit inventory transition/tombstone may. Treat everything this
        # source already owned as still "emitted" so nothing computes as dropped this run.
        new_node_ids = new_node_ids | existing_node_ids
        new_relation_keys = new_relation_keys | existing_relation_keys

    node_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners={node_id: {source_instance_id} for node_id in existing_node_ids},
        newly_emitted_claim_keys=new_node_ids,
    )
    relation_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners={key: {source_instance_id} for key in existing_relation_keys},
        newly_emitted_claim_keys=new_relation_keys,
    )

    nodes_written = _write_nodes(tx, source_instance_id, model)
    relations_written = _write_relations(tx, source_instance_id, model)

    if relation_plan.expired_claim_keys:
        tx.run(
            _EXPIRE_RELATIONS_QUERY,
            keys=list(relation_plan.expired_claim_keys),
            source_instance_id=source_instance_id,
        )
    if relation_plan.ownership_removed_claim_keys:
        tx.run(
            _REMOVE_RELATION_OWNERSHIP_QUERY,
            keys=list(relation_plan.ownership_removed_claim_keys),
            source_instance_id=source_instance_id,
        )
    if node_plan.expired_claim_keys:
        tx.run(_STRIP_STALE_EVIDENCE_QUERY, ids=list(node_plan.expired_claim_keys))
        tx.run(
            _EXPIRE_NODES_QUERY,
            ids=list(node_plan.expired_claim_keys),
            source_instance_id=source_instance_id,
        )
    if node_plan.ownership_removed_claim_keys:
        tx.run(
            _REMOVE_NODE_OWNERSHIP_QUERY,
            ids=list(node_plan.ownership_removed_claim_keys),
            source_instance_id=source_instance_id,
        )

    tx.run(
        _WRITE_SOURCE_STATE_QUERY,
        source_instance_id=source_instance_id,
        semantic_input_digest=semantic_input_digest,
        scope_definition_digest=scope_definition_digest,
        discovery_scope_id=discovery_scope_id,
    )

    is_no_op = node_plan.is_semantic_no_op and relation_plan.is_semantic_no_op
    graph_revision_advanced = replay_decision.graph_revision_advance_possible and not is_no_op
    if graph_revision_advanced:
        bump_revision(tx)

    return SourceImportStats(
        source_instance_id=source_instance_id,
        locator=locator,
        result=result,
        nodes_written=nodes_written,
        relations_written=relations_written,
        nodes_expired=len(node_plan.expired_claim_keys),
        relations_expired=len(relation_plan.expired_claim_keys),
        graph_revision_advanced=graph_revision_advanced,
    )


def _remove_source_tx(
    tx: neo4j.ManagedTransaction, *, source_instance_id: str
) -> SourceImportStats:
    existing_node_ids = {
        record["id"]
        for record in tx.run(_OWNED_NODE_IDS_QUERY, source_instance_id=source_instance_id)
    }
    existing_relation_keys = {
        record["key"]
        for record in tx.run(_OWNED_RELATION_KEYS_QUERY, source_instance_id=source_instance_id)
    }
    node_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners={node_id: {source_instance_id} for node_id in existing_node_ids},
        newly_emitted_claim_keys=frozenset(),
    )
    relation_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners={key: {source_instance_id} for key in existing_relation_keys},
        newly_emitted_claim_keys=frozenset(),
    )

    if relation_plan.expired_claim_keys:
        tx.run(
            _EXPIRE_RELATIONS_QUERY,
            keys=list(relation_plan.expired_claim_keys),
            source_instance_id=source_instance_id,
        )
    if relation_plan.ownership_removed_claim_keys:
        tx.run(
            _REMOVE_RELATION_OWNERSHIP_QUERY,
            keys=list(relation_plan.ownership_removed_claim_keys),
            source_instance_id=source_instance_id,
        )
    if node_plan.expired_claim_keys:
        tx.run(_STRIP_STALE_EVIDENCE_QUERY, ids=list(node_plan.expired_claim_keys))
        tx.run(
            _EXPIRE_NODES_QUERY,
            ids=list(node_plan.expired_claim_keys),
            source_instance_id=source_instance_id,
        )
    if node_plan.ownership_removed_claim_keys:
        tx.run(
            _REMOVE_NODE_OWNERSHIP_QUERY,
            ids=list(node_plan.ownership_removed_claim_keys),
            source_instance_id=source_instance_id,
        )
    tx.run(_DELETE_SOURCE_STATE_QUERY, source_instance_id=source_instance_id)
    bump_revision(tx)

    return SourceImportStats(
        source_instance_id=source_instance_id,
        locator="",
        result=IngestionResult.ACCEPTED,
        nodes_written=0,
        relations_written=0,
        nodes_expired=len(node_plan.expired_claim_keys),
        relations_expired=len(relation_plan.expired_claim_keys),
        graph_revision_advanced=True,
    )


def import_all_sources(
    driver: neo4j.Driver, *, database: str, source_config: FilesystemSourceConfig
) -> ImportRunStats:
    """Runs the I1 orchestrator for one configured filesystem source, then atomically commits the
    result: nothing is written to Neo4j unless the whole discovery run is COMPLETE (I1 spec §6 - a
    PARTIAL/FAILED run must preserve prior state, never a partial write).
    """
    run_result = run_filesystem_discovery(source_config)

    if not run_result.commit_eligible:
        return ImportRunStats(
            inventory_status=run_result.inventory_status,
            committed=False,
            per_source={},
            removed_source_instance_ids=(),
            diagnostics=run_result.diagnostics,
        )

    validate_canonical_model(run_result.merged_model)

    with open_session(driver, database=database) as session:
        ensure_schema(session)

        # Pre-merge every source's nodes first (separate transactions) so cross-source relation
        # targets always resolve regardless of processing order - unchanged in spirit from the
        # PoC-era pre-merge pass, now scoped per source instance instead of per service. Unlike the
        # PoC-era version, this pass does NOT bump the revision fence itself: MERGE here is
        # idempotent, and the real "did anything semantically change" decision (and the resulting
        # conditional bump) happens once, per source, in `_import_source_tx` below.
        for source_instance_id, source_outcome in run_result.source_outcomes.items():
            session.execute_write(_write_nodes, source_instance_id, source_outcome.outcome.model)

        per_source: dict[str, SourceImportStats] = {}
        for source_instance_id, source_outcome in run_result.source_outcomes.items():
            stats = import_source(
                session,
                source_instance_id=source_instance_id,
                locator=source_outcome.descriptor_locator,
                model=source_outcome.outcome.model,
                result=source_outcome.outcome.result,
                semantic_input_digest=source_outcome.outcome.semantic_input_digest,
                discovery_scope_id=run_result.discovery_scope_id,
                scope_definition_digest=run_result.scope_definition_digest,
            )
            per_source[source_instance_id] = stats

        removed_source_instance_ids: list[str] = []
        if run_result.inventory_status is InventoryStatus.COMPLETE:
            known_states = list(
                session.run(
                    _READ_SOURCE_STATES_FOR_SCOPE_QUERY,
                    discovery_scope_id=run_result.discovery_scope_id,
                )
            )
            for record in known_states:
                source_instance_id = record["source_instance_id"]
                if source_instance_id in run_result.source_outcomes:
                    continue
                decision = authorize_source_removal(
                    tombstone_validation=None,
                    enumeration_status=run_result.inventory_status,
                    enumeration_discovery_scope_id=run_result.discovery_scope_id,
                    enumeration_scope_definition_digest=run_result.scope_definition_digest,
                    committed_discovery_scope_id=run_result.discovery_scope_id,
                    committed_scope_definition_digest=record["scope_definition_digest"],
                    source_absent_from_enumeration=True,
                )
                if decision.authorized:
                    session.execute_write(_remove_source_tx, source_instance_id=source_instance_id)
                    removed_source_instance_ids.append(source_instance_id)

        return ImportRunStats(
            inventory_status=run_result.inventory_status,
            committed=True,
            per_source=per_source,
            removed_source_instance_ids=tuple(removed_source_instance_ids),
            diagnostics=run_result.diagnostics,
        )
