import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.analysis.runtime import confirmed_relations, observed_only_relations
from app.canonical import ids
from app.canonical.model import (
    ArchitectureModel,
    Message,
    Operation,
    Queue,
    Relation,
    Schema,
    Service,
)
from app.graph.importer import import_all_sources, import_source
from app.graph.schema import ensure_schema
from app.provenance.model import ObservedEvidence, Provenance
from app.sources.model import FilesystemSourceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"

SCOPE_ID = "urn:aip:discovery-scope:test"
SCOPE_DIGEST_1 = "scope-digest-1"
SCOPE_DIGEST_2 = "scope-digest-2"
DIGEST_1 = "a" * 64
DIGEST_2 = "b" * 64


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _count(driver, query: str, **params) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query, **params).single()["c"]


def _import(session, source_instance_id: str, model: ArchitectureModel, *, digest: str = DIGEST_1):
    return import_source(
        session,
        source_instance_id=source_instance_id,
        locator=f"{source_instance_id}.yaml",
        model=model,
        semantic_input_digest=digest,
        discovery_scope_id=SCOPE_ID,
        scope_definition_digest=SCOPE_DIGEST_1,
    )


def test_ensure_schema_creates_constraints(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        names = {
            record["name"] for record in session.run("SHOW CONSTRAINTS YIELD name RETURN name")
        }
    assert {
        "service_id",
        "operation_id",
        "queue_id",
        "message_id",
        "schema_id",
        "source_state_source_instance_id",
    } <= names


def test_import_source_creates_nodes_and_relations(driver):
    model = ArchitectureModel(
        services=[Service(id="service:product-service", name="ProductService")],
        operations=[
            Operation(
                id="operation:product-service:GET:/products/{id}",
                service_id="service:product-service",
                operation_id="getProduct",
                method="GET",
                path="/products/{id}",
                response_schema_ids=["schema:Product"],
            )
        ],
        schemas=[Schema(id="schema:Product", name="Product", format="application/json")],
        relations=[
            Relation(
                type="PROVIDES",
                source_id="service:product-service",
                target_id="operation:product-service:GET:/products/{id}",
            ),
            Relation(
                type="RESPONSE_SCHEMA",
                source_id="operation:product-service:GET:/products/{id}",
                target_id="schema:Product",
            ),
        ],
    )

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        stats = _import(session, "src:product-service", model)

    assert stats.nodes_written == 3
    assert stats.relations_written == 2
    assert stats.nodes_expired == 0
    assert stats.relations_expired == 0
    assert stats.graph_revision_advanced is True

    assert (
        _count(driver, "MATCH (n:Service {id: 'service:product-service'}) RETURN count(n) AS c")
        == 1
    )
    assert _count(driver, "MATCH ()-[r:PROVIDES]->() RETURN count(r) AS c") == 1
    assert _count(driver, "MATCH ()-[r:RESPONSE_SCHEMA]->() RETURN count(r) AS c") == 1

    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (n:Service {id: 'service:product-service'}) RETURN n.owner_source_ids AS owners"
        ).single()
    assert record["owners"] == ["src:product-service"]


