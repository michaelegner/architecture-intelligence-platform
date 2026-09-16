from collections.abc import Sequence
from dataclasses import dataclass

import neo4j

from app.canonical.model import ArchitectureModel
from app.graph.repository import open_session
from app.graph.revision_fence import bump_revision
from app.graph.schema import ensure_schema
from app.ingestion.orchestrator import DiscoveryRunResult, run_filesystem_discovery
from app.sources.claim_reconciliation import plan_source_claim_reconciliation
from app.sources.inventory import InventoryStatus
from app.sources.inventory import inventory_event_id as compute_inventory_event_id
from app.sources.jcs import canonical_json_bytes
from app.sources.migration_mappings import SharedIdentityMappingIndex
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionDiagnostic,
    IngestionResult,
)
from app.sources.removal_authority import authorize_source_removal
from app.sources.replay import ReplayCase, classify_replay_case
from app.sources.tombstones import (
    Tombstone,
    TombstoneValidation,
    validate_tombstone_against_committed_inventory,
)
from app.validation.canonical_validation import validate_canonical_model


class _NotSupplied:
    """A dedicated sentinel type, not a string constant, for the `expected_prior_inventory_revision`
    default below - I2 Draft 0.2 §3 prerequisite slice, item 4. Distinguishes "caller supplied no
    expectation at all" (every existing caller - preserves today's behavior exactly, no predecessor
    check performed) from a legitimate explicit expectation of `None` (caller expects no prior
    committed inventory to exist yet). A plain `None` default could not make that distinction, and a
    string sentinel compared by identity (`is not`) would be fragile - string identity is a CPython
    interning implementation detail, not a language guarantee (a real finding from PR review).
    """

    __slots__ = ()

    def __repr__(self) -> str:
        return "<not supplied>"


_NOT_SUPPLIED = _NotSupplied()


class StalePredecessorError(RuntimeError):
    """Raised inside `_import_all_sources_tx` when a caller-supplied expected predecessor
    inventory revision does not match what is actually committed for the scope - I2 Draft 0.2 §3
    prerequisite slice, item 4. Raising aborts the whole transaction before any write, so prior
    committed state is left untouched; `import_discovery_run` catches this and reports the run as
    not committed."""


NODE_LABELS = {
    "services": "Service",
    "operations": "Operation",
    "queues": "Queue",
    "messages": "Message",
    "schemas": "Schema",
    "provenance": "Evidence",
}

# I2 Draft 0.2 §3 item 6 / §7: internal-only infrastructure labels, deliberately NOT in
# `NODE_LABELS` above - that mapping is keyed by `ArchitectureModel` field name and assumes
# `model_dump(exclude={"id"})` yields Neo4j-storable primitives, which is not true for an entity's
# nested `ports` nor for contributions/claims whose `id` is a computed property rather than a field.
# `_write_infrastructure_nodes` handles them explicitly, using the same MERGE template.
INFRASTRUCTURE_ENTITY_LABEL = "InfrastructureEntity"
INFRASTRUCTURE_CONTRIBUTION_LABEL = "InfrastructureContribution"
INFRASTRUCTURE_CLAIM_LABEL = "InfrastructureClaim"

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
        # I2 Draft 0.2 §3 item 6: infrastructure facts go through the *same* ownership and
        # reconciliation path as every other canonical fact - including them here is what makes
        # `plan_source_claim_reconciliation`'s claim-key diff, `_EXPIRE_NODES_QUERY`'s
        # last-owner-wins deletion, and `_REMOVE_NODE_OWNERSHIP_QUERY`'s shared-ownership retirement
        # apply to them unchanged.
        *(e.id for e in model.infrastructure_entities),
        *(c.id for c in model.infrastructure_contributions),
        *(c.id for c in model.infrastructure_claims),
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

