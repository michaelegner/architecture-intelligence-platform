"""I1.3 exit condition: the REST CONFIRMED scenario passes end-to-end (setup -> canonical
projection -> comparison), using evaluation.runner.run_scenario against a real Neo4j.

Also covers the I1 post-merge review's F1 regression: the projector must classify status at true
canonical (type, source, target) identity, not just (source, type) - otherwise two same-type edges
from the same source silently share one status.
"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from app.canonical import ids
from app.graph.importer import import_all_sources
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate
from evaluation.loader import load_scenario
from evaluation.model import ScenarioScope
from evaluation.projector import load_relation_facts
from evaluation.runner import reset_graph, run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "scenarios"
DATABASE = "neo4j"
SINCE = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


@pytest.fixture
def session(driver):
    with driver.session(database=DATABASE) as s:
        yield s


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


def test_rest_confirmed_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "01-rest-confirmed")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_wrong_expectation_is_reported_as_a_semantic_mismatch_not_a_pass(driver, tmp_path):
    """Sanity-break control: mutating the real scenario's expected status must turn this into a
    reported FAIL, proving the comparison is actually discriminating rather than vacuously true."""
    broken_dir = tmp_path / "01-rest-confirmed-broken"
    shutil.copytree(SCENARIOS_DIR / "01-rest-confirmed", broken_dir)
    expected_file = broken_dir / "expected.yaml"
    data = yaml.safe_load(expected_file.read_text())
    data["expected"]["relations"][0]["status"] = "OBSERVED_ONLY"
    expected_file.write_text(yaml.safe_dump(data))

    scenario = load_scenario(broken_dir)
    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert not result.passed
    assert len(result.mismatches) == 1
    assert result.mismatches[0].kind == "semantic_mismatch"
    assert result.mismatches[0].actual.status == "CONFIRMED"


# --- I2 scenarios: orphan messaging, mixed REST+async, request/response queue pair --------------


def test_orphan_messaging_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "04-orphan-messaging")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_mixed_rest_async_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "05-mixed-rest-async")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_request_response_queue_pair_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "06-request-response-queue-pair")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_forbidding_a_fact_that_is_actually_present_fails_the_scenario(driver, tmp_path):
    """Sanity-break control for the forbidden-fact path: re-declaring one of the request/response
    scenario's real, present facts (SENDS order-service->request-q) as forbidden instead of
    expected must turn it into a reported FORBIDDEN_PRESENT FAIL, proving forbidden-fact
    enforcement actually discriminates rather than being vacuously true."""
    broken_dir = tmp_path / "06-request-response-queue-pair-broken"
    shutil.copytree(SCENARIOS_DIR / "06-request-response-queue-pair", broken_dir)
    expected_file = broken_dir / "expected.yaml"
    data = yaml.safe_load(expected_file.read_text())
    data["expected"]["relations"] = [
        r
        for r in data["expected"]["relations"]
        if not (r["type"] == "SENDS" and r["target"] == "queue:request-q")
    ]
    data["forbidden"]["relations"] = [
        {"type": "SENDS", "source": "service:order-service", "target": "queue:request-q"}
    ]
    expected_file.write_text(yaml.safe_dump(data))

    scenario = load_scenario(broken_dir)
    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert not result.passed
    assert len(result.mismatches) == 1
    assert result.mismatches[0].kind == "forbidden_present"
    assert result.mismatches[0].actual.target == "queue:request-q"


# --- F1 regression: status must be classified per (type, source, target), not per (source, type) ---


def test_two_sends_edges_from_the_same_service_get_independent_status(driver, session, tmp_path):
    reset_graph(driver, database=DATABASE)
    declarations = tmp_path / "declarations" / "order-service"
    declarations.mkdir(parents=True)
    (declarations / "asyncapi.yaml").write_text(
        "asyncapi: '2.6.0'\n"
        'info:\n  title: OrderService\n  version: "1.0.0"\n'
        "channels:\n"
        "  queue-a:\n"
        "    publish:\n      operationId: sendA\n      message:\n"
        "        $ref: '#/components/messages/MsgA'\n"
        "  queue-b:\n"
        "    publish:\n      operationId: sendB\n      message:\n"
        "        $ref: '#/components/messages/MsgB'\n"
        "components:\n  messages:\n"
        "    MsgA:\n      name: MsgA\n      payload:\n        type: object\n"
        "    MsgB:\n      name: MsgB\n      payload:\n        type: object\n"
    )
    import_all_sources(driver, database=DATABASE, root=tmp_path / "declarations")

    subject_id = ids.service_id("order-service")
    queue_a = ids.queue_id("queue-a")
    queue_b = ids.queue_id("queue-b")
    environment = "f1-sends-env"

    # Only queue-a is observed -> CONFIRMED. queue-b stays declared-only (not classified by I1) -
    # the bug this regresses previously labeled it CONFIRMED too, since it shared queue-a's
    # (source, type) key.
    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            entities=[],
            facts=[
                _observed_fact(
                    subject_id=subject_id,
                    relation_type="SENDS",
                    object_id=queue_a,
                    environment=environment,
                    timestamp=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            ],
        ),
    )

    scope = ScenarioScope(entities=(subject_id, queue_a, queue_b))
    facts = load_relation_facts(session, scope=scope, environment=environment, since=SINCE)

    fact_a = next(f for f in facts if f.target == queue_a)
    fact_b = next(f for f in facts if f.target == queue_b)
    assert fact_a.status == "CONFIRMED"
    assert fact_b.status != "CONFIRMED"


def test_two_receives_from_edges_from_the_same_service_get_independent_status(
    driver, session, tmp_path
):
    reset_graph(driver, database=DATABASE)
    declarations = tmp_path / "declarations" / "inventory-service"
    declarations.mkdir(parents=True)
    (declarations / "asyncapi.yaml").write_text(
        "asyncapi: '2.6.0'\n"
        'info:\n  title: InventoryService\n  version: "1.0.0"\n'
        "channels:\n"
        "  queue-c:\n"
        "    subscribe:\n      operationId: receiveC\n      message:\n"
        "        $ref: '#/components/messages/MsgC'\n"
        "  queue-d:\n"
        "    subscribe:\n      operationId: receiveD\n      message:\n"
        "        $ref: '#/components/messages/MsgD'\n"
        "components:\n  messages:\n"
        "    MsgC:\n      name: MsgC\n      payload:\n        type: object\n"
        "    MsgD:\n      name: MsgD\n      payload:\n        type: object\n"
    )
    import_all_sources(driver, database=DATABASE, root=tmp_path / "declarations")

    subject_id = ids.service_id("inventory-service")
    queue_c = ids.queue_id("queue-c")
    queue_d = ids.queue_id("queue-d")
    environment = "f1-receives-env"

    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            entities=[],
            facts=[
                _observed_fact(
                    subject_id=subject_id,
                    relation_type="RECEIVES_FROM",
                    object_id=queue_c,
                    environment=environment,
                    timestamp=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            ],
        ),
    )

    scope = ScenarioScope(entities=(subject_id, queue_c, queue_d))
    facts = load_relation_facts(session, scope=scope, environment=environment, since=SINCE)

    fact_c = next(f for f in facts if f.target == queue_c)
    fact_d = next(f for f in facts if f.target == queue_d)
    assert fact_c.status == "CONFIRMED"
    assert fact_d.status != "CONFIRMED"


def test_a_caller_with_multiple_calls_targets_gets_independent_status_per_target(
    driver, session, tmp_path
):
    """Also proves the target identity is the raw Operation id, not coalesced through PROVIDES to
    the provider service - the second half of the F1 finding."""
    reset_graph(driver, database=DATABASE)
    root = tmp_path / "declarations"
    order_dir = root / "order-service"
    product_dir = root / "product-service"
    order_dir.mkdir(parents=True)
    product_dir.mkdir(parents=True)

    (product_dir / "openapi.yaml").write_text(
        "openapi: 3.1.0\n"
        'info:\n  title: ProductService\n  version: "1.0.0"\n'
        "paths:\n"
        "  /a:\n    get:\n      operationId: getA\n      responses:\n"
        '        "200":\n          description: ok\n'
        "  /b:\n    get:\n      operationId: getB\n      responses:\n"
        '        "200":\n          description: ok\n'
    )
    (order_dir / "openapi.yaml").write_text(
        'openapi: 3.1.0\ninfo:\n  title: OrderService\n  version: "1.0.0"\npaths: {}\n'
    )
    (order_dir / "architecture.yaml").write_text(
        "service: order-service\n"
        "calls:\n"
        "  - service: product-service\n    operationId: getA\n"
        "  - service: product-service\n    operationId: getB\n"
    )
    import_all_sources(driver, database=DATABASE, root=root)

    subject_id = ids.service_id("order-service")
    provider_id = ids.service_id("product-service")
    operation_a = ids.operation_id(provider_id, "GET", "/a")
    operation_b = ids.operation_id(provider_id, "GET", "/b")
    environment = "f1-calls-env"

    # Only GET /a is observed -> CONFIRMED. GET /b stays declared-only.
    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(
            entities=[],
            facts=[
                _observed_fact(
                    subject_id=subject_id,
                    relation_type="CALLS",
                    object_id=operation_a,
                    environment=environment,
                    timestamp=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
                )
            ],
        ),
    )

    scope = ScenarioScope(
        entities=(subject_id, operation_a, operation_b), relation_types=("CALLS",)
    )
    facts = load_relation_facts(session, scope=scope, environment=environment, since=SINCE)

    fact_a = next(f for f in facts if f.target == operation_a)
    fact_b = next(f for f in facts if f.target == operation_b)
    assert fact_a.status == "CONFIRMED"
    assert fact_a.target == operation_a  # raw Operation id, not the provider id
    assert fact_b.status != "CONFIRMED"


# --- I3: NOT_OBSERVED_IN_WINDOW -----------------------------------------------------------------


def test_not_observed_in_window_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "07-not-observed-in-window")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_window_including_the_observation_reclassifies_it_as_confirmed(driver, tmp_path):
    """I3 spec §8.5 window sanity-break: scenario 07's runtime fixture is deliberately outside its
    selected window. Widening the window to include it must flip the classification to CONFIRMED,
    proving NOT_OBSERVED_IN_WINDOW isn't produced by simply ignoring OBSERVED evidence."""
    widened_dir = tmp_path / "07-not-observed-in-window-widened"
    shutil.copytree(SCENARIOS_DIR / "07-not-observed-in-window", widened_dir)
    expected_file = widened_dir / "expected.yaml"
    data = yaml.safe_load(expected_file.read_text())
    data["observation"]["window"] = {
        "start": "2026-08-01T09:00:00Z",
        "end": "2026-08-01T10:00:00Z",
    }
    data["expected"]["relations"][0]["status"] = "CONFIRMED"
    data["expected"]["relations"][0]["evidence"] = {"declared": True, "observed": True}
    expected_file.write_text(yaml.safe_dump(data))

    scenario = load_scenario(widened_dir)
    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()