def test_import_source_creates_evidence_node_and_tags_relation(driver):
    evidence = Provenance(
        id="evidence:openapi:src:product-service",
        source_type="OPENAPI",
        source_file="product-service/openapi.yaml",
        source_revision="abc123",
    )
    model = ArchitectureModel(
        services=[Service(id="service:product-service", name="ProductService")],
        operations=[
            Operation(
                id="operation:product-service:GET:/products/{id}",
                service_id="service:product-service",
                operation_id="getProduct",
                method="GET",
                path="/products/{id}",
            )
        ],
        relations=[
            Relation(
                type="PROVIDES",
                source_id="service:product-service",
                target_id="operation:product-service:GET:/products/{id}",
                evidence_ids=[evidence.id],
            )
        ],
        provenance=[evidence],
    )
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        stats = _import(session, "src:product-service", model)

    assert stats.nodes_written == 3  # service + operation + evidence

    with driver.session(database=DATABASE) as session:
        evidence_record = session.run(
            "MATCH (e:Evidence {id: $id}) RETURN e.source_type AS source_type, "
            "e.source_file AS source_file, e.source_revision AS source_revision, "
            "e.evidence_type AS evidence_type, e.owner_source_ids AS owners",
            id=evidence.id,
        ).single()
    assert evidence_record["source_type"] == "OPENAPI"
    assert evidence_record["source_file"] == "product-service/openapi.yaml"
    assert evidence_record["source_revision"] == "abc123"
    assert evidence_record["evidence_type"] == "DECLARED"
    assert evidence_record["owners"] == ["src:product-service"]

    with driver.session(database=DATABASE) as session:
        relation_record = session.run(
            "MATCH ()-[r:PROVIDES]->() RETURN r.evidence_ids AS evidence_ids"
        ).single()
    assert relation_record["evidence_ids"] == [evidence.id]


def test_shared_relation_accumulates_evidence_from_both_declaring_sources(driver):
    # Mirrors the real fixture landscape: order-service (sender) and payment-service (receiver)
    # both independently declare CARRIES payment-q -> PaymentRequested in their own AsyncAPI docs -
    # the same relation triple, two separate import transactions, two separate pieces of evidence
    # that must both survive.
    evidence_order = Provenance(
        id="evidence:asyncapi:src:order-service",
        source_type="ASYNCAPI",
        source_file="order-service/asyncapi.yaml",
    )
    evidence_payment = Provenance(
        id="evidence:asyncapi:src:payment-service",
        source_type="ASYNCAPI",
        source_file="payment-service/asyncapi.yaml",
    )
    order_model = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
        messages=[Message(id="message:PaymentRequested:v2", name="PaymentRequested", version="v2")],
        relations=[
            Relation(
                type="SENDS",
                source_id="service:order-service",
                target_id="queue:payment-q",
                evidence_ids=[evidence_order.id],
            ),
            Relation(
                type="CARRIES",
                source_id="queue:payment-q",
                target_id="message:PaymentRequested:v2",
                evidence_ids=[evidence_order.id],
            ),
        ],
        provenance=[evidence_order],
    )
    payment_model = ArchitectureModel(
        services=[Service(id="service:payment-service", name="PaymentService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
        messages=[Message(id="message:PaymentRequested:v2", name="PaymentRequested", version="v2")],
        relations=[
            Relation(
                type="RECEIVES_FROM",
                source_id="service:payment-service",
                target_id="queue:payment-q",
                evidence_ids=[evidence_payment.id],
            ),
            Relation(
                type="CARRIES",
                source_id="queue:payment-q",
                target_id="message:PaymentRequested:v2",
                evidence_ids=[evidence_payment.id],
            ),
        ],
        provenance=[evidence_payment],
    )

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:order-service", order_model)
        _import(session, "src:payment-service", payment_model)

    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (:Queue {id:'queue:payment-q'})-[r:CARRIES]->(:Message) "
            "RETURN r.evidence_ids AS evidence_ids"
        ).single()
    assert set(record["evidence_ids"]) == {evidence_order.id, evidence_payment.id}

    # order-service stops declaring payment-q entirely (e.g. its asyncapi.yaml was removed)
    order_model_without_payment_q = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")]
    )
    with driver.session(database=DATABASE) as session:
        _import(session, "src:order-service", order_model_without_payment_q, digest=DIGEST_2)

    # order-service's evidence is gone entirely (no longer referenced by anyone)
    assert (
        _count(driver, "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c", id=evidence_order.id)
        == 0
    )
    # the CARRIES relation survives (payment-service still declares it) with only
    # payment-service's evidence remaining
    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (:Queue {id:'queue:payment-q'})-[r:CARRIES]->(:Message) "
            "RETURN r.evidence_ids AS evidence_ids"
        ).single()
    assert record["evidence_ids"] == [evidence_payment.id]