# I2 Draft 0.2 §3 prerequisite slice, items 3/4/5: one persisted "current committed inventory" node
# per discovery scope - sibling to `SourceState` above, which tracks per-*source* replay state.
# This tracks per-*scope* inventory-revision/capture/event-id/audit-chain state, feeding the
# transactional predecessor comparison and real (non-self-referential) values into
# `authorize_source_removal`/`validate_tombstone_against_committed_inventory`.
#
# This is a MERGE, not a plain MATCH, even though it is only ever used as a read: under Neo4j's
# default read-committed isolation, a plain MATCH takes no lock, so two concurrent transactions for
# the same scope could both read the same pre-image, both pass their own predecessor check, and
# both proceed to write - a real TOCTOU race found in PR review. MERGE acquires an exclusive lock
# on the matched-or-created node for the rest of the transaction, so a second concurrent
# transaction for the same scope blocks here until the first commits or rolls back, and then
# correctly observes the first transaction's real, committed result rather than a stale snapshot.
# A freshly created node's fields are all null, which this module already treats identically to "no
# prior committed inventory" below.
_READ_CURRENT_INVENTORY_QUERY = (
    "MERGE (i:CurrentInventory {discovery_scope_id: $discovery_scope_id}) "
    "RETURN i.inventory_revision AS inventory_revision, "
    "i.inventory_capture_id AS inventory_capture_id, "
    "i.inventory_event_id AS inventory_event_id, "
    "i.scope_definition_digest AS scope_definition_digest, "
    "i.discovery_scope_id AS discovery_scope_id"
)
_WRITE_CURRENT_INVENTORY_QUERY = (
    "MERGE (i:CurrentInventory {discovery_scope_id: $discovery_scope_id}) "
    "SET i.inventory_revision = $inventory_revision, "
    "i.inventory_capture_id = $inventory_capture_id, "
    "i.inventory_event_id = $inventory_event_id, "
    "i.scope_definition_digest = $scope_definition_digest"
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
    return count + _write_infrastructure_nodes(tx, source_instance_id, model)


def _infrastructure_entity_props(entity) -> dict:
    """I2 Draft 0.2 §7.1 delegates "persistence encoding" to the implementation. Everything except
    `ports` is already a Neo4j-storable primitive; `ports` is the Canonical Model's only nested
    object, and Neo4j properties cannot hold nested maps - so each port is stored as one RFC 8785
    canonical-JSON string, reusing `app.sources.jcs` rather than inventing a second canonicalization.
    The list stays in the entity's own §7.1 sorted order, so the stored value is deterministic and
    the before/after property snapshot that drives the revision fence stays meaningful.
    """
    props = entity.model_dump(exclude={"id", "ports"})
    props["ports"] = [
        canonical_json_bytes(port.model_dump()).decode("utf-8") for port in entity.ports
    ]
    return props


def _write_infrastructure_nodes(
    tx: neo4j.ManagedTransaction, source_instance_id: str, model: ArchitectureModel
) -> int:
    """I2 Draft 0.2 §3 item 6: infrastructure entities, contributions, and claims are written
    through the same MERGE-with-`owner_source_ids` template as every other canonical node, so they
    inherit the identical ownership, shared-ownership, reconciliation, and expiry semantics without
    a second mechanism (§12: "no second reconciliation engine is permitted").

    Contributions and claims are nodes rather than graph relationships on purpose: `WORKLOAD_EXISTS`
    is a first-class *unary* claim, and §7.2 forbids inventing "a sentinel entity or self-edge to
    force it through a binary-relation representation" - modelling all four claim kinds uniformly as
    owned claim nodes honors that, and keeps these internal-only facts out of every existing
    untyped relationship traversal (§9: they "MUST NOT leak through generic serialization, existing
    dependency answers, or a graph tool").
    """
    count = 0
    entity_query = _MERGE_NODE_TEMPLATE.format(label=INFRASTRUCTURE_ENTITY_LABEL)
    for entity in model.infrastructure_entities:
        tx.run(
            entity_query,
            id=entity.id,
            props=_infrastructure_entity_props(entity),
            source_instance_id=source_instance_id,
        )
        count += 1

    contribution_query = _MERGE_NODE_TEMPLATE.format(label=INFRASTRUCTURE_CONTRIBUTION_LABEL)
    for contribution in model.infrastructure_contributions:
        tx.run(
            contribution_query,
            id=contribution.id,
            props=contribution.model_dump(),
            source_instance_id=source_instance_id,
        )
        count += 1

    claim_query = _MERGE_NODE_TEMPLATE.format(label=INFRASTRUCTURE_CLAIM_LABEL)
    for claim in model.infrastructure_claims:
        tx.run(
            claim_query,
            id=claim.id,
            props=claim.model_dump(),
            source_instance_id=source_instance_id,
        )
        count += 1
    return count


_SNAPSHOT_NODE_PROPS_QUERY = (
    "UNWIND $ids AS nid MATCH (n {id: nid}) RETURN n.id AS id, properties(n) AS props"
)
_SNAPSHOT_RELATION_PROPS_QUERY = (
    "UNWIND $keys AS rkey MATCH ()-[r {key: rkey}]->() RETURN r.key AS key, properties(r) AS props"
)


def _snapshot_node_props(tx: neo4j.ManagedTransaction, node_ids: set[str]) -> dict[str, dict]:
    if not node_ids:
        return {}
    return {
        record["id"]: dict(record["props"])
        for record in tx.run(_SNAPSHOT_NODE_PROPS_QUERY, ids=list(node_ids))
    }


def _snapshot_relation_props(
    tx: neo4j.ManagedTransaction, relation_keys: set[str]
) -> dict[str, dict]:
    if not relation_keys:
        return {}
    return {
        record["key"]: dict(record["props"])
        for record in tx.run(_SNAPSHOT_RELATION_PROPS_QUERY, keys=list(relation_keys))
    }


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
    committed_nodes_before: dict[str, dict] | None = None,
    committed_relations_before: dict[str, dict] | None = None,
) -> SourceImportStats:
    """`committed_nodes_before`/`committed_relations_before`, when given, must be a snapshot of
    every node/relation this call could touch, taken before ANY write in this run (including
    another source's pre-merge) - see `_import_all_sources_tx`, which is the only caller that needs
    this: `import_all_sources` pre-merges every source's nodes before any source's own
    `_import_source_tx` runs (so cross-source relation targets always resolve), which would
    otherwise already have applied this exact source's own new property values by the time this
    function queried "before" state itself, making a real property-only change invisible to the
    no-op check below (a real bug found in PR review). `None` (the default, and always the case for
    a direct standalone `import_source()` call, which has no pre-merge step to race against) means
    "query the current graph state now" - correct there, since nothing else has written yet.
    """
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

    # I1 §5.4/§14: a semantic no-op means the canonical snapshot doesn't change, not merely that
    # semantic_input_digest changed - an adapter's normalized projection can hash raw input the
    # canonical model never surfaces at all (e.g. OpenAPI's info.description, unmapped to any
    # canonical field). Snapshotting each emitted node/relation's properties immediately before and
    # after this source's own write isolates exactly what THIS write actually changed, independent
    # of what varied in the raw input bytes. Combined with node_plan/relation_plan's claim-KEY-set
    # diff (added/removed/expired), this is the complete no-op signal - the claim-set diff alone
    # misses a property-only change on a retained claim, and semantic_input_digest alone
    # over-triggers on a canonically-inert input change.
    if committed_nodes_before is not None:
        nodes_before = {k: v for k, v in committed_nodes_before.items() if k in new_node_ids}
    else:
        nodes_before = _snapshot_node_props(tx, new_node_ids)
    if committed_relations_before is not None:
        relations_before = {
            k: v for k, v in committed_relations_before.items() if k in new_relation_keys
        }
    else:
        relations_before = _snapshot_relation_props(tx, new_relation_keys)

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

    nodes_after = _snapshot_node_props(tx, new_node_ids)
    relations_after = _snapshot_relation_props(tx, new_relation_keys)
    content_changed = nodes_before != nodes_after or relations_before != relations_after

    # graph_revision_advance_possible=False (FAILED_LOAD_PRESERVE_PRIOR, or REPLAY_NO_OP whose
    # byte-identical semantic_input_digest already proves nothing could have changed) is a
    # necessary condition: skip it and never advance, without paying for the snapshot diff at all.
    # Otherwise, is_no_op is the real decision - both the claim-KEY-set diff (an add/remove/
    # expire/ownership change, e.g. node_plan.is_semantic_no_op is False) AND the before/after
    # content diff above (a property-only change on a claim this source retains) count as a real
    # change; neither alone is sufficient (the claim-set diff alone misses property-only edits, and
    # semantic_input_digest alone over-triggers on an input change the canonical model never
    # surfaces, e.g. OpenAPI's info.description).
    is_no_op = (
        node_plan.is_semantic_no_op and relation_plan.is_semantic_no_op and not content_changed
    )
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


