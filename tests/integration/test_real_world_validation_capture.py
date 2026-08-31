"""I2.3: real_world_validation/capture.py against a real Neo4j, using the real
app.graph.importer/app.telemetry.aggregator paths - never a hand-written Cypher shortcut.

Mirrors tests/integration/test_evaluation_projector.py's fixture style (this is the same query
shape adapted for real_world_validation's own ScopeDeclaration/RelationFact, I1 §"three similar
lines beats a premature abstraction" precedent - the two projectors stay independent).
"""

from datetime import UTC, datetime

from app.canonical import ids
from app.graph.importer import import_all_sources
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate
from real_world_validation.capture import capture_actual_facts
from real_world_validation.model import ScopeDeclaration

DATABASE = "neo4j"
SINCE = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


def _reset_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _observed_fact(
    *, subject_id: str, relation_type: str, object_id: str, environment: str, timestamp: datetime
) -> ObservedFactCandidate:
    bucket_start = datetime(timestamp.year, timestamp.month, timestamp.day, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(
            environment, bucket_start, subject_id, relation_type, object_id
        ),
        environment=environment,
        bucket_start=bucket_start,
        bucket_end=bucket_start,
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


def _import_fights_heroes(driver, tmp_path):
    root = tmp_path / "declarations"
    fights_dir = root / "rest-fights"
    heroes_dir = root / "rest-heroes"
    fights_dir.mkdir(parents=True)
    heroes_dir.mkdir(parents=True)

    (heroes_dir / "openapi.yaml").write_text(
        'openapi: 3.1.0\ninfo:\n  title: Hero API\n  version: "1.0"\npaths:\n'
        "  /api/heroes/random:\n    get:\n      operationId: getRandomHero\n      responses:\n"
        '        "200":\n          description: ok\n'
    )
    (fights_dir / "openapi.yaml").write_text(
        'openapi: 3.1.0\ninfo:\n  title: Fights API\n  version: "1.0"\npaths: {}\n'
    )
    (fights_dir / "architecture.yaml").write_text(
        "service: rest-fights\ncalls:\n  - service: rest-heroes\n    operationId: getRandomHero\n"
    )
    import_all_sources(driver, database=DATABASE, root=root)

    return (
        ids.service_id("rest-fights"),
        ids.service_id("rest-heroes"),
        ids.operation_id(ids.service_id("rest-heroes"), "GET", "/api/heroes/random"),
    )


def test_declared_only_call_is_not_observed_in_window(driver, tmp_path):
    _reset_graph(driver)
    fights_id, heroes_id, operation_id = _import_fights_heroes(driver, tmp_path)
    scope = ScopeDeclaration(entities=(fights_id, heroes_id))

    with driver.session(database=DATABASE) as session:
        facts = capture_actual_facts(
            session, scope=scope, environment="capture-test-env", since=SINCE
        )

    calls_fact = next(f for f in facts if f.type == "CALLS")
    assert calls_fact.source == fights_id
    assert calls_fact.target == operation_id
    assert calls_fact.status == "NOT_OBSERVED_IN_WINDOW"
    assert calls_fact.declared_evidence is True
    assert calls_fact.observed_evidence is False


def test_provides_facts_get_declared_evidence_but_no_status(driver, tmp_path):
    """PR #41 review F1: every relation app/ingestion/openapi_adapter.py produces carries a real
    DECLARED Provenance/evidence_ids entry, PROVIDES included - capture.py must report that, not
    treat PROVIDES as evidence-less. PROVIDES still gets no `status` (AIP's own
    app.analysis.runtime module defines runtime-observation status only for
    CALLS/SENDS/RECEIVES_FROM)."""
    _reset_graph(driver)
    fights_id, heroes_id, operation_id = _import_fights_heroes(driver, tmp_path)
    scope = ScopeDeclaration(entities=(fights_id, heroes_id))

    with driver.session(database=DATABASE) as session:
        facts = capture_actual_facts(
            session, scope=scope, environment="capture-test-env", since=SINCE
        )

    provides_fact = next(f for f in facts if f.type == "PROVIDES")
    assert provides_fact.source == heroes_id
    assert provides_fact.target == operation_id
    assert provides_fact.status is None
    assert provides_fact.declared_evidence is True
    assert provides_fact.observed_evidence is False


def test_observed_call_is_confirmed(driver, tmp_path):
    _reset_graph(driver)
    fights_id, heroes_id, operation_id = _import_fights_heroes(driver, tmp_path)
    environment = "capture-confirmed-env"
    timestamp = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            entities=[],
            facts=[
                _observed_fact(
                    subject_id=fights_id,
                    relation_type="CALLS",
                    object_id=operation_id,
                    environment=environment,
                    timestamp=timestamp,
                )
            ],
        ),
    )

    scope = ScopeDeclaration(entities=(fights_id, heroes_id))
    with driver.session(database=DATABASE) as session:
        facts = capture_actual_facts(
            session,
            scope=scope,
            environment=environment,
            since=SINCE,
            until=datetime(2026, 8, 2, tzinfo=UTC),
        )

    calls_fact = next(f for f in facts if f.type == "CALLS")
    assert calls_fact.status == "CONFIRMED"
    assert calls_fact.declared_evidence is True
    assert calls_fact.observed_evidence is True


