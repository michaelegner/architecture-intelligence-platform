import neo4j

from app.graph.revision_fence import ensure_revision_singleton

CONSTRAINTS = [
    "CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT operation_id IF NOT EXISTS FOR (o:Operation) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT queue_id IF NOT EXISTS FOR (q:Queue) REQUIRE q.id IS UNIQUE",
    "CREATE CONSTRAINT message_id IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT schema_id IF NOT EXISTS FOR (s:Schema) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE",
    # I1 v0.5.0 PR 3a: one committed-replay-state node per source instance, read/written by
    # app.graph.importer to feed app.sources.replay.classify_replay_case.
    (
        "CREATE CONSTRAINT source_state_source_instance_id IF NOT EXISTS "
        "FOR (s:SourceState) REQUIRE s.source_instance_id IS UNIQUE"
    ),
    # I2 Draft 0.2 §3 prerequisite slice: one persisted "current committed inventory" node per
    # discovery scope, read/written by app.graph.importer to feed the transactional predecessor
    # comparison and the inventory_event_id audit chain.
    (
        "CREATE CONSTRAINT current_inventory_discovery_scope_id IF NOT EXISTS "
        "FOR (i:CurrentInventory) REQUIRE i.discovery_scope_id IS UNIQUE"
    ),
    # I2 Draft 0.2 §3 item 6 / §7: internal-only infrastructure facts, owned and reconciled through
    # the same per-source machinery as every other canonical node - so they need the same stable-id
    # uniqueness guarantee.
    (
        "CREATE CONSTRAINT infrastructure_entity_id IF NOT EXISTS "
        "FOR (e:InfrastructureEntity) REQUIRE e.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT infrastructure_contribution_id IF NOT EXISTS "
        "FOR (c:InfrastructureContribution) REQUIRE c.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT infrastructure_claim_id IF NOT EXISTS "
        "FOR (c:InfrastructureClaim) REQUIRE c.id IS UNIQUE"
    ),
    # I2 Draft 0.2 §7.2: one per-source claim-support row, id-scoped per (claim, source) exactly
    # like InfrastructureContribution - see app.graph.importer's own module docstring on why a
    # claim's shared evidence_refs is derived from these rather than written to directly.
    (
        "CREATE CONSTRAINT infrastructure_claim_contribution_id IF NOT EXISTS "
        "FOR (c:InfrastructureClaimContribution) REQUIRE c.id IS UNIQUE"
    ),
    # v0.4.0 I1.2, spec §19: read_revision()/bump_revision() rely on (:AipInternalState {id}) being
    # a true singleton (read_revision() uses .single()) - without this, a concurrent
    # ensure_revision_singleton() race could create a duplicate and break stable-read fencing.
    "CREATE CONSTRAINT aip_internal_state_id IF NOT EXISTS FOR (s:AipInternalState) REQUIRE s.id IS UNIQUE",
    # v0.5.0 I3 §9.4/§23 slice 2: a bounded OTel runtime identity observation, kept under its own
    # label rather than :Evidence - see app.provenance.model.RuntimeIdentityObservation's docstring.
    (
        "CREATE CONSTRAINT runtime_identity_observation_id IF NOT EXISTS "
        "FOR (o:RuntimeIdentityObservation) REQUIRE o.id IS UNIQUE"
    ),
]


def ensure_schema(session: neo4j.Session) -> None:
    """Applies the spec §11.4 uniqueness constraints idempotently, and ensures the v0.4.0 I1.2
    internal revision-fence singleton exists (spec §19) before the graph is written to or read
    through the architecture-intelligence contract."""
    for statement in CONSTRAINTS:
        session.run(statement)
    ensure_revision_singleton(session)