def _import_all_sources_tx(
    tx: neo4j.ManagedTransaction,
    *,
    run_result: DiscoveryRunResult,
    expected_prior_inventory_revision: str | None | _NotSupplied = _NOT_SUPPLIED,
) -> tuple[dict[str, SourceImportStats], tuple[str, ...], tuple[IngestionDiagnostic, ...]]:
    """Pre-merge, per-source reconciliation, and removal for one whole discovery run, all against
    the same transaction - a run either commits in full or (on any error, including a driver/
    infrastructure failure partway through) rolls back in full. Previously these were separate
    `execute_write` calls per source: a failure partway through the loop left earlier sources'
    writes committed even though the run as a whole never reached `ImportRunStats(committed=True)`
    - contradicting this module's own "nothing is written unless the whole run is COMPLETE"
    contract (I1 spec §6), a real bug found in PR review.

    I2 Draft 0.2 §3 prerequisite slice, items 3/4/5: also reads and (on success) rewrites the
    scope's `CurrentInventory` state in this same transaction. `expected_prior_inventory_revision`
    defaults to `_NOT_SUPPLIED` (skip the check entirely - every existing caller's behavior is
    unchanged); a caller that opts in (including with an explicit `None`, meaning "expect no prior
    committed inventory") gets a real transactional predecessor comparison against what is actually
    persisted, raising `StalePredecessorError` (aborting the whole transaction, writing nothing) on
    a mismatch.
    """
    # A MERGE, not a MATCH - see _READ_CURRENT_INVENTORY_QUERY's own comment: this acquires an
    # exclusive per-scope lock for the rest of this transaction, so `.single()` always returns
    # exactly one row. For a freshly created node, `discovery_scope_id` is set immediately (it's
    # part of the MERGE's own matching pattern), but `inventory_revision`/`scope_definition_digest`/
    # `inventory_event_id` remain null - there is no real committed inventory yet. Treat
    # `inventory_revision is None` as the single source of truth for "nothing committed yet", and
    # normalize `discovery_scope_id` to `None` alongside it wherever "committed state" is passed
    # onward - passing the MERGE-created `discovery_scope_id` on its own would present a partially
    # populated committed state (id set, revision/digest null) to
    # `validate_tombstone_against_committed_inventory`, which raises
    # `InconsistentCommittedInventoryStateError` on exactly that inconsistency (a real bug found in
    # PR review: a tombstone submitted on a brand-new scope's very first run crashed instead of
    # being classified `NO_COMMITTED_INVENTORY`).
    persisted_inventory = tx.run(
        _READ_CURRENT_INVENTORY_QUERY, discovery_scope_id=run_result.discovery_scope_id
    ).single()
    has_committed_inventory = persisted_inventory["inventory_revision"] is not None
    committed_discovery_scope_id = (
        persisted_inventory["discovery_scope_id"] if has_committed_inventory else None
    )

    if expected_prior_inventory_revision is not _NOT_SUPPLIED:
        actual_committed_revision = persisted_inventory["inventory_revision"]
        if actual_committed_revision != expected_prior_inventory_revision:
            raise StalePredecessorError(
                f"expected prior inventory revision {expected_prior_inventory_revision!r} for "
                f"scope {run_result.discovery_scope_id!r}, but the currently committed revision "
                f"is {actual_committed_revision!r}"
            )

    if run_result.inventory_snapshot is None:
        raise ValueError(
            "a commit-eligible discovery run must carry a real inventory_snapshot "
            f"(discovery_scope_id={run_result.discovery_scope_id!r})"
        )

    tombstone_validations: dict[str, TombstoneValidation] = {}
    tombstone_diagnostics: list[IngestionDiagnostic] = []
    for tombstone in run_result.inventory_snapshot.tombstones:
        validation = validate_tombstone_against_committed_inventory(
            tombstone=tombstone,
            committed_discovery_scope_id=committed_discovery_scope_id,
            committed_scope_definition_digest=persisted_inventory["scope_definition_digest"],
            committed_inventory_revision=persisted_inventory["inventory_revision"],
        )
        tombstone_validations[tombstone.target_source_instance_id] = validation
        # A rejected tombstone must not silently no-op from the caller's perspective (no removal,
        # no explanation) - a real finding from PR review.
        if not validation.accepted and validation.diagnostic is not None:
            tombstone_diagnostics.append(validation.diagnostic)

    # Snapshot every source's own emitted node/relation properties BEFORE the pre-merge pass below
    # touches anything - the pre-merge writes every source's nodes first (see its own comment), so
    # by the time a given source's own `_import_source_tx` ran, its own PRE-MERGE write had already
    # applied its new property values, making its no-op check's "before" snapshot indistinguishable
    # from "after" even for a genuine property-only change (a real bug found in PR review: this
    # made a title-only reimport through the real `import_all_sources` path silently skip the
    # revision fence). Captured once, for the union of every source's own node ids/relation keys.
    all_node_ids: set[str] = set()
    all_relation_keys: set[str] = set()
    for source_outcome in run_result.source_outcomes.values():
        all_node_ids |= _model_node_ids(source_outcome.outcome.model)
        all_relation_keys |= _model_relation_keys(source_outcome.outcome.model)
    committed_nodes_before = _snapshot_node_props(tx, all_node_ids)
    committed_relations_before = _snapshot_relation_props(tx, all_relation_keys)

    # Pre-merge every source's nodes first so cross-source relation targets always resolve
    # regardless of processing order - unchanged in spirit from the PoC-era pre-merge pass, now
    # scoped per source instance instead of per service. This pass does NOT bump the revision fence
    # itself: MERGE here is idempotent, and the real "did anything semantically change" decision
    # (and the resulting conditional bump) happens once, per source, in `_import_source_tx` below.
    for source_instance_id, source_outcome in run_result.source_outcomes.items():
        _write_nodes(tx, source_instance_id, source_outcome.outcome.model)

    per_source: dict[str, SourceImportStats] = {}
    for source_instance_id, source_outcome in run_result.source_outcomes.items():
        per_source[source_instance_id] = _import_source_tx(
            tx,
            source_instance_id=source_instance_id,
            locator=source_outcome.descriptor_locator,
            model=source_outcome.outcome.model,
            result=source_outcome.outcome.result,
            semantic_input_digest=source_outcome.outcome.semantic_input_digest,
            discovery_scope_id=run_result.discovery_scope_id,
            scope_definition_digest=run_result.scope_definition_digest,
            committed_nodes_before=committed_nodes_before,
            committed_relations_before=committed_relations_before,
        )

    removed_source_instance_ids: list[str] = []
    if run_result.inventory_status is InventoryStatus.COMPLETE:
        known_states = list(
            tx.run(
                _READ_SOURCE_STATES_FOR_SCOPE_QUERY,
                discovery_scope_id=run_result.discovery_scope_id,
            )
        )
        for record in known_states:
            source_instance_id = record["source_instance_id"]
            if source_instance_id in run_result.source_outcomes:
                continue
            # `known_states` can only be non-empty if a prior COMPLETE run already persisted both
            # `SourceState` and `CurrentInventory` for this scope together (see the write below),
            # so `has_committed_inventory` (hence `committed_discovery_scope_id`) is guaranteed set
            # whenever this loop body runs.
            decision = authorize_source_removal(
                tombstone_validation=tombstone_validations.get(source_instance_id),
                enumeration_status=run_result.inventory_status,
                enumeration_discovery_scope_id=run_result.discovery_scope_id,
                enumeration_scope_definition_digest=run_result.scope_definition_digest,
                committed_discovery_scope_id=committed_discovery_scope_id,
                committed_scope_definition_digest=record["scope_definition_digest"],
                source_absent_from_enumeration=True,
            )
            if decision.authorized:
                _remove_source_tx(tx, source_instance_id=source_instance_id)
                removed_source_instance_ids.append(source_instance_id)

    new_event_id = compute_inventory_event_id(
        previous_event_id=persisted_inventory["inventory_event_id"],
        inventory_capture_id=run_result.inventory_snapshot.inventory_capture_id,
    )
    tx.run(
        _WRITE_CURRENT_INVENTORY_QUERY,
        discovery_scope_id=run_result.discovery_scope_id,
        inventory_revision=run_result.inventory_snapshot.inventory_revision,
        inventory_capture_id=run_result.inventory_snapshot.inventory_capture_id,
        inventory_event_id=new_event_id,
        scope_definition_digest=run_result.scope_definition_digest,
    )

    return per_source, tuple(removed_source_instance_ids), tuple(tombstone_diagnostics)


