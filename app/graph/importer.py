from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace

import neo4j

from app.canonical.model import ArchitectureModel
from app.canonical.pubsub import (
    PUBSUB_DECLARATION_LABEL,
    SUBSCRIPTION_DEAD_LETTER_CONFIGURATION_LABEL,
)
from app.graph.repository import open_session
from app.graph.revision_fence import bump_revision
from app.graph.schema import ensure_schema
from app.ingestion.orchestrator import (
    DiscoveryRunResult,
    SourceRunOutcome,
    run_filesystem_discovery,
    run_kubernetes_discovery,
)
from app.sources.claim_reconciliation import (
    SourceClaimReconciliationPlan,
    plan_source_claim_reconciliation,
)
from app.sources.encoding import length_delimited, sha256_hex
from app.sources.inventory import InventoryStatus
from app.sources.inventory import inventory_event_id as compute_inventory_event_id
from app.sources.jcs import canonical_json_bytes
from app.sources.migration_mappings import SharedIdentityMappingIndex
from app.sources.model import (
    NOT_SUPPLIED,
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionDiagnostic,
    IngestionResult,
    KubernetesSourceConfig,
    NotSupplied,
)
from app.sources.removal_authority import authorize_source_removal
from app.sources.replay import ReplayCase, classify_replay_case
from app.sources.tombstones import (
    Tombstone,
    TombstoneValidation,
    validate_tombstone_against_committed_inventory,
)

# NotSupplied/NOT_SUPPLIED were relocated to app.sources.model in I2 Draft 0.2 slice 2b-ii - see
# that module's own docstring for why (app.sources.registry/app.ingestion.orchestrator, both lower
# layers this module already imports from, also need the type for their own
# `expected_prior_inventory_revision` fields).


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
    # v0.5.0 I4 spec §6.2/§11: persisted from the same slice (2b) that bumps snapshot
    # canonicalization to v3 with dedicated Topic/Subscription node queries.
    "topics": "Topic",
    "subscriptions": "Subscription",
}

# I2 Draft 0.2 §3 item 6 / §7: internal-only infrastructure labels, deliberately NOT in
# `NODE_LABELS` above - that mapping is keyed by `ArchitectureModel` field name and assumes
# `model_dump(exclude={"id"})` yields Neo4j-storable primitives, which is not true for an entity's
# nested `ports` nor for contributions/claims whose `id` is a computed property rather than a field.
# `_write_infrastructure_nodes` handles them explicitly, using the same MERGE template.
INFRASTRUCTURE_ENTITY_LABEL = "InfrastructureEntity"
INFRASTRUCTURE_CONTRIBUTION_LABEL = "InfrastructureContribution"
INFRASTRUCTURE_CLAIM_LABEL = "InfrastructureClaim"
# I2 Draft 0.2 §7.2: "Claim contributions use the same source ownership, evidence-mode retention,
# deterministic evidence union... as entity contributions." A claim node is shared by every source
# asserting the same (kind, subject, object) - §7.2's own identity rule - so its own `evidence_refs`
# can never be written directly from any one source's model (a real bug found in PR review, twice:
# a plain overwrite made the stored evidence depend on which source wrote last, and a reduce-based
# union could accumulate refs forever - neither let a RETAINED source correctly REPLACE its own
# evidence on reimport, since nothing ever ran for a claim whose ownership hadn't changed). Instead,
# each source's own view of a claim is persisted as its own `InfrastructureClaimContribution` row -
# id-scoped per (claim, source) exactly like `InfrastructureContribution`, so a reimport correctly
# *overwrites* (never accumulates) that source's own evidence - and the claim's own `evidence_refs`
# is a derived, recomputed-from-scratch union of whatever contribution rows currently exist,
# computed by `_recompute_infrastructure_claim_evidence` after every source's own write+reconcile
# step. This is the same "one shared fact, several sources' own evidence" shape `InfrastructureEntity`
# /`InfrastructureContribution` already solve correctly; a claim needed its own contribution layer
# because §7.2 (unlike §7.1) puts `evidence_refs` on the shared claim object itself, with no
# adapter-facing per-source contribution type of its own.
INFRASTRUCTURE_CLAIM_CONTRIBUTION_LABEL = "InfrastructureClaimContribution"

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
    # v0.5.0 I4 spec §6.3 (RECEIVES_FROM and CARRIES are reused for Subscription/Topic endpoints).
    "PUBLISHES_TO",
    "SUBSCRIPTION_OF",
}


def relation_key(relation) -> str:
    return f"{relation.type}:{relation.source_id}:{relation.target_id}"