def test_import_source_is_idempotent(driver):
    model = ArchitectureModel(
        services=[Service(id="service:x", name="X")],
        queues=[Queue(id="queue:x-q", name="x-q")],
        relations=[Relation(type="SENDS", source_id="service:x", target_id="queue:x-q")],
    )
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        first = _import(session, "src:x", model)
        second = _import(session, "src:x", model)

    # excludes the v0.4.0 I1.2 internal revision-fence singleton (spec §19) and the new SourceState
    # bookkeeping node (I1 v0.5.0) - neither is part of the Canonical Model.
    assert (
        _count(
            driver,
            "MATCH (n) WHERE NOT n:AipInternalState AND NOT n:SourceState RETURN count(n) AS c",
        )
        == 2
    )
    assert _count(driver, "MATCH ()-[r]->() RETURN count(r) AS c") == 1
    assert first.graph_revision_advanced is True
    # I1 spec §5.4: an unchanged reimport is a true no-op - no graph-revision advance.
    assert second.graph_revision_advanced is False


def test_reimport_expires_stale_facts_no_longer_declared(driver):
    with_queue = ArchitectureModel(
        services=[Service(id="service:x", name="X")],
        queues=[Queue(id="queue:old-q", name="old-q")],
        relations=[Relation(type="SENDS", source_id="service:x", target_id="queue:old-q")],
    )
    without_queue = ArchitectureModel(
        services=[Service(id="service:x", name="X")],
        queues=[Queue(id="queue:new-q", name="new-q")],
        relations=[Relation(type="SENDS", source_id="service:x", target_id="queue:new-q")],
    )

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:x", with_queue)
        assert _count(driver, "MATCH (q:Queue {id: 'queue:old-q'}) RETURN count(q) AS c") == 1

        stats = _import(session, "src:x", without_queue, digest=DIGEST_2)

    assert stats.nodes_expired == 1
    assert stats.relations_expired == 1
    assert stats.graph_revision_advanced is True
    assert _count(driver, "MATCH (q:Queue {id: 'queue:old-q'}) RETURN count(q) AS c") == 0
    assert _count(driver, "MATCH (q:Queue {id: 'queue:new-q'}) RETURN count(q) AS c") == 1


def test_reimport_with_changed_scope_preserves_absent_claims(driver):
    # I1 spec §5.4/§6: a changed scope_definition_digest must not itself authorize expiring claims
    # this source stops emitting - only an explicit tombstone/inventory transition may.
    with_queue = ArchitectureModel(
        services=[Service(id="service:x", name="X")],
        queues=[Queue(id="queue:old-q", name="old-q")],
        relations=[Relation(type="SENDS", source_id="service:x", target_id="queue:old-q")],
    )
    without_queue = ArchitectureModel(services=[Service(id="service:x", name="X")])

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:x", with_queue)
        stats = import_source(
            session,
            source_instance_id="src:x",
            locator="src:x.yaml",
            model=without_queue,
            semantic_input_digest=DIGEST_2,
            discovery_scope_id=SCOPE_ID,
            scope_definition_digest=SCOPE_DIGEST_2,  # scope changed
        )

    assert stats.nodes_expired == 0
    assert stats.relations_expired == 0
    assert _count(driver, "MATCH (q:Queue {id: 'queue:old-q'}) RETURN count(q) AS c") == 1


_SINCE = datetime(2026, 8, 26, 0, 0, tzinfo=UTC)


