from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.canonical import ids
from app.graph.importer import import_all_sources
from app.telemetry.adapter import correlate_http_call_observations, correlate_queue_observations
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.messaging_guards import UNSUPPORTED_DESTINATION_SEMANTICS
from app.telemetry.model import RuntimeSpan, day_bucket
from app.telemetry.operation_resolver import fetch_operation_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"


@pytest.fixture(scope="module", autouse=True)
def populated_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)


@pytest.fixture
def session(driver):
    with driver.session(database=DATABASE) as s:
        yield s


def _span(**overrides) -> RuntimeSpan:
    defaults = {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "parent_span_id": None,
        "span_name": "op",
        "span_kind": "CLIENT",
        "service_name": "OrderService",
        "service_namespace": None,
        "service_version": None,
        "service_instance_id": None,
        "environment": "production",
        "start_time": datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        "end_time": datetime(2026, 8, 26, 12, 0, 1, tzinfo=UTC),
        "attributes": {},
    }
    defaults.update(overrides)
    return RuntimeSpan(**defaults)


def test_declared_call_reuses_the_real_declared_operation(session):
    # Mirrors examples/order-service/architecture.yaml's real declared CALLS: order-service ->
    # product-service's GET /products/{id} (H4.6: existing OpenAPI operations are reused).
    client = _span(span_id="c1" * 8, span_kind="CLIENT", service_name="OrderService")
    server = _span(
        parent_span_id=client.span_id,
        span_kind="SERVER",
        service_name="ProductService",
        attributes={"http.request.method": "GET", "http.route": "/products/{id}"},
    )

    service_candidates = fetch_candidates(session)
    operation_candidates = fetch_operation_candidates(session)
    batch = correlate_http_call_observations(
        [client, server],
        service_candidates=service_candidates,
        operation_candidates=operation_candidates,
        service_aliases={},
    )

    assert len(batch.facts) == 1
    fact = batch.facts[0]
    assert fact.subject_id == ids.service_id("order-service")
    assert fact.object_id == ids.operation_id(
        ids.service_id("product-service"), "GET", "/products/{id}"
    )
    assert batch.entities == []  # both sides and the operation are all declared - nothing new
    assert batch.unresolved == []


def test_unknown_route_mints_observed_only_operation_against_real_service_data(session):
    client = _span(span_id="c2" * 8, span_kind="CLIENT", service_name="OrderService")
    server = _span(
        parent_span_id=client.span_id,
        span_kind="SERVER",
        service_name="ProductService",
        attributes={"http.request.method": "GET", "http.route": "/internal/products/{id}"},
    )

    service_candidates = fetch_candidates(session)
    operation_candidates = fetch_operation_candidates(session)
    batch = correlate_http_call_observations(
        [client, server],
        service_candidates=service_candidates,
        operation_candidates=operation_candidates,
        service_aliases={},
    )

    # 11H-D: an OBSERVED_ONLY resolution now also earns an observed PROVIDES fact alongside CALLS.
    assert len(batch.facts) == 2
    fact = next(f for f in batch.facts if f.relation_type == "CALLS")
    provider_id = ids.service_id("product-service")
    assert fact.object_id == ids.operation_id(provider_id, "GET", "/internal/products/{id}")
    provides_fact = next(f for f in batch.facts if f.relation_type == "PROVIDES")
    assert provides_fact.subject_id == provider_id
    assert provides_fact.object_id == fact.object_id
    operation_entities = [e for e in batch.entities if e.label == "Operation"]
    assert len(operation_entities) == 1
    assert operation_entities[0].id == fact.object_id

    # nothing written to the graph - Iteration 11C stays read-only, like 11A/11B
    count = session.run(
        "MATCH (o:Operation {id: $id}) RETURN count(o) AS c", id=fact.object_id
    ).single()["c"]
    assert count == 0