def test_request_schema_relation_is_captured_with_declared_evidence(driver, tmp_path):
    """PR #41 review F2: capture.py must cover AIP's complete canonical relation vocabulary, not
    silently omit types outside CALLS/PROVIDES/SENDS/RECEIVES_FROM. REQUEST_SCHEMA (Operation ->
    Schema) is produced by app/ingestion/openapi_adapter.py whenever an operation declares a
    requestBody schema."""
    _reset_graph(driver)
    root = tmp_path / "declarations" / "rest-heroes"
    root.mkdir(parents=True)
    (root / "openapi.yaml").write_text(
        'openapi: 3.1.0\ninfo:\n  title: Hero API\n  version: "1.0"\n'
        "paths:\n"
        "  /api/heroes:\n"
        "    post:\n"
        "      operationId: createHero\n"
        "      requestBody:\n"
        "        content:\n"
        "          application/json:\n"
        "            schema:\n"
        "              $ref: '#/components/schemas/Hero'\n"
        "      responses:\n"
        '        "200":\n          description: ok\n'
        "components:\n"
        "  schemas:\n"
        "    Hero:\n      type: object\n"
    )
    import_all_sources(driver, database=DATABASE, root=tmp_path / "declarations")

    heroes_id = ids.service_id("rest-heroes")
    operation_id = ids.operation_id(heroes_id, "POST", "/api/heroes")
    scope = ScopeDeclaration(entities=(heroes_id, operation_id))

    with driver.session(database=DATABASE) as session:
        facts = capture_actual_facts(
            session, scope=scope, environment="capture-test-env", since=SINCE
        )

    schema_fact = next(f for f in facts if f.type == "REQUEST_SCHEMA")
    assert schema_fact.source == operation_id
    assert schema_fact.status is None
    assert schema_fact.declared_evidence is True
    assert schema_fact.observed_evidence is False


def test_scope_excludes_facts_outside_declared_entities(driver, tmp_path):
    _reset_graph(driver)
    fights_id, _heroes_id, _operation_id = _import_fights_heroes(driver, tmp_path)
    narrow_scope = ScopeDeclaration(entities=(fights_id,))  # heroes_id deliberately omitted

    with driver.session(database=DATABASE) as session:
        facts = capture_actual_facts(
            session, scope=narrow_scope, environment="capture-test-env", since=SINCE
        )

    # rest-fights CALLS the heroes operation - source (fights_id) keeps it in scope even without
    # heroes_id. The heroes PROVIDES fact (source=heroes_id, target=operation) has neither endpoint
    # in the narrowed scope and must be excluded.
    assert any(f.type == "CALLS" for f in facts)
    assert not any(f.type == "PROVIDES" for f in facts)