def _observed_fact(*, subject_id: str, relation_type: str, object_id: str, environment: str):
    timestamp = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(
            environment, datetime(2026, 8, 26, tzinfo=UTC), subject_id, relation_type, object_id
        ),
        environment=environment,
        bucket_start=datetime(2026, 8, 26, tzinfo=UTC),
        bucket_end=datetime(2026, 8, 27, tzinfo=UTC),
        first_seen=timestamp,
        last_seen=timestamp,
        observation_count=1,
        sample_trace_ids=["a" * 32],
    )
    return ObservedFactCandidate(
        subject_id=subject_id,
        relation_type=relation_type,
        object_id=object_id,
        environment=environment,
        timestamp=timestamp,
        trace_id="a" * 32,
        evidence=evidence,
    )


def test_declared_evidence_removed_but_observed_evidence_preserved(driver):
    # 11H-A / R1: a relation with both DECLARED and OBSERVED evidence must survive a re-import
    # that drops the declaration, retaining exactly its OBSERVED evidence (spec Delete(F) iff
    # Evidence(F) = empty - not iff DeclaredSources(F) = empty).
    declared_evidence = Provenance(
        id="evidence:asyncapi:src:order-service",
        source_type="ASYNCAPI",
        source_file="order-service/asyncapi.yaml",
    )
    with_relation = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
        relations=[
            Relation(
                type="SENDS",
                source_id="service:order-service",
                target_id="queue:payment-q",
                evidence_ids=[declared_evidence.id],
            )
        ],
        provenance=[declared_evidence],
    )
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:order-service", with_relation)

    observed_fact = _observed_fact(
        subject_id="service:order-service",
        relation_type="SENDS",
        object_id="queue:payment-q",
        environment="production",
    )
    persist_observation_batch(driver, DATABASE, ObservationBatch(facts=[observed_fact]))

    with driver.session(database=DATABASE) as session:
        confirmed = confirmed_relations(session, environment="production", since=_SINCE)
    assert any(r.target_id == "queue:payment-q" for r in confirmed)

    # Re-import order-service still declaring the queue itself, but no longer the SENDS
    # relation to it - keeps the Queue node alive so only the relation goes stale, not the node.
    without_relation = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
    )
    with driver.session(database=DATABASE) as session:
        stats = _import(session, "src:order-service", without_relation, digest=DIGEST_2)

    assert stats.relations_expired == 1
    assert (
        _count(driver, "MATCH ()-[r:SENDS]->(:Queue {id: 'queue:payment-q'}) RETURN count(r) AS c")
        == 1
    )
    with driver.session(database=DATABASE) as session:
        relation_record = session.run(
            "MATCH ()-[r:SENDS]->(:Queue {id: 'queue:payment-q'}) RETURN r.evidence_ids AS ids"
        ).single()
    assert declared_evidence.id not in relation_record["ids"]
    assert observed_fact.evidence.id in relation_record["ids"]

    with driver.session(database=DATABASE) as session:
        observed_only = observed_only_relations(session, environment="production", since=_SINCE)
    assert any(r.target_id == "queue:payment-q" for r in observed_only)