def test_fetch_queue_candidates_returns_declared_queues_with_no_namespace(session):
    candidates = fetch_queue_candidates(session)
    by_name = {c.name for c in candidates}
    assert {"payment-q", "invoice-q", "unused-q", "unknown-producer-q"} <= by_name
    assert all(c.namespace is None for c in candidates)


def test_send_observation_reuses_the_real_declared_queue(session):
    # Mirrors examples/order-service/asyncapi.yaml's real declared SENDS: order-service -> payment-q
    # (H4.9: existing AsyncAPI queues are reused).
    span = _span(
        span_id="q1" * 8,
        service_name="OrderService",
        attributes={"messaging.operation.type": "send", "messaging.destination.name": "payment-q"},
    )

    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )

    assert len(batch.facts) == 1
    fact = batch.facts[0]
    assert fact.subject_id == ids.service_id("order-service")
    assert fact.relation_type == "SENDS"
    assert fact.object_id == ids.queue_id("payment-q")
    assert batch.entities == []


def test_unknown_destination_mints_observed_only_queue_against_real_service_data(session):
    # v0.4.1 I2: an undeclared destination with no destination-kind evidence now refuses (default-
    # deny, spec §11) rather than silently minting - explicit kind=queue is what still allows an
    # otherwise-undeclared destination to be recorded here.
    span = _span(
        span_id="q2" * 8,
        service_name="OrderService",
        attributes={
            "messaging.operation.type": "send",
            "messaging.destination.name": "legacy-payment-q",
            "messaging.destination_kind": "queue",
        },
    )

    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )

    assert len(batch.facts) == 1
    fact = batch.facts[0]
    assert fact.object_id == ids.queue_id("legacy-payment-q")
    queue_entities = [e for e in batch.entities if e.label == "Queue"]
    assert len(queue_entities) == 1
    assert queue_entities[0].id == fact.object_id

    # nothing written to the graph - Iteration 11D stays read-only, like 11A-11C
    count = session.run(
        "MATCH (q:Queue {id: $id}) RETURN count(q) AS c", id=fact.object_id
    ).single()["c"]
    assert count == 0


# --- v0.4.1 I2.2: real-Neo4j persistence proof (spec §29) ----------------------------------------
#
# Unlike the tests above (which only exercise correlate_queue_observations in isolation), these
# go all the way through persist_observation_batch against the real, module-shared graph - proving
# that a refused span creates zero new semantic artifacts at the actual persistence boundary, not
# just an empty in-memory ObservationBatch. One positive control proves a guard-approved span still
# persists normally through the same real boundary.


def _assert_no_new_messaging_artifacts(
    session,
    *,
    service_id: str,
    queue_id: str,
    evidence_id: str,
    relation_type: str,
    service_preexists: bool,
    queue_preexists: bool,
) -> None:
    """Spec §29: "The negative assertion SHALL query nodes, Evidence, and SENDS/RECEIVES_FROM" -
    all four artifact types, not just one. `service_preexists`/`queue_preexists` mark an identity
    that was already a real declared node before this span (its node's mere presence isn't itself
    evidence of this span's effect) - that count is expected to stay exactly 1, never duplicated;
    an identity this span's guards refused to mint is expected to stay exactly 0."""
    service_count = session.run(
        "MATCH (s:Service {id: $id}) RETURN count(s) AS c", id=service_id
    ).single()["c"]
    assert service_count == (1 if service_preexists else 0)

    queue_count = session.run(
        "MATCH (q:Queue {id: $id}) RETURN count(q) AS c", id=queue_id
    ).single()["c"]
    assert queue_count == (1 if queue_preexists else 0)

    evidence_count = session.run(
        "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c", id=evidence_id
    ).single()["c"]
    assert evidence_count == 0

    relation_count = session.run(
        f"MATCH (:Service {{id: $sid}})-[r:{relation_type}]->(:Queue {{id: $qid}}) "
        "WHERE $eid IN coalesce(r.evidence_ids, []) RETURN count(r) AS c",
        sid=service_id,
        qid=queue_id,
        eid=evidence_id,
    ).single()["c"]
    assert relation_count == 0


