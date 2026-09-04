import neo4j

from app.graph.revision_fence import ensure_revision_singleton

CONSTRAINTS = [
    "CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT operation_id IF NOT EXISTS FOR (o:Operation) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT queue_id IF NOT EXISTS FOR (q:Queue) REQUIRE q.id IS UNIQUE",
    "CREATE CONSTRAINT message_id IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT schema_id IF NOT EXISTS FOR (s:Schema) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE",
    # v0.4.0 I1.2, spec §19: read_revision()/bump_revision() rely on (:AipInternalState {id}) being
    # a true singleton (read_revision() uses .single()) - without this, a concurrent
    # ensure_revision_singleton() race could create a duplicate and break stable-read fencing.
    "CREATE CONSTRAINT aip_internal_state_id IF NOT EXISTS FOR (s:AipInternalState) REQUIRE s.id IS UNIQUE",
]


def ensure_schema(session: neo4j.Session) -> None:
    """Applies the spec §11.4 uniqueness constraints idempotently, and ensures the v0.4.0 I1.2
    internal revision-fence singleton exists (spec §19) before the graph is written to or read
    through the architecture-intelligence contract."""
    for statement in CONSTRAINTS:
        session.run(statement)
    ensure_revision_singleton(session)