def test_shared_declared_evidence_survives_reconciliation_with_observed_evidence_present(driver):
    # Extends test_shared_relation_accumulates_evidence_from_both_declaring_sources (11H-A / R1
    # §5.3): a relation declared by two independent sources plus OBSERVED evidence must lose only
    # the reimporting source's own DECLARED evidence - never the other declarer's, never OBSERVED.
    evidence_order = Provenance(
        id="evidence:asyncapi:src:order-service",
        source_type="ASYNCAPI",
        source_file="order-service/asyncapi.yaml",
    )
    evidence_payment = Provenance(
        id="evidence:asyncapi:src:payment-service",
        source_type="ASYNCAPI",
        source_file="payment-service/asyncapi.yaml",
    )
    order_model = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
        messages=[Message(id="message:PaymentRequested:v2", name="PaymentRequested", version="v2")],
        relations=[
            Relation(
                type="CARRIES",
                source_id="queue:payment-q",
                target_id="message:PaymentRequested:v2",
                evidence_ids=[evidence_order.id],
            ),
        ],
        provenance=[evidence_order],
    )
    payment_model = ArchitectureModel(
        services=[Service(id="service:payment-service", name="PaymentService")],
        queues=[Queue(id="queue:payment-q", name="payment-q")],
        messages=[Message(id="message:PaymentRequested:v2", name="PaymentRequested", version="v2")],
        relations=[
            Relation(
                type="CARRIES",
                source_id="queue:payment-q",
                target_id="message:PaymentRequested:v2",
                evidence_ids=[evidence_payment.id],
            ),
        ],
        provenance=[evidence_payment],
    )
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:order-service", order_model)
        _import(session, "src:payment-service", payment_model)

    observed_fact = _observed_fact(
        subject_id="queue:payment-q",
        relation_type="CARRIES",
        object_id="message:PaymentRequested:v2",
        environment="production",
    )
    persist_observation_batch(driver, DATABASE, ObservationBatch(facts=[observed_fact]))

    # order-service stops declaring the CARRIES relation entirely.
    order_model_without_carries = ArchitectureModel(
        services=[Service(id="service:order-service", name="OrderService")]
    )
    with driver.session(database=DATABASE) as session:
        _import(session, "src:order-service", order_model_without_carries, digest=DIGEST_2)

    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (:Queue {id:'queue:payment-q'})-[r:CARRIES]->(:Message) "
            "RETURN r.evidence_ids AS evidence_ids"
        ).single()
    assert set(record["evidence_ids"]) == {evidence_payment.id, observed_fact.evidence.id}


def test_shared_queue_kept_when_still_referenced_by_another_source(driver):
    sender_model = ArchitectureModel(
        services=[Service(id="service:sender", name="Sender")],
        queues=[Queue(id="queue:shared-q", name="shared-q")],
        relations=[Relation(type="SENDS", source_id="service:sender", target_id="queue:shared-q")],
    )
    receiver_model = ArchitectureModel(
        services=[Service(id="service:receiver", name="Receiver")],
        queues=[Queue(id="queue:shared-q", name="shared-q")],
        relations=[
            Relation(type="RECEIVES_FROM", source_id="service:receiver", target_id="queue:shared-q")
        ],
    )
    sender_model_without_queue = ArchitectureModel(
        services=[Service(id="service:sender", name="Sender")]
    )

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, "src:sender", sender_model)
        _import(session, "src:receiver", receiver_model)

        with driver.session(database=DATABASE) as read_session:
            owners = read_session.run(
                "MATCH (q:Queue {id: 'queue:shared-q'}) RETURN q.owner_source_ids AS owners"
            ).single()["owners"]
        assert set(owners) == {"src:sender", "src:receiver"}

        # sender no longer declares the queue, but receiver still does -> queue must survive
        _import(session, "src:sender", sender_model_without_queue, digest=DIGEST_2)

    assert _count(driver, "MATCH (q:Queue {id: 'queue:shared-q'}) RETURN count(q) AS c") == 1
    with driver.session(database=DATABASE) as session:
        owners = session.run(
            "MATCH (q:Queue {id: 'queue:shared-q'}) RETURN q.owner_source_ids AS owners"
        ).single()["owners"]
    assert owners == ["src:receiver"]


def test_import_source_rejects_unknown_relation_type_without_writing_anything(driver):
    model = ArchitectureModel(
        services=[Service(id="service:x", name="X")],
        relations=[Relation(type="BOGUS", source_id="service:x", target_id="service:x")],
    )
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        with pytest.raises(ValueError, match="Unknown relation type"):
            _import(session, "src:x", model)

    # excludes the v0.4.0 I1.2 internal revision-fence singleton (spec §19) - `ensure_schema`
    # creates it unconditionally, before the (failed) import ever runs.
    assert _count(driver, "MATCH (n) WHERE NOT n:AipInternalState RETURN count(n) AS c") == 0


def _bundled_examples_config() -> FilesystemSourceConfig:
    return FilesystemSourceConfig(
        id="aip-bundled-examples-v0.5",
        root=EXAMPLES_DIR,
        stable_target_identity="urn:aip:logical-root:bundled-examples",
    )