def test_positive_control_declared_span_persists_service_queue_evidence_and_relation(
    driver, session
):
    span = _span(
        span_id="pc1" * 4,
        service_name="OrderService",
        environment="i2-positive-control",
        attributes={"messaging.operation.type": "send", "messaging.destination.name": "payment-q"},
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert len(batch.facts) == 1
    persist_observation_batch(driver, DATABASE, batch)

    evidence_id = batch.facts[0].evidence.id
    evidence_count = session.run(
        "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c", id=evidence_id
    ).single()["c"]
    assert evidence_count == 1

    relation_count = session.run(
        "MATCH (:Service {id: $sid})-[r:SENDS]->(:Queue {id: $qid}) "
        "WHERE $eid IN r.evidence_ids RETURN count(r) AS c",
        sid=ids.service_id("order-service"),
        qid=ids.queue_id("payment-q"),
        eid=evidence_id,
    ).single()["c"]
    assert relation_count == 1


def test_topic_shaped_destination_persists_no_new_artifacts(driver, session):
    span = _span(
        span_id="tp1" * 4,
        service_name="OrderService",
        environment="i2-topic-refusal",
        attributes={
            "messaging.operation.type": "send",
            "messaging.destination.name": "payment-q",
            "messaging.destination_kind": "topic",
        },
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert batch.facts == []
    assert batch.entities == []
    persist_observation_batch(driver, DATABASE, batch)

    would_be_evidence_id = ids.observed_evidence_id(
        span.environment,
        day_bucket(span.end_time)[0],
        ids.service_id("order-service"),
        "SENDS",
        ids.queue_id("payment-q"),
    )
    _assert_no_new_messaging_artifacts(
        session,
        service_id=ids.service_id("order-service"),
        queue_id=ids.queue_id("payment-q"),
        evidence_id=would_be_evidence_id,
        relation_type="SENDS",
        service_preexists=True,  # OrderService is declared - unaffected by this refusal
        queue_preexists=True,  # payment-q is declared - unaffected by this refusal
    )


def test_unresolved_destination_persists_no_new_artifacts(driver, session):
    span = _span(
        span_id="ur1" * 4,
        service_name="OrderService",
        environment="i2-unresolved-refusal",
        attributes={
            "messaging.operation.type": "send",
            "messaging.destination.name": "totally-unrecognized-destination",
        },
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert batch.facts == []
    assert batch.entities == []
    persist_observation_batch(driver, DATABASE, batch)

    would_be_queue_id = ids.queue_id("totally-unrecognized-destination")
    would_be_evidence_id = ids.observed_evidence_id(
        span.environment,
        day_bucket(span.end_time)[0],
        ids.service_id("order-service"),
        "SENDS",
        would_be_queue_id,
    )
    _assert_no_new_messaging_artifacts(
        session,
        service_id=ids.service_id("order-service"),
        queue_id=would_be_queue_id,
        evidence_id=would_be_evidence_id,
        relation_type="SENDS",
        service_preexists=True,  # OrderService is declared - unaffected by this refusal
        queue_preexists=False,  # the destination guard refused to mint this Queue at all
    )


def test_placeholder_service_persists_no_new_artifacts(driver, session):
    span = _span(
        span_id="ph1" * 4,
        service_name="unknown_service",
        environment="i2-placeholder-refusal",
        attributes={"messaging.operation.type": "send", "messaging.destination.name": "payment-q"},
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert batch.facts == []
    assert batch.entities == []
    persist_observation_batch(driver, DATABASE, batch)

    would_be_service_id = ids.service_id("unknown-service")
    would_be_evidence_id = ids.observed_evidence_id(
        span.environment,
        day_bucket(span.end_time)[0],
        would_be_service_id,
        "SENDS",
        ids.queue_id("payment-q"),
    )
    _assert_no_new_messaging_artifacts(
        session,
        service_id=would_be_service_id,
        queue_id=ids.queue_id("payment-q"),
        evidence_id=would_be_evidence_id,
        relation_type="SENDS",
        service_preexists=False,  # the service guard refused to mint this Service at all
        queue_preexists=True,  # payment-q is declared - unaffected by this refusal
    )


def test_ambiguous_service_persists_no_new_artifacts(driver, session):
    # Hand-seeds two declared Services sharing a distinctive, otherwise-unused name - the real
    # examples/ fixture never declares a namespace (spec's own confirmed finding), so an ambiguous
    # same-name collision can't occur from the fixture alone and must be constructed directly.
    # Neither pre-existing candidate id is "the" resolved one (that's the point of "ambiguous") -
    # both are checked explicitly, alongside Evidence and relation absence, per spec §29.
    duplicate_a, duplicate_b = "service:duplicated-role-a", "service:duplicated-role-b"
    session.run(
        "CREATE (:Service {id: $id1, name: $name}) CREATE (:Service {id: $id2, name: $name})",
        id1=duplicate_a,
        id2=duplicate_b,
        name="DuplicatedRoleService",
    )
    span = _span(
        span_id="am1" * 4,
        service_name="DuplicatedRoleService",
        environment="i2-ambiguous-refusal",
        attributes={"messaging.operation.type": "send", "messaging.destination.name": "payment-q"},
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert batch.facts == []
    assert batch.entities == []
    persist_observation_batch(driver, DATABASE, batch)

    payment_q = ids.queue_id("payment-q")
    payment_q_count = session.run(
        "MATCH (q:Queue {id: $id}) RETURN count(q) AS c", id=payment_q
    ).single()["c"]
    assert payment_q_count == 1  # declared - unaffected by this refusal

    for candidate_id in (duplicate_a, duplicate_b):
        would_be_evidence_id = ids.observed_evidence_id(
            span.environment, day_bucket(span.end_time)[0], candidate_id, "SENDS", payment_q
        )
        evidence_count = session.run(
            "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c", id=would_be_evidence_id
        ).single()["c"]
        assert evidence_count == 0
        relation_count = session.run(
            "MATCH (:Service {id: $sid})-[r:SENDS]->(:Queue {id: $qid}) "
            "WHERE $eid IN coalesce(r.evidence_ids, []) RETURN count(r) AS c",
            sid=candidate_id,
            qid=payment_q,
            eid=would_be_evidence_id,
        ).single()["c"]
        assert relation_count == 0


def test_both_guards_failing_persists_no_new_artifacts(driver, session):
    span = _span(
        span_id="bf1" * 4,
        service_name="unknown_service",
        environment="i2-both-guards-failing",
        attributes={
            "messaging.operation.type": "send",
            "messaging.destination.name": "payment-q",
            "messaging.destination_kind": "topic",
        },
    )
    service_candidates = fetch_candidates(session)
    queue_candidates = fetch_queue_candidates(session)
    batch = correlate_queue_observations(
        [span],
        service_candidates=service_candidates,
        queue_candidates=queue_candidates,
        service_aliases={},
        queue_aliases={},
    )
    assert batch.facts == []
    assert batch.entities == []
    # Destination-first precedence (spec §6): exactly one reason, the destination's.
    assert [u.reason for u in batch.unresolved] == [UNSUPPORTED_DESTINATION_SEMANTICS]
    persist_observation_batch(driver, DATABASE, batch)

    would_be_service_id = ids.service_id("unknown-service")
    would_be_evidence_id = ids.observed_evidence_id(
        span.environment,
        day_bucket(span.end_time)[0],
        would_be_service_id,
        "SENDS",
        ids.queue_id("payment-q"),
    )
    _assert_no_new_messaging_artifacts(
        session,
        service_id=would_be_service_id,
        queue_id=ids.queue_id("payment-q"),
        evidence_id=would_be_evidence_id,
        relation_type="SENDS",
        service_preexists=False,  # never reached - destination refused first - but still unminted
        queue_preexists=True,  # payment-q is declared - unaffected by this refusal
    )