def import_discovery_run(
    driver: neo4j.Driver,
    *,
    database: str,
    run_result: DiscoveryRunResult,
    expected_prior_inventory_revision: str | None | _NotSupplied = _NOT_SUPPLIED,
) -> ImportRunStats:
    """I2 Draft 0.2 §3 prerequisite slice, items 2/4: the source-neutral commit entry point - takes
    an already-computed `DiscoveryRunResult` (from `run_discovery` or any source-neutral discovery
    path) rather than constructing discovery itself, and does not branch on source kind.
    `import_all_sources` below is now a thin compatibility wrapper over this function for the
    filesystem source kind.

    Nothing is written to Neo4j unless the whole discovery run is COMPLETE (I1 spec §6 - a
    PARTIAL/FAILED run must preserve prior state, never a partial write), and pre-merge/
    reconciliation/removal for every source in the run share one transaction (see
    `_import_all_sources_tx`), so a failure partway through the run - including a stale
    `expected_prior_inventory_revision` - leaves nothing committed.
    """
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
        try:
            per_source, removed_source_instance_ids, tombstone_diagnostics = session.execute_write(
                _import_all_sources_tx,
                run_result=run_result,
                expected_prior_inventory_revision=expected_prior_inventory_revision,
            )
        except StalePredecessorError as exc:
            return ImportRunStats(
                inventory_status=run_result.inventory_status,
                committed=False,
                per_source={},
                removed_source_instance_ids=(),
                diagnostics=(
                    *run_result.diagnostics,
                    IngestionDiagnostic(
                        code=DiagnosticCode.STALE_INVENTORY_PREDECESSOR,
                        message=str(exc),
                    ),
                ),
            )

        return ImportRunStats(
            inventory_status=run_result.inventory_status,
            committed=True,
            per_source=per_source,
            removed_source_instance_ids=removed_source_instance_ids,
            diagnostics=(*run_result.diagnostics, *tombstone_diagnostics),
        )


def import_all_sources(
    driver: neo4j.Driver,
    *,
    database: str,
    source_config: FilesystemSourceConfig,
    migration_mappings: SharedIdentityMappingIndex | None = None,
    tombstones: Sequence[Tombstone] = (),
    expected_prior_inventory_revision: str | None | _NotSupplied = _NOT_SUPPLIED,
) -> ImportRunStats:
    """Thin compatibility wrapper over `run_filesystem_discovery` + `import_discovery_run` for the
    filesystem source kind - every existing caller/test keeps working unchanged."""
    run_result = run_filesystem_discovery(
        source_config, migration_mappings=migration_mappings, tombstones=tombstones
    )
    return import_discovery_run(
        driver,
        database=database,
        run_result=run_result,
        expected_prior_inventory_revision=expected_prior_inventory_revision,
    )