def test_import_all_sources_real_examples_end_to_end(driver):
    stats = import_all_sources(driver, database=DATABASE, source_config=_bundled_examples_config())

    assert stats.committed is True
    assert len(stats.per_source) == 6  # order (x3), product, payment, invoice
    assert _count(driver, "MATCH (n:Service) RETURN count(n) AS c") == 4

    calls = _count(driver, "MATCH ()-[r:CALLS]->() RETURN count(r) AS c")
    assert calls == 1
    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (s:Service {id: 'service:order-service'})-[:CALLS]->(o:Operation) RETURN o.id AS id"
        ).single()
    assert record["id"] == "operation:service:product-service:GET:/products/{id}"

    assert _count(driver, "MATCH ()-[r:DEAD_LETTERS_TO]->() RETURN count(r) AS c") == 1
    assert _count(driver, "MATCH (q:Queue) RETURN count(q) AS c") == 5

    # Evidence: one per discovered source file - order-service has 3 (openapi/asyncapi/manifest),
    # product-service/payment-service/invoice-service have 1 each (AC13).
    assert _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c") == 6

    # PaymentRequested is independently declared by order-service (sender) and payment-service
    # (receiver) - under I1's owner-scoped Message identity (§9.1), with no explicit shared-
    # identity mapping wired in 3a, these are two DISTINCT Message entities, each with its own
    # single-source CARRIES relation from payment-q - not one merged node with two evidence ids.
    with driver.session(database=DATABASE) as session:
        records = list(
            session.run(
                "MATCH (:Queue {name: 'payment-q'})-[r:CARRIES]->(m:Message {name: 'PaymentRequested'}) "
                "RETURN r.evidence_ids AS evidence_ids"
            )
        )
    assert len(records) == 2
    assert all(len(record["evidence_ids"]) == 1 for record in records)


def test_import_all_sources_is_idempotent(driver):
    config = _bundled_examples_config()
    import_all_sources(driver, database=DATABASE, source_config=config)
    first_nodes = _count(driver, "MATCH (n) RETURN count(n) AS c")
    first_relations = _count(driver, "MATCH ()-[r]->() RETURN count(r) AS c")

    stats = import_all_sources(driver, database=DATABASE, source_config=config)
    second_nodes = _count(driver, "MATCH (n) RETURN count(n) AS c")
    second_relations = _count(driver, "MATCH ()-[r]->() RETURN count(r) AS c")

    assert first_nodes == second_nodes
    assert first_relations == second_relations
    assert all(not s.graph_revision_advanced for s in stats.per_source.values())


def test_import_all_sources_removes_source_no_longer_discovered(driver, tmp_path):
    root = tmp_path / "root"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    shutil.copytree(EXAMPLES_DIR / "order-service", root / "order-service")
    # order-service's architecture.yaml calls product-service's getProduct - drop it so this
    # synthetic scope doesn't depend on cross-referencing manifest resolution.
    (root / "order-service" / "architecture.yaml").unlink()

    config = FilesystemSourceConfig(id="removal-test", root=root)
    stats1 = import_all_sources(driver, database=DATABASE, source_config=config)
    assert stats1.committed is True
    assert _count(driver, "MATCH (n:Service) RETURN count(n) AS c") == 2

    # product-service is removed from the filesystem entirely
    shutil.rmtree(root / "product-service")

    stats2 = import_all_sources(driver, database=DATABASE, source_config=config)
    assert stats2.committed is True
    assert len(stats2.removed_source_instance_ids) == 1
    assert (
        _count(driver, "MATCH (s:Service {id: 'service:product-service'}) RETURN count(s) AS c")
        == 0
    )
    assert (
        _count(driver, "MATCH (s:Service {id: 'service:order-service'}) RETURN count(s) AS c") == 1
    )
