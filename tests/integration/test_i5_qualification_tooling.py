"""v0.5.0 I5 Slice 1: the qualification tooling against real Neo4j (I5 §3 gaps 1-3, §7).

- Capture covers every admitted endpoint-label pair, and `PUBLISHES_TO` carries runtime status.
- `DEPLOYED_AS` outcomes are captured only through the public deployment projection.
- The evaluator's reference snapshot reproduces production canonicalization v3 exactly.

The graphs come from the real importer, telemetry and Kubernetes paths, reusing the I3 and I4
fixtures.
"""

from pathlib import Path

import yaml

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.importer import import_all_sources
from app.sources.model import FilesystemSourceConfig
from evaluation.architecture_answers.reference import snapshot as reference_snapshot
from real_world_validation.capture import (
    capture_actual_facts,
    capture_deployment_facts,
    write_actual_facts,
)
from real_world_validation.comparator import compare
from real_world_validation.loader import load_actual, load_actual_deployments, load_expected
from real_world_validation.model import ScopeDeclaration, WorkloadKey
from tests.integration import test_i3_cross_source_qualification as i3
from tests.integration.test_pubsub_persistence import _pubsub_scene
from tests.integration.test_pubsub_runtime import SPAN_TIME, _ingest, _span

DATABASE = "neo4j"
EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
PUBSUB_SERVICES = ("service:orders", "service:billing", "service:shipping")
EXAMPLE_SERVICES = ("service:order-service", "service:payment-service", "service:invoice-service")


def _wipe(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _import(driver, root: Path, source_id: str) -> None:
    stats = import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(id=source_id, root=root),
    )
    assert stats.committed is True


def _queue_and_pubsub_graph(driver, tmp_path: Path) -> None:
    """The examples' Queue topology plus the I4 Topic/Subscription scene, in one graph."""
    _wipe(driver)
    _import(driver, EXAMPLES_DIR, "i5-tooling-examples")
    _pubsub_scene(tmp_path / "pubsub")
    _import(driver, tmp_path / "pubsub", "i5-tooling-pubsub")


def _capture(driver, entities) -> list:
    with driver.session(database=DATABASE) as session:
        return capture_actual_facts(
            session,
            scope=ScopeDeclaration(entities=tuple(entities)),
            environment="production",
            since=SPAN_TIME.replace(hour=0),
            until=SPAN_TIME.replace(hour=23),
        )


def _targets(facts, relation_type: str) -> set[str]:
    return {f.target.split(":")[0] for f in facts if f.type == relation_type}


def _sources(facts, relation_type: str) -> set[str]:
    return {f.source.split(":")[0] for f in facts if f.type == relation_type}


# --- §3 gap 1: every admitted endpoint-label pair ----------------------------------------------


def test_capture_includes_both_labels_of_multi_label_relations(driver, tmp_path):
    _queue_and_pubsub_graph(driver, tmp_path)

    services = EXAMPLE_SERVICES + PUBSUB_SERVICES
    facts = _capture(driver, services)
    # CARRIES has no Service endpoint, so scope the destinations the services send/publish to.
    destinations = sorted({f.target for f in facts if f.type in {"SENDS", "PUBLISHES_TO"}})
    destination_facts = _capture(driver, destinations)

    # RECEIVES_FROM targets Queue | Subscription, and CARRIES leaves Queue | Topic. The old
    # `next(iter(frozenset))` captured only one label of each, depending on the hash seed.
    assert _targets(facts, "RECEIVES_FROM") == {"queue", "subscription"}
    assert _sources(destination_facts, "CARRIES") == {"queue", "topic"}


# --- §3 gap 2: PUBLISHES_TO and RECEIVES_FROM -> Subscription runtime status --------------------


def _status(facts, relation_type: str, source: str, target_prefix: str) -> str:
    [fact] = [
        f
        for f in facts
        if f.type == relation_type and f.source == source and f.target.startswith(target_prefix)
    ]
    return fact.status


def test_pubsub_relations_carry_runtime_status(driver, tmp_path):
    _queue_and_pubsub_graph(driver, tmp_path)
    before = _capture(driver, PUBSUB_SERVICES)
    assert _status(before, "PUBLISHES_TO", "service:orders", "topic:") == "NOT_OBSERVED_IN_WINDOW"
    assert (
        _status(before, "RECEIVES_FROM", "service:billing", "subscription:")
        == "NOT_OBSERVED_IN_WINDOW"
    )

    _ingest(
        driver,
        [
            _span("orders", "send", trace="a"),
            _span(
                "billing",
                "process",
                trace="c",
                **{"messaging.destination.subscription.name": "billing"},
            ),
        ],
    )
    after = _capture(driver, PUBSUB_SERVICES)

    assert _status(after, "PUBLISHES_TO", "service:orders", "topic:") == "CONFIRMED"
    assert _status(after, "RECEIVES_FROM", "service:billing", "subscription:") == "CONFIRMED"
    assert (
        _status(after, "RECEIVES_FROM", "service:shipping", "subscription:")
        == "NOT_OBSERVED_IN_WINDOW"
    )


# --- §7: DEPLOYED_AS through the public projection only -----------------------------------------


def _deployment_capture(service, services):
    return capture_deployment_facts(
        service,
        scope=ScopeDeclaration(entities=tuple(services)),
        environment=i3.ENVIRONMENT,
        since=i3.WINDOW_START,
        until=i3.WINDOW_END,
    )