def _model_node_ids(model: ArchitectureModel, *, source_instance_id: str) -> set[str]:
    return {
        *(s.id for s in model.services),
        *(o.id for o in model.operations),
        *(q.id for q in model.queues),
        *(m.id for m in model.messages),
        *(sc.id for sc in model.schemas),
        *(p.id for p in model.provenance),
        # v0.5.0 I4: Topic/Subscription plus their internal source-owned carriers, through the same
        # ownership/reconciliation path (§11: no parallel lifecycle engine).
        *(t.id for t in model.topics),
        *(s.id for s in model.subscriptions),
        *(d.id for d in model.pubsub_declarations),
        *(c.id for c in model.subscription_dead_letter_configurations),
        # I2 Draft 0.2 §3 item 6: infrastructure facts go through the *same* ownership and
        # reconciliation path as every other canonical fact - including them here is what makes
        # `plan_source_claim_reconciliation`'s claim-key diff, `_EXPIRE_NODES_QUERY`'s
        # last-owner-wins deletion, and `_EXPIRE_NODES_QUERY`'s shared-ownership retirement
        # apply to them unchanged.
        *(e.id for e in model.infrastructure_entities),
        *(c.id for c in model.infrastructure_contributions),
        *(c.id for c in model.infrastructure_claims),
        # The per-source claim-contribution row (see _write_infrastructure_nodes) is its own owned
        # node, keyed per (claim, THIS source), so it must participate in ownership reconciliation
        # the same way `InfrastructureContribution` already does.
        *(
            _infrastructure_claim_contribution_id(claim.id, source_instance_id)
            for claim in model.infrastructure_claims
        ),
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

# Every claim this source owns, with its full committed owner set: a claim this source stops
# emitting expires only if no other source will own it (I1 §6), so the reconciliation plan needs the
# real owners, not only this source.
_OWNED_NODE_IDS_QUERY = (
    "MATCH (n) WHERE $source_instance_id IN coalesce(n.owner_source_ids, []) "
    "RETURN n.id AS id, n.owner_source_ids AS owners"
)
_OWNED_RELATION_KEYS_QUERY = (
    "MATCH ()-[r]->() WHERE $source_instance_id IN coalesce(r.owner_source_ids, []) "
    "RETURN r.key AS key, r.owner_source_ids AS owners"
)

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
class ClaimEffectSet:
    """One category of a source's canonical reconciliation effects (I1 §10 "canonical planned/
    committed effects"), by stable claim identity. Public canonical facts are listed by id or
    relation key. Internal-only facts (Kubernetes infrastructure entities, contributions and claims,
    Pub/Sub carriers, and Evidence) are only counted: I2 §9 forbids exposing them."""

    public_node_ids: tuple[str, ...] = ()
    relation_keys: tuple[str, ...] = ()
    internal_count: int = 0

    @property
    def is_empty(self) -> bool:
        return not (self.public_node_ids or self.relation_keys or self.internal_count)


@dataclass(frozen=True)
class SourceClaimEffects:
    """What one source's reconciliation changed, from its claim-reconciliation plans and the
    before/after property snapshots that also decide `graph_revision_advanced`. An unchanged replay
    has empty effects, although the importer still executes idempotent MERGEs."""

    added: ClaimEffectSet = ClaimEffectSet()
    changed: ClaimEffectSet = ClaimEffectSet()
    expired: ClaimEffectSet = ClaimEffectSet()
    ownership_removed: ClaimEffectSet = ClaimEffectSet()

    @property
    def is_empty(self) -> bool:
        return all(
            category.is_empty
            for category in (self.added, self.changed, self.expired, self.ownership_removed)
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
    # `nodes_written`/`relations_written` count MERGE operations, which an unchanged replay also
    # executes; `effects` is the canonical effect set (None only where no reconciliation ran).
    effects: SourceClaimEffects | None = None


@dataclass(frozen=True)
class EmittedCounts:
    """What one source's adapter mapped (I1 §10 "emitted counts"), before any reconciliation."""

    services: int
    operations: int
    schemas: int
    messages: int
    queues: int
    topics: int
    subscriptions: int
    relations: int
    infrastructure_entities: int
    infrastructure_claims: int

    @classmethod
    def of(cls, model: ArchitectureModel) -> "EmittedCounts":
        return cls(
            services=len(model.services),
            operations=len(model.operations),
            schemas=len(model.schemas),
            messages=len(model.messages),
            queues=len(model.queues),
            topics=len(model.topics),
            subscriptions=len(model.subscriptions),
            relations=len(model.relations),
            infrastructure_entities=len(model.infrastructure_entities),
            infrastructure_claims=len(model.infrastructure_claims),
        )


@dataclass(frozen=True)
class SourceRunResult:
    """I1 spec §10: "Each source receives exactly one result" - one discovered source's own result
    and diagnostics for a discovery run, recorded whether or not the run committed (unlike
    `SourceImportStats`, which only exists for sources actually reconciled into the graph). v0.5.0
    I5 finding F2: a non-committing run previously dropped every per-source result."""

    source_instance_id: str
    locator: str
    result: IngestionResult
    diagnostics: tuple[IngestionDiagnostic, ...]
    # I1 §10's "dialects, identities, emitted counts": the claiming adapter (None when no adapter
    # claimed the source), the document's own declared dialect version, the adapter's semantic
    # input digest, the Service ids the source emits, and what the adapter mapped - recorded
    # whether or not the run commits.
    source_kind: str = ""
    adapter_identity: str | None = None
    mapping_rule_version: str | None = None
    dialect_version: str | None = None
    semantic_input_digest: str | None = None
    service_ids: tuple[str, ...] = ()
    emitted: EmittedCounts | None = None


@dataclass(frozen=True)
class TombstoneDecision:
    """I1 spec §10's report entry for one in-scope explicit tombstone evaluated by a committing run:
    whether it was accepted against the committed inventory, and the rejection reason if not."""

    target_source_instance_id: str
    tombstone_revision: str
    accepted: bool
    reason: str | None


@dataclass(frozen=True)
class ImportRunStats:
    inventory_status: InventoryStatus
    committed: bool
    per_source: dict[str, SourceImportStats]
    removed_source_instance_ids: tuple[str, ...]
    diagnostics: tuple[IngestionDiagnostic, ...]
    # v0.5.0 I5 finding F2 (I1 spec §10 import report) - defaulted so existing constructors keep
    # working. `source_results` holds every discovered source's own result on every return path,
    # committing or not; `inventory_revision` is the committed revision this run wrote (None when
    # the run did not commit).
    source_results: tuple[SourceRunResult, ...] = ()
    discovery_scope_id: str | None = None
    scope_definition_digest: str | None = None
    inventory_revision: str | None = None
    tombstone_decisions: tuple[TombstoneDecision, ...] = ()
    # The expirations each authorized removal committed, one per `removed_source_instance_ids`.
    removal_stats: tuple[SourceImportStats, ...] = ()


# The public canonical node labels (the `NODE_LABELS` entities, minus Evidence). Every other owned
# node is internal-only, and appears in a `ClaimEffectSet` only as a count.
_PUBLIC_NODE_LABELS = frozenset(label for label in NODE_LABELS.values() if label != "Evidence")
_PUBLIC_MODEL_FIELDS = tuple(
    field for field, label in NODE_LABELS.items() if label in _PUBLIC_NODE_LABELS
)

_NODE_LABELS_QUERY = "UNWIND $ids AS nid MATCH (n {id: nid}) RETURN n.id AS id, labels(n) AS labels"


def _public_node_ids(
    tx: neo4j.ManagedTransaction, node_ids: set[str], model: ArchitectureModel
) -> frozenset[str]:
    """The public canonical ids among `node_ids`: by the model's own fields for what this source
    emits, and by committed label for what it owned before (which may no longer be emitted)."""
    public = {entity.id for field in _PUBLIC_MODEL_FIELDS for entity in getattr(model, field)}
    if node_ids:
        public.update(
            record["id"]
            for record in tx.run(_NODE_LABELS_QUERY, ids=list(node_ids))
            if _PUBLIC_NODE_LABELS.intersection(record["labels"])
        )
    return frozenset(public & node_ids)


def _effect_set(
    node_ids: AbstractSet[str], relation_keys: AbstractSet[str], public: AbstractSet[str]
) -> ClaimEffectSet:
    return ClaimEffectSet(
        public_node_ids=tuple(sorted(node_ids & public)),
        relation_keys=tuple(sorted(relation_keys)),
        internal_count=len(node_ids - public),
    )


def _without_owners(props: dict | None) -> dict | None:
    if props is None:
        return None
    return {key: value for key, value in props.items() if key != "owner_source_ids"}


def _owners_after_run(
    committed_owners: AbstractSet[str],
    key: str,
    *,
    run_source_ids: AbstractSet[str],
    run_emitters: Mapping[str, AbstractSet[str]],
) -> set[str]:
    """Who owns a claim once the whole run has committed: its committed owners outside this run,
    plus the run's sources that still emit it. Independent of the order the run's sources are
    reconciled in, so a claim two sources of one run both stop emitting expires for both."""
    return {owner for owner in committed_owners if owner not in run_source_ids} | set(
        run_emitters.get(key, ())
    )


def _dropped_claim_owners(
    owned: Mapping[str, AbstractSet[str]],
    *,
    source_instance_id: str,
    run_source_ids: AbstractSet[str],
    run_emitters: Mapping[str, AbstractSet[str]],
) -> dict[str, set[str]]:
    """`committed_claim_owners` for `plan_source_claim_reconciliation`: this source plus every owner
    the claim will have after the run, so a dropped claim is `expired` only when nobody else will
    own it, and `ownership_removed` otherwise."""
    return {
        key: {source_instance_id}
        | _owners_after_run(owners, key, run_source_ids=run_source_ids, run_emitters=run_emitters)
        for key, owners in owned.items()
    }


def _expire_dropped_claims(
    tx: neo4j.ManagedTransaction,
    *,
    source_instance_id: str,
    node_plan: SourceClaimReconciliationPlan,
    relation_plan: SourceClaimReconciliationPlan,
) -> None:
    """Retire every claim this source dropped. Expired and ownership-removed claims share the same
    queries: each removes this source as an owner and deletes only what is left without one, and the
    relation query also strips this source's DECLARED evidence, which a shared relation must lose
    too. The plan's split decides only what the report says, never a different mutation."""
    dropped_relations = (
        relation_plan.expired_claim_keys | relation_plan.ownership_removed_claim_keys
    )
    if dropped_relations:
        tx.run(
            _EXPIRE_RELATIONS_QUERY,
            keys=sorted(dropped_relations),
            source_instance_id=source_instance_id,
        )
    if node_plan.expired_claim_keys:
        tx.run(_STRIP_STALE_EVIDENCE_QUERY, ids=sorted(node_plan.expired_claim_keys))
    dropped_nodes = node_plan.expired_claim_keys | node_plan.ownership_removed_claim_keys
    if dropped_nodes:
        tx.run(
            _EXPIRE_NODES_QUERY,
            ids=sorted(dropped_nodes),
            source_instance_id=source_instance_id,
        )


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
    count += _write_pubsub_carrier_nodes(tx, source_instance_id, model)
    return count + _write_infrastructure_nodes(tx, source_instance_id, model)


def _write_pubsub_carrier_nodes(
    tx: neo4j.ManagedTransaction, source_instance_id: str, model: ArchitectureModel
) -> int:
    """v0.5.0 I4 spec §10/§11: the internal source-owned carriers, deliberately outside
    `NODE_LABELS` (their `id` is a computed property, and they must stay out of the NL-query label
    allowlist and snapshot canonicalization), written with the same MERGE template as
    `_write_infrastructure_nodes`' contributions."""
    count = 0
    for label, carriers in (
        (PUBSUB_DECLARATION_LABEL, model.pubsub_declarations),
        (
            SUBSCRIPTION_DEAD_LETTER_CONFIGURATION_LABEL,
            model.subscription_dead_letter_configurations,
        ),
    ):
        query = _MERGE_NODE_TEMPLATE.format(label=label)
        for carrier in carriers:
            tx.run(
                query,
                id=carrier.id,
                props=carrier.model_dump(),
                source_instance_id=source_instance_id,
            )
            count += 1
    return count


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


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def _infrastructure_claim_contribution_id(claim_id: str, source_instance_id: str) -> str:
    """Not spec-named (§7.2 describes the per-source contribution *concept* in prose, not a schema
    - the same discipline as every other id formula this PR's own layer invents). Length-delimited
    like every other identity hash in this codebase; deliberately a different literal prefix from
    `InfrastructureClaim.id`'s own `urn:aip:infra-claim:` so `_recompute_infrastructure_claim_evidence`
    can distinguish "a claim id" from "a claim-contribution id" by a plain string prefix check,
    without needing a Neo4j label lookup.
    """
    key = length_delimited(_utf8(claim_id), _utf8(source_instance_id))
    return f"urn:aip:infra-claim-support:{sha256_hex(key)}"


_INFRASTRUCTURE_CLAIM_ID_PREFIX = "urn:aip:infra-claim:"

_READ_CLAIM_CONTRIBUTION_EVIDENCE_QUERY = (
    f"MATCH (c:{INFRASTRUCTURE_CLAIM_CONTRIBUTION_LABEL} {{claim_id: $claim_id}}) "
    "RETURN c.evidence_refs AS evidence_refs"
)
_SET_CLAIM_EVIDENCE_REFS_QUERY = (
    f"MATCH (n:{INFRASTRUCTURE_CLAIM_LABEL} {{id: $claim_id}}) SET n.evidence_refs = $evidence_refs"
)


def _recompute_affected_infrastructure_claims(
    tx: neo4j.ManagedTransaction,
    node_plan,
    *,
    currently_emitted_claim_ids: frozenset[str] = frozenset(),
) -> None:
    """Recomputes every infrastructure claim a source's own reconciliation step could have
    affected: every claim it currently emits (`currently_emitted_claim_ids` - empty for whole-source
    removal, which emits nothing), plus every claim it just stopped emitting (found by filtering
    `node_plan`'s expired/ownership-removed id set for the claim-id prefix, since that set mixes
    every node kind together). Must run AFTER this source's own nodes are written/reconciled, so the
    read-your-own-writes view each recompute sees already reflects them.
    """
    affected_claim_ids = currently_emitted_claim_ids | {
        node_id
        for node_id in node_plan.expired_claim_keys | node_plan.ownership_removed_claim_keys
        if node_id.startswith(_INFRASTRUCTURE_CLAIM_ID_PREFIX)
    }
    for claim_id in sorted(affected_claim_ids):
        _recompute_infrastructure_claim_evidence(tx, claim_id)


def _recompute_infrastructure_claim_evidence(tx: neo4j.ManagedTransaction, claim_id: str) -> None:
    """A claim's `evidence_refs` is never written directly from any one source's model - it is
    recomputed, from scratch, as the sorted union of every *currently live*
    `InfrastructureClaimContribution` row for this claim id. Correct regardless of why this claim
    was touched: a brand-new claim, a retained claim whose owning source replaced its own evidence
    (the specific bug this replaces two prior write-time-union attempts to fix), or a claim losing
    one of several owners (a real co-ownership bug found in PR review) - all three reduce to "read
    what's currently there and set the union," with no incremental accumulate/strip logic to get
    subtly wrong. A no-op if the claim node was already deleted (its last contribution just expired):
    `MATCH` finds no rows to `SET`.
    """
    refs: set[str] = set()
    for record in tx.run(_READ_CLAIM_CONTRIBUTION_EVIDENCE_QUERY, claim_id=claim_id):
        refs.update(record["evidence_refs"] or [])
    tx.run(_SET_CLAIM_EVIDENCE_REFS_QUERY, claim_id=claim_id, evidence_refs=sorted(refs))


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

    # I2 Draft 0.2 §7.2: "Evidence mode is retained per contribution... merging declarations and
    # captures never turns all support into observation" - the same requirement §7.1 states for
    # entity contributions, applied to claim contributions too. `InfrastructureClaim` itself (§7.2's
    # frozen adapter-facing schema) carries no `evidence_mode` field - by design, since that's a
    # per-CONTRIBUTION property, not a property of the shared claim - so it is looked up here from
    # this SAME model's own entity contribution for the claim's subject, which does carry it. This
    # holds because a claim and its subject's own contribution are always emitted together by the
    # same adapter for the same source in the same model, and §4.1 guarantees one source has exactly
    # one immutable evidence mode - so the subject's contribution is authoritative for this claim's
    # contribution too. `None` only if the model is malformed (a claim whose subject has no
    # contribution from this same source at all).
    contribution_by_entity_id = {c.entity_id: c for c in model.infrastructure_contributions}

    # The claim node itself carries every field EXCEPT evidence_refs, which is never written here -
    # see `_recompute_infrastructure_claim_evidence`. Its own per-source CONTRIBUTION row (id-scoped
    # per (claim, source), so a reimport correctly overwrites rather than accumulates) is what
    # actually carries this source's own evidence_refs and evidence mode.
    claim_query = _MERGE_NODE_TEMPLATE.format(label=INFRASTRUCTURE_CLAIM_LABEL)
    claim_contribution_query = _MERGE_NODE_TEMPLATE.format(
        label=INFRASTRUCTURE_CLAIM_CONTRIBUTION_LABEL
    )
    for claim in model.infrastructure_claims:
        tx.run(
            claim_query,
            id=claim.id,
            props=claim.model_dump(exclude={"evidence_refs"}),
            source_instance_id=source_instance_id,
        )
        subject_contribution = contribution_by_entity_id.get(claim.subject_id)
        tx.run(
            claim_contribution_query,
            id=_infrastructure_claim_contribution_id(claim.id, source_instance_id),
            props={
                "claim_id": claim.id,
                "evidence_refs": claim.evidence_refs,
                "mapping_rule_id": claim.mapping_rule_id,
                "mapping_rule_version": claim.mapping_rule_version,
                "evidence_mode": (
                    subject_contribution.evidence_mode if subject_contribution else None
                ),
            },
            source_instance_id=source_instance_id,
        )
        count += 2
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
    run_source_ids: AbstractSet[str] | None = None,
    run_node_emitters: Mapping[str, AbstractSet[str]] | None = None,
    run_relation_emitters: Mapping[str, AbstractSet[str]] | None = None,
) -> SourceImportStats:
    """`run_source_ids`/`run_node_emitters`/`run_relation_emitters` describe the whole discovery run
    (every source reconciled in it, and which of them emits each node id and relation key), so a
    dropped claim is classified by who owns it after the run; `None` means a run of this source
    alone.

    `committed_nodes_before`/`committed_relations_before`, when given, must be a snapshot of
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

    owned_nodes = {
        record["id"]: set(record["owners"] or ())
        for record in tx.run(_OWNED_NODE_IDS_QUERY, source_instance_id=source_instance_id)
    }
    owned_relations = {
        record["key"]: set(record["owners"] or ())
        for record in tx.run(_OWNED_RELATION_KEYS_QUERY, source_instance_id=source_instance_id)
    }
    existing_node_ids = set(owned_nodes)
    existing_relation_keys = set(owned_relations)

    new_node_ids = _model_node_ids(model, source_instance_id=source_instance_id)
    new_relation_keys = _model_relation_keys(model)
    if replay_decision.case is ReplayCase.SCOPE_CHANGED_PRESERVE_PENDING_TOMBSTONE:
        # I1 spec §5.4/§6: a scope change must not itself authorize expiring claims absent from the
        # new scope - only an explicit inventory transition/tombstone may. Treat everything this
        # source already owned as still "emitted" so nothing computes as dropped this run.
        new_node_ids = new_node_ids | existing_node_ids
        new_relation_keys = new_relation_keys | existing_relation_keys

    if run_source_ids is None:
        run_source_ids = {source_instance_id}
        run_node_emitters = {node_id: {source_instance_id} for node_id in new_node_ids}
        run_relation_emitters = {key: {source_instance_id} for key in new_relation_keys}
    node_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners=_dropped_claim_owners(
            owned_nodes,
            source_instance_id=source_instance_id,
            run_source_ids=run_source_ids,
            run_emitters=run_node_emitters or {},
        ),
        newly_emitted_claim_keys=new_node_ids,
    )
    relation_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners=_dropped_claim_owners(
            owned_relations,
            source_instance_id=source_instance_id,
            run_source_ids=run_source_ids,
            run_emitters=run_relation_emitters or {},
        ),
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

    public_node_ids = _public_node_ids(tx, existing_node_ids | new_node_ids, model)

    nodes_written = _write_nodes(tx, source_instance_id, model)
    relations_written = _write_relations(tx, source_instance_id, model)

    _expire_dropped_claims(
        tx, source_instance_id=source_instance_id, node_plan=node_plan, relation_plan=relation_plan
    )

    # I2 Draft 0.2 §7.2: a brand-new claim, a retained one whose owning source just replaced its own
    # evidence (the specific bug this mechanism replaces two prior write-time-union attempts to
    # fix), and a claim losing one of several owners (a real co-ownership bug found in PR review)
    # all reduce to the same derive-from-scratch recompute.
    _recompute_affected_infrastructure_claims(
        tx,
        node_plan,
        currently_emitted_claim_ids=frozenset(claim.id for claim in model.infrastructure_claims),
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

    # Canonical effects by identity. Added-vs-retained is decided from the pre-run snapshot, not
    # from `node_plan`: in `_import_all_sources_tx` every source's nodes are pre-merged (with their
    # owner ids) before this function runs, so its ownership query already counts every emitted
    # node as owned. `changed` is attributed to this source alone, independent of the order the
    # run's sources are reconciled in: a retained node whose properties differ, ignoring the owner
    # bookkeeping another source's reconciliation may change (every source's property writes are
    # already pre-merged); and a retained relation that gains evidence this source emits, since a
    # relation's only other properties are its key and owners.
    model_node_ids = _model_node_ids(model, source_instance_id=source_instance_id)
    previously_owned_nodes = (existing_node_ids - model_node_ids) | {
        node_id
        for node_id in model_node_ids
        if source_instance_id in (nodes_before.get(node_id) or {}).get("owner_source_ids", [])
    }
    model_relation_keys = _model_relation_keys(model)
    previously_owned_relations = (existing_relation_keys - model_relation_keys) | {
        key
        for key in model_relation_keys
        if source_instance_id in (relations_before.get(key) or {}).get("owner_source_ids", [])
    }
    emitted_evidence: dict[str, set[str]] = {}
    for relation in model.relations:
        emitted_evidence.setdefault(relation_key(relation), set()).update(relation.evidence_ids)
    retained_nodes = new_node_ids & previously_owned_nodes
    retained_relations = new_relation_keys & previously_owned_relations
    effects = SourceClaimEffects(
        added=_effect_set(
            new_node_ids - previously_owned_nodes,
            new_relation_keys - previously_owned_relations,
            public_node_ids,
        ),
        changed=_effect_set(
            {
                i
                for i in retained_nodes
                if _without_owners(nodes_before.get(i)) != _without_owners(nodes_after.get(i))
            },
            {
                k
                for k in retained_relations
                if not emitted_evidence.get(k, set())
                <= set((relations_before.get(k) or {}).get("evidence_ids") or ())
            },
            public_node_ids,
        ),
        expired=_effect_set(
            node_plan.expired_claim_keys, relation_plan.expired_claim_keys, public_node_ids
        ),
        ownership_removed=_effect_set(
            node_plan.ownership_removed_claim_keys,
            relation_plan.ownership_removed_claim_keys,
            public_node_ids,
        ),
    )

    return SourceImportStats(
        source_instance_id=source_instance_id,
        locator=locator,
        result=result,
        nodes_written=nodes_written,
        relations_written=relations_written,
        nodes_expired=len(node_plan.expired_claim_keys),
        relations_expired=len(relation_plan.expired_claim_keys),
        graph_revision_advanced=graph_revision_advanced,
        effects=effects,
    )


def _remove_source_tx(
    tx: neo4j.ManagedTransaction,
    *,
    source_instance_id: str,
    removed_source_ids: AbstractSet[str] = frozenset(),
) -> SourceImportStats:
    """`removed_source_ids` is every source the run removes (this one included): a claim they all
    owned expires for each of them, whichever is removed first."""
    owned_nodes = {
        record["id"]: set(record["owners"] or ())
        for record in tx.run(_OWNED_NODE_IDS_QUERY, source_instance_id=source_instance_id)
    }
    owned_relations = {
        record["key"]: set(record["owners"] or ())
        for record in tx.run(_OWNED_RELATION_KEYS_QUERY, source_instance_id=source_instance_id)
    }
    existing_node_ids = set(owned_nodes)
    removed = {source_instance_id, *removed_source_ids}
    node_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners=_dropped_claim_owners(
            owned_nodes,
            source_instance_id=source_instance_id,
            run_source_ids=removed,
            run_emitters={},
        ),
        newly_emitted_claim_keys=frozenset(),
    )
    relation_plan = plan_source_claim_reconciliation(
        source_instance_id=source_instance_id,
        committed_claim_owners=_dropped_claim_owners(
            owned_relations,
            source_instance_id=source_instance_id,
            run_source_ids=removed,
            run_emitters={},
        ),
        newly_emitted_claim_keys=frozenset(),
    )
    # Classified before anything expires: an expired node may be deleted.
    public_node_ids = _public_node_ids(tx, existing_node_ids, ArchitectureModel())

    _expire_dropped_claims(
        tx, source_instance_id=source_instance_id, node_plan=node_plan, relation_plan=relation_plan
    )
    # This source dropped every claim it owned (emits nothing) - see the identical mechanism in
    # `_import_source_tx`.
    _recompute_affected_infrastructure_claims(tx, node_plan)
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
        effects=SourceClaimEffects(
            expired=_effect_set(
                node_plan.expired_claim_keys, relation_plan.expired_claim_keys, public_node_ids
            ),
            ownership_removed=_effect_set(
                node_plan.ownership_removed_claim_keys,
                relation_plan.ownership_removed_claim_keys,
                public_node_ids,
            ),
        ),
    )


def _import_all_sources_tx(
    tx: neo4j.ManagedTransaction,
    *,
    run_result: DiscoveryRunResult,
    expected_prior_inventory_revision: str | None | NotSupplied = NOT_SUPPLIED,
) -> tuple[
    dict[str, SourceImportStats],
    tuple[str, ...],
    tuple[IngestionDiagnostic, ...],
    tuple[TombstoneDecision, ...],
    tuple[SourceImportStats, ...],
]:
    """Pre-merge, per-source reconciliation, and removal for one whole discovery run, all against
    the same transaction - a run either commits in full or (on any error, including a driver/
    infrastructure failure partway through) rolls back in full. Previously these were separate
    `execute_write` calls per source: a failure partway through the loop left earlier sources'
    writes committed even though the run as a whole never reached `ImportRunStats(committed=True)`
    - contradicting this module's own "nothing is written unless the whole run is COMPLETE"
    contract (I1 spec §6), a real bug found in PR review.

    I2 Draft 0.2 §3 prerequisite slice, items 3/4/5: also reads and (on success) rewrites the
    scope's `CurrentInventory` state in this same transaction. `expected_prior_inventory_revision`
    defaults to `NOT_SUPPLIED` (skip the check entirely - every existing caller's behavior is
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

    # Type-based, not identity-based: NotSupplied is a public type (relocated here from a
    # file-private sentinel in I2 Draft 0.2 slice 2b-ii specifically so lower layers could also use
    # it), so a caller can legally construct its own NotSupplied() instance - `is not NOT_SUPPLIED`
    # would treat that as a real predecessor value and incorrectly reject the run as stale. Any
    # NotSupplied instance, not only the canonical singleton, must mean "skip the check" (a real
    # finding from PR review).
    if not isinstance(expected_prior_inventory_revision, NotSupplied):
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
    tombstone_decisions: list[TombstoneDecision] = []
    for tombstone in run_result.inventory_snapshot.tombstones:
        validation = validate_tombstone_against_committed_inventory(
            tombstone=tombstone,
            committed_discovery_scope_id=committed_discovery_scope_id,
            committed_scope_definition_digest=persisted_inventory["scope_definition_digest"],
            committed_inventory_revision=persisted_inventory["inventory_revision"],
        )
        tombstone_validations[tombstone.target_source_instance_id] = validation
        tombstone_decisions.append(
            TombstoneDecision(
                target_source_instance_id=tombstone.target_source_instance_id,
                tombstone_revision=tombstone.tombstone_revision,
                accepted=validation.accepted,
                reason=(
                    validation.rejection_reason.value
                    if validation.rejection_reason is not None
                    else None
                ),
            )
        )
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
    for source_instance_id, source_outcome in run_result.source_outcomes.items():
        all_node_ids |= _model_node_ids(
            source_outcome.outcome.model, source_instance_id=source_instance_id
        )
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

    # Which absent sources this COMPLETE run removes is decided before any source is reconciled:
    # they take part in the run too (they will own nothing after it), so a claim a present source
    # drops and a removed source co-owned expires rather than surviving for an owner that is about
    # to leave. Removing a source never changes another's authorization, so deciding early is safe.
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
                removed_source_instance_ids.append(source_instance_id)

    run_node_emitters: dict[str, set[str]] = {}
    run_relation_emitters: dict[str, set[str]] = {}
    for source_instance_id, source_outcome in run_result.source_outcomes.items():
        model = source_outcome.outcome.model
        for node_id in _model_node_ids(model, source_instance_id=source_instance_id):
            run_node_emitters.setdefault(node_id, set()).add(source_instance_id)
        for key in _model_relation_keys(model):
            run_relation_emitters.setdefault(key, set()).add(source_instance_id)

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
            run_source_ids=frozenset(run_result.source_outcomes) | set(removed_source_instance_ids),
            run_node_emitters=run_node_emitters,
            run_relation_emitters=run_relation_emitters,
        )

    # Decided before any is removed, so a claim several removed sources shared expires for each.
    removal_stats: list[SourceImportStats] = []
    for source_instance_id in removed_source_instance_ids:
        removal_stats.append(
            _remove_source_tx(
                tx,
                source_instance_id=source_instance_id,
                removed_source_ids=frozenset(removed_source_instance_ids),
            )
        )

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

    return (
        per_source,
        tuple(removed_source_instance_ids),
        tuple(tombstone_diagnostics),
        tuple(tombstone_decisions),
        tuple(removal_stats),
    )


def _source_run_results(run_result: DiscoveryRunResult) -> tuple[SourceRunResult, ...]:
    """Every discovered source's own I1 §10 result, sorted by source instance id - taken from the
    discovery run itself, so it exists whether or not the run commits."""
    return tuple(
        _source_run_result(source_instance_id, run_outcome)
        for source_instance_id, run_outcome in sorted(run_result.source_outcomes.items())
    )


def _source_run_result(source_instance_id: str, run_outcome: SourceRunOutcome) -> SourceRunResult:
    descriptor = run_outcome.descriptor
    model = run_outcome.outcome.model
    return SourceRunResult(
        source_instance_id=source_instance_id,
        locator=run_outcome.descriptor_locator,
        result=run_outcome.outcome.result,
        diagnostics=tuple(run_outcome.outcome.diagnostics),
        source_kind=descriptor.source_kind.value if descriptor is not None else "",
        adapter_identity=(descriptor.adapter_identity or None) if descriptor is not None else None,
        mapping_rule_version=(
            (descriptor.mapping_rule_version or None) if descriptor is not None else None
        ),
        dialect_version=descriptor.document_dialect_version if descriptor is not None else None,
        semantic_input_digest=run_outcome.outcome.semantic_input_digest,
        service_ids=tuple(sorted({service.id for service in model.services})),
        emitted=EmittedCounts.of(model),
    )


def import_discovery_run(
    driver: neo4j.Driver,
    *,
    database: str,
    run_result: DiscoveryRunResult,
    expected_prior_inventory_revision: str | None | NotSupplied = NOT_SUPPLIED,
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
    source_results = _source_run_results(run_result)
    if not run_result.commit_eligible:
        return ImportRunStats(
            inventory_status=run_result.inventory_status,
            committed=False,
            per_source={},
            removed_source_instance_ids=(),
            diagnostics=run_result.diagnostics,
            source_results=source_results,
            discovery_scope_id=run_result.discovery_scope_id,
            scope_definition_digest=run_result.scope_definition_digest,
        )

    with open_session(driver, database=database) as session:
        ensure_schema(session)
        try:
            (
                per_source,
                removed_source_instance_ids,
                tombstone_diagnostics,
                tombstone_decisions,
                removal_stats,
            ) = session.execute_write(
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
                source_results=source_results,
                discovery_scope_id=run_result.discovery_scope_id,
                scope_definition_digest=run_result.scope_definition_digest,
            )

        return ImportRunStats(
            inventory_status=run_result.inventory_status,
            committed=True,
            per_source=per_source,
            removed_source_instance_ids=removed_source_instance_ids,
            diagnostics=(*run_result.diagnostics, *tombstone_diagnostics),
            source_results=source_results,
            discovery_scope_id=run_result.discovery_scope_id,
            scope_definition_digest=run_result.scope_definition_digest,
            inventory_revision=run_result.inventory_snapshot.inventory_revision,
            tombstone_decisions=tombstone_decisions,
            removal_stats=removal_stats,
        )


def import_all_sources(
    driver: neo4j.Driver,
    *,
    database: str,
    source_config: FilesystemSourceConfig,
    migration_mappings: SharedIdentityMappingIndex | None = None,
    tombstones: Sequence[Tombstone] = (),
    expected_prior_inventory_revision: str | None | NotSupplied = NOT_SUPPLIED,
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


def import_kubernetes_source(
    driver: neo4j.Driver,
    *,
    database: str,
    source_config: KubernetesSourceConfig,
    migration_mappings: SharedIdentityMappingIndex | None = None,
    tombstones: Sequence[Tombstone] = (),
) -> ImportRunStats:
    """Thin wrapper over `run_kubernetes_discovery` + `import_discovery_run` for the Kubernetes
    source kind, mirroring `import_all_sources`'s exact shape (I2 Draft 0.2 slice 2b-i). Threads the
    envelope's own `completeness.expectedPriorInventoryRevision` (carried on `run_result` by
    `KubernetesSourceDiscoverer`) into the predecessor-check transaction, and layers the
    Kubernetes-specific `K8S_STALE_INVENTORY` diagnostic alongside the generic
    `STALE_INVENTORY_PREDECESSOR` one on a stale predecessor (I2 Draft 0.2 §4.2/§10, slice 2b-ii) -
    at this wrapper level, not inside `_import_all_sources_tx`, which stays source-kind-neutral.
    """
    run_result = run_kubernetes_discovery(
        source_config, migration_mappings=migration_mappings, tombstones=tombstones
    )
    stats = import_discovery_run(
        driver,
        database=database,
        run_result=run_result,
        expected_prior_inventory_revision=run_result.expected_prior_inventory_revision,
    )
    # STALE_INVENTORY_PREDECESSOR can only appear here when a real (non-NOT_SUPPLIED) expectation
    # was actually checked - i.e. only for a fully-accepted Kubernetes envelope - so this never
    # spuriously fires for a rejected source or bleeds into a filesystem source's own diagnostics.
    if any(d.code == DiagnosticCode.STALE_INVENTORY_PREDECESSOR for d in stats.diagnostics):
        # §10: "K8S_STALE_INVENTORY | REJECTED_CONFLICT; no commit." `committed=False` alone
        # satisfies "no commit" but not the REJECTED_CONFLICT classification itself -
        # import_discovery_run's stale-predecessor path returns per_source={} (the transaction
        # aborted before any write), so there is nothing to rewrite there. `run_result.
        # source_outcomes` still holds the pre-transaction (accepted-at-discovery-time) outcome for
        # exactly this reason: staleness is a commit-time-only check (§4.2), undetectable at
        # discovery time. Mirrors K8S_RESOURCE_CONFLICT's own precedent (`_rejected_conflict`
        # rewriting the affected source's own result) - reconstructed here, not inside the
        # transaction, since that is source-kind-neutral and must not classify a Kubernetes-
        # specific outcome.
        stale_per_source = {
            source_instance_id: SourceImportStats(
                source_instance_id=source_instance_id,
                locator=run_outcome.descriptor_locator,
                result=IngestionResult.REJECTED_CONFLICT,
                nodes_written=0,
                relations_written=0,
                nodes_expired=0,
                relations_expired=0,
                graph_revision_advanced=False,
            )
            for source_instance_id, run_outcome in run_result.source_outcomes.items()
        }
        stats = replace(
            stats,
            per_source=stale_per_source,
            source_results=tuple(
                replace(source_result, result=IngestionResult.REJECTED_CONFLICT)
                for source_result in stats.source_results
            ),
            diagnostics=(
                *stats.diagnostics,
                IngestionDiagnostic(
                    code=DiagnosticCode.K8S_STALE_INVENTORY,
                    message="stale or racing predecessor: expectedPriorInventoryRevision did not "
                    "match the currently committed inventory revision",
                ),
            ),
        )
    return stats