def test_deployment_capture_equals_the_public_resolutions(driver):
    i3._reset_graph(driver)
    i3._declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    i3._import_real_kubernetes_bundle(driver)
    i3._persist_spans(driver, [i3._runtime_demo_span(service_name="runtime-demo")])
    service = i3._service(driver, document=i3._load_mapping("service-workload-mapping-agree.yaml"))

    [fact] = _deployment_capture(service, ["service:runtime-demo"])

    [resolution] = service.get_service_dependencies(
        i3._dependencies_request("service:runtime-demo")
    ).data.deployment_resolutions
    assert fact.service == resolution.service_id == "service:runtime-demo"
    assert fact.workload == WorkloadKey(
        namespace=resolution.workload.namespace,
        kind=resolution.workload.workload_kind.value,
        name=resolution.workload.name,
    )
    assert fact.status == "RESOLVED_EXPLICIT"
    assert fact.supporting_methods == (
        "RESOLVED_EXPLICIT",
        "RESOLVED_CONFIGURED",
        "RESOLVED_OBSERVED",
    )


def test_deployment_capture_reports_conflict_without_a_claim(driver):
    i3._reset_graph(driver)
    i3._declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    i3._declare_service(driver, service_id="service:runtime-demo-alt", name="runtime-demo-alt")
    i3._import_real_kubernetes_bundle(driver)
    service = i3._service(
        driver, document=i3._load_mapping("service-workload-mapping-conflict.yaml")
    )

    facts = _deployment_capture(service, ["service:runtime-demo", "service:runtime-demo-alt"])

    assert facts
    assert {f.status for f in facts} == {"CONFLICT"}


def test_deployment_capture_round_trips_through_the_comparator(driver, tmp_path):
    i3._reset_graph(driver)
    i3._declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    i3._import_real_kubernetes_bundle(driver)
    service = i3._service(driver, document=i3._load_mapping("service-workload-mapping-agree.yaml"))
    deployments = _deployment_capture(service, ["service:runtime-demo"])
    [fact] = deployments
    actual_path = tmp_path / "actual.yaml"
    write_actual_facts(actual_path, [], deployments)

    expected_path = tmp_path / "expected.yaml"
    workload = {"namespace": fact.workload.namespace, "kind": fact.workload.kind}
    expected_path.write_text(
        yaml.safe_dump(
            {
                "system": "tooling",
                "upstream_revision": "n/a",
                "scope": {"entities": ["service:runtime-demo"]},
                "expected": {
                    "deployments": [
                        {
                            "id": "deploy",
                            "service": "service:runtime-demo",
                            "workload": {**workload, "name": fact.workload.name},
                            "status": "RESOLVED_EXPLICIT",
                            "supporting_methods": ["RESOLVED_EXPLICIT", "RESOLVED_CONFIGURED"],
                        }
                    ]
                },
                "forbidden": {
                    "deployments": [
                        {
                            "id": "no-name-only",
                            "service": "service:runtime-demo",
                            "workload": {**workload, "name": "no-such-workload"},
                        }
                    ]
                },
            }
        )
    )

    findings = compare(
        load_expected(expected_path), load_actual(actual_path), load_actual_deployments(actual_path)
    )

    assert {(f.id, f.classification) for f in findings} == {
        ("deploy", "CORRECT"),
        ("no-name-only", "CORRECT"),
    }


# --- §3 gap 3 / §12: reference canonicalization reproduces production v3 -------------------------


def _fingerprints(driver, *, document=None) -> tuple[tuple[str, str], tuple[str, str]]:
    artifact = (
        reference_snapshot.MappingArtifactIdentity(
            artifact_id=document.artifact_id,
            artifact_revision=document.artifact_revision,
            content_digest=document.content_digest,
        )
        if document is not None
        else None
    )
    with driver.session(database=DATABASE) as session:
        production = snapshot_fingerprint(
            canonical_snapshot_state(
                session,
                coverage_qualification_enabled=True,
                service_workload_mapping_document=document,
            )
        )
        reference = reference_snapshot.fingerprint(
            session, coverage_qualification_enabled=True, mapping_artifact=artifact
        )
    return production, reference


def test_reference_snapshot_matches_production_on_queue_and_pubsub_graphs(driver, tmp_path):
    _wipe(driver)
    _import(driver, EXAMPLES_DIR, "i5-tooling-examples")
    production, reference = _fingerprints(driver)
    assert reference == production

    _queue_and_pubsub_graph(driver, tmp_path)
    _ingest(driver, [_span("orders", "send", trace="a")])
    production, reference = _fingerprints(driver)
    assert reference == production


def test_reference_snapshot_matches_production_on_deployment_graphs(driver):
    i3._reset_graph(driver)
    i3._declare_service(driver, service_id="service:runtime-demo", name="runtime-demo")
    i3._import_real_kubernetes_bundle(driver)
    i3._persist_spans(driver, [i3._runtime_demo_span(service_name="runtime-demo")])

    production, reference = _fingerprints(driver)
    assert reference == production

    document = i3._load_mapping("service-workload-mapping-agree.yaml")
    production_with, reference_with = _fingerprints(driver, document=document)
    assert reference_with == production_with
    # the mapping artifact is genuinely bound: it moves the snapshot
    assert production_with != production


def test_reference_snapshot_is_canonicalization_version_3(driver):
    _wipe(driver)
    with driver.session(database=DATABASE) as session:
        state = reference_snapshot.canonical_state(session, coverage_qualification_enabled=True)
    assert state["version"] == 3
    assert state["topics"] == [] and state["subscriptions"] == []
    with driver.session(database=DATABASE) as session:
        first = reference_snapshot.fingerprint(session, coverage_qualification_enabled=True)
        second = reference_snapshot.fingerprint(session, coverage_qualification_enabled=True)
    assert first == second
