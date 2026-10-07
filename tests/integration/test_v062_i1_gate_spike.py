"""v0.6.2 I1: the G1-G5 gate spike, executed against the real v0.6.1 code on real Neo4j.

Characterization tests (spec §3.2; plan "observe, then characterize"): each test freezes the
behavior v0.6.1 actually exhibits for the Pitstop-shaped world, so a gate that ends FAIL or
PASS-WITH-LIMITS is still a green test that proves the limitation. The verdicts live in
`docs/specifications/0.6.2/i1-spike-finding.md`; this module is its evidence, not an acceptance gate
for the v0.6.2 demo.

World: nine operator-authored AsyncAPI 2.6.0 overlays (`tests/fixtures/pitstop_spike/overlay`) - four
publishers and five subscribers of one fanout exchange `Pitstop` (Topic) on one broker, each
subscriber naming its queue (Subscription). Runtime evidence is injected as `RuntimeSpan`s through the
same adapter/aggregator the OTLP endpoint uses, with frozen timestamps (no wall clock).
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_all_sources
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import DiagnosticCode, FilesystemSourceConfig
from app.telemetry.adapter import adapt
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import RuntimeSpan
from app.telemetry.pubsub_resolver import fetch_subscription_candidates, fetch_topic_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates
from tests.integration.test_broker_architecture_intelligence import PRODUCER
from tests.support.answer_schemas import validate_dependencies

DATABASE = "neo4j"
ROOT = Path(__file__).resolve().parents[2]
OVERLAY = ROOT / "tests" / "fixtures" / "pitstop_spike" / "overlay"
ENV = "pitstop-spike"
DAY_1 = datetime(2026, 10, 6, 12, 0, 0, tzinfo=UTC)
DAY_2 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=UTC)
FULL_DAY = {
    "environment": ENV,
    "window_start": "2026-10-06T00:00:00Z",
    "window_end": "2026-10-06T23:59:59Z",
}
SHORT_WINDOW = {
    "environment": ENV,
    "window_start": "2026-10-06T11:59:00Z",
    "window_end": "2026-10-06T12:01:00Z",
}
PUBLISHER = "service:workshop-management-api"
BROKER = "rabbitmq:pitstop-rabbitmq"
SUBSCRIPTIONS = {
    "AuditlogService": "Auditlog",
    "InvoiceService": "Invoicing",
    "NotificationService": "Notifications",
    "ReportingService": "Reporting",
    "WorkshopManagementEventHandler": "WorkshopManagement",
}
PUBLISHER_NAMES = {
    "WorkshopManagementAPI",
    "CustomerManagementAPI",
    "VehicleManagementAPI",
    "TimeService",
}


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


# --- helpers ----------------------------------------------------------------------------------------


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _import(driver, root: Path):
    return import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(id="pitstop-spike", root=root),
    )


def _variant(tmp_path: Path, **edits) -> Path:
    """A copy of the overlay in which the named service documents are edited by the given callables."""
    root = tmp_path / "overlay"
    shutil.copytree(OVERLAY, root)
    for service_dir, edit in edits.items():
        path = root / service_dir.replace("_", "-") / "asyncapi.yaml"
        document = yaml.safe_load(path.read_text())
        edit(document)
        path.write_text(yaml.safe_dump(document, sort_keys=False))
    return root


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]


def _names(driver, query: str) -> set[str]:
    with driver.session(database=DATABASE) as session:
        return {r["n"] for r in session.run(query)}


def _wipe(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _span(
    service: str,
    operation: str,
    *,
    when: datetime = DAY_1,
    env: str | None = ENV,
    trace: str = "a",
    **attributes,
) -> RuntimeSpan:
    return RuntimeSpan(
        trace_id=trace * 32,
        span_id="b" * 16,
        parent_span_id=None,
        span_name="Pitstop",
        span_kind="PRODUCER" if operation == "send" else "CONSUMER",
        service_name=service,
        service_namespace=None,
        service_version=None,
        service_instance_id=None,
        environment=env,
        start_time=when,
        end_time=when,
        attributes={
            "messaging.system": "rabbitmq",
            "messaging.operation.type": operation,
            "messaging.destination.name": "Pitstop",
            **attributes,
        },
    )


def _send(service: str = "WorkshopManagementAPI", **kwargs) -> RuntimeSpan:
    attributes = kwargs.pop("attributes", {})
    return _span(service, "send", **attributes, **kwargs)


def _receive(service: str, queue: str | None, **kwargs) -> RuntimeSpan:
    attributes = kwargs.pop("attributes", {})
    if queue is not None:
        attributes = {"messaging.destination.subscription.name": queue, **attributes}
    return _span(service, "process", **attributes, **kwargs)


def _ingest(driver, spans):
    with driver.session(database=DATABASE) as session:
        batch = adapt(
            spans,
            service_candidates=fetch_candidates(session),
            operation_candidates=[],
            queue_candidates=fetch_queue_candidates(session),
            service_aliases={},
            queue_aliases={},
            topic_candidates=fetch_topic_candidates(session),
            subscription_candidates=fetch_subscription_candidates(session),
        )
    persist_observation_batch(driver, DATABASE, batch)
    return batch


def _ask(driver, service_id: str = PUBLISHER, context: dict = FULL_DAY):
    answer = _service(driver).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {"service_id": service_id, "observation_context": context}
        )
    )
    validate_dependencies(json.loads(answer.model_dump_json()))
    return answer


def _dependency_claims(answer) -> dict[str, object]:
    return {c.object.name: c for c in answer.claims if hasattr(c, "delivery")}


def _broker_claims(answer) -> list:
    return [c for c in answer.claims if not hasattr(c, "delivery")]


def _qualifications(answer) -> dict[str, str]:
    return {name: c.qualification.value for name, c in _dependency_claims(answer).items()}


def _resolution_refs(answer, name: str) -> list[str]:
    return list(_dependency_claims(answer)[name].resolution_evidence_refs)


def _snapshot_id(driver) -> str:
    with driver.session(database=DATABASE) as session:
        return snapshot_fingerprint(
            canonical_snapshot_state(session, coverage_qualification_enabled=False)
        )[0]


def _full_claims(answer) -> list[dict]:
    """The complete claim set, not a filtered summary."""
    return json.loads(answer.model_dump_json())["claims"]


# --- G1: declare the fanout exchange as a Topic and five named queues as Subscriptions ----------------


def test_g1_overlay_declares_one_topic_one_broker_five_named_subscriptions(driver):
    stats = _import(driver, OVERLAY)

    assert stats.committed is True
    assert stats.diagnostics == ()
    assert _names(driver, "MATCH (t:Topic) RETURN t.name AS n") == {"Pitstop"}
    assert _names(driver, "MATCH (s:Subscription) RETURN s.name AS n") == set(
        SUBSCRIPTIONS.values()
    )
    assert _count(driver, "MATCH (b:Broker) RETURN count(b) AS c") == 1
    assert _count(driver, "MATCH ()-[r:USES_BROKER]->() RETURN count(r) AS c") == 9
    assert _count(driver, "MATCH ()-[r:SUBSCRIPTION_OF]->(:Topic) RETURN count(r) AS c") == 5
    assert _count(driver, "MATCH (:Service)-[r:PUBLISHES_TO]->(:Topic) RETURN count(r) AS c") == 4
    assert (
        _count(driver, "MATCH (:Service)-[r:RECEIVES_FROM]->(:Subscription) RETURN count(r) AS c")
        == 5
    )
    # nothing receives from the Topic itself: receipt is only ever through a named Subscription
    assert _count(driver, "MATCH (:Service)-[r:RECEIVES_FROM]->(:Topic) RETURN count(r) AS c") == 0
    assert _names(driver, "MATCH (x:Service) RETURN x.name AS n") == (
        PUBLISHER_NAMES | set(SUBSCRIPTIONS)
    )


def test_g1_one_publisher_without_a_broker_id_rejects_the_whole_import(driver, tmp_path):
    def drop_broker_id(document):
        del document["servers"]["pitstop-rabbitmq"]["x-aip-broker-id"]

    stats = _import(driver, _variant(tmp_path, workshop_management_api=drop_broker_id))

    # that one document is REJECTED_UNSUPPORTED (AMBIGUOUS) and, being one source set, the import
    # commits nothing at all: a single bad overlay file empties the demo's declared topology
    assert DiagnosticCode.AMBIGUOUS in {d.code for d in stats.diagnostics}
    rejected = [r for r in stats.source_results if r.result.value == "REJECTED_UNSUPPORTED"]
    assert [Path(r.locator).parent.name for r in rejected] == ["workshop-management-api"]
    assert stats.committed is False
    assert _count(driver, "MATCH (n) RETURN count(n) AS c") == 0


def test_g1_a_subscriber_without_a_queue_name_gets_no_subscription(driver, tmp_path):
    def drop_queue_name(document):
        del document["channels"]["Pitstop"]["subscribe"]["x-aip-subscription-name"]

    stats = _import(driver, _variant(tmp_path, reporting_service=drop_queue_name))

    assert DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING in {d.code for d in stats.diagnostics}
    assert _names(driver, "MATCH (s:Subscription) RETURN s.name AS n") == (
        set(SUBSCRIPTIONS.values()) - {"Reporting"}
    )
    assert set(_dependency_claims(_ask(driver))) == set(SUBSCRIPTIONS) - {"ReportingService"}


def test_g1_a_virtual_host_namespaces_the_topic_apart_from_the_other_overlays(driver, tmp_path):
    def add_virtual_host(document):
        document["servers"]["pitstop-rabbitmq"]["bindings"] = {"amqp": {"virtualHost": "/"}}

    _import(driver, _variant(tmp_path, workshop_management_api=add_virtual_host))

    # one Topic per (broker, namespace, address): the fanout exchange splits in two
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 2


# --- G2: receivers are visible in the existing answer and resolve through get_evidence ----------------


def test_g2_publisher_answer_lists_the_five_receivers_through_their_subscriptions(driver):
    _import(driver, OVERLAY)

    answer = _ask(driver)
    claims = _dependency_claims(answer)

    assert answer.schema_version == "0.6"
    assert set(claims) == set(SUBSCRIPTIONS)
    for service_name, queue in SUBSCRIPTIONS.items():
        claim = claims[service_name]
        assert claim.destination_resolution.value == "RESOLVED_SERVICE"
        assert claim.delivery.via.name == "Pitstop"
        assert claim.delivery.subscription is not None
        assert claim.delivery.subscription.name == queue
    assert [c.object.name for c in _broker_claims(answer)] == [BROKER]


def test_g2_every_claim_ref_resolves_through_get_evidence_at_the_answers_snapshot(driver):
    _import(driver, OVERLAY)
    answer = _ask(driver)

    evidence = _service(driver).get_evidence(
        EvidenceRequest(evidence_refs=answer.evidence_refs, snapshot_id=answer.snapshot.snapshot_id)
    )

    assert evidence.data.missing_evidence_refs == []
    assert {r.id for r in evidence.data.records} == set(answer.evidence_refs)


def test_g2_there_is_no_receiver_side_claim_so_a_consumer_answer_cannot_list_receivers(driver):
    _import(driver, OVERLAY)

    consumer = _ask(driver, "service:reporting-service")

    assert _dependency_claims(consumer) == {}
    # all it states is that the service uses the broker
    assert [c.object.name for c in _broker_claims(consumer)] == [BROKER]


def test_g2_receivers_resolve_only_through_a_declared_publisher(driver, tmp_path):
    root = _variant(tmp_path)
    for publisher in (
        "workshop-management-api",
        "customer-management-api",
        "vehicle-management-api",
        "time-service",
    ):
        shutil.rmtree(root / publisher)
    _import(driver, root)

    # five declared receivers, no declared publisher: no service has a question that yields them
    assert (
        _count(driver, "MATCH (:Service)-[r:RECEIVES_FROM]->(:Subscription) RETURN count(r) AS c")
        == 5
    )
    for service_id in ("service:reporting-service", "service:invoice-service"):
        assert _dependency_claims(_ask(driver, service_id)) == {}


# --- G3: a Topic carrying several event types is answered per Topic, without any per-event claim -------


def test_g3_header_distinguished_event_types_on_one_channel_change_no_claim(driver, tmp_path):
    _import(driver, OVERLAY)
    baseline = _full_claims(_ask(driver))
    _wipe(driver)

    def two_event_types(document):
        def event(name):
            return {
                "name": name,
                "headers": {"properties": {"MessageType": {"const": name}}},
            }

        document["channels"]["Pitstop"]["publish"]["message"] = {
            "oneOf": [event("MaintenanceJobFinished"), event("MaintenanceJobPlanned")]
        }

    _import(driver, _variant(tmp_path, workshop_management_api=two_event_types))
    with_events = _full_claims(_ask(driver))

    assert _count(driver, "MATCH (:Topic)-[r:CARRIES]->(:Message) RETURN count(r) AS c") == 2
    # nothing in the answer names an event, and the claim set is identical up to the content-hash
    # ids and refs, which cover the (now richer) declaration evidence
    volatile = {"claim_id", "evidence_refs", "resolution_evidence_refs"}

    def strip(claims):
        return [{k: v for k, v in c.items() if k not in volatile} for c in claims]

    assert strip(with_events) == strip(baseline)
    assert "MaintenanceJob" not in json.dumps(with_events)


# --- G4: runtime evidence - publisher qualification (A) and receiver-route evidence (B) ---------------


def test_g4a_a_publisher_send_span_qualifies_every_receiver_claim_of_that_publisher(driver):
    _import(driver, OVERLAY)
    assert set(_qualifications(_ask(driver)).values()) == {"NOT_OBSERVED_IN_WINDOW"}

    batch = _ingest(driver, [_send()])
    answer = _ask(driver)

    assert batch.unresolved == []
    # one span for the Topic confirms all five claims alike: qualification is the publisher's, and
    # there is no per-Subscription qualification field to differ on
    assert _qualifications(answer) == {name: "CONFIRMED" for name in SUBSCRIPTIONS}
    assert all(c.coverage is None for c in _dependency_claims(answer).values())


@pytest.mark.parametrize(
    "span",
    [
        _send(attributes={"messaging.operation.type": ""}),  # operation not send/receive/process
        _send(env=None),  # no deployment.environment.name
        _send(attributes={"messaging.destination.name": "pitstop"}),  # exchange name, wrong case
    ],
    ids=["operation-type", "no-environment", "destination-name"],
)
def test_g4a_each_publisher_requirement_removed_leaves_the_claims_unqualified(driver, span):
    _import(driver, OVERLAY)
    before = _snapshot_id(driver)

    batch = _ingest(driver, [span])
    answer = _ask(driver)

    assert batch.facts == []
    assert set(_qualifications(answer).values()) == {"NOT_OBSERVED_IN_WINDOW"}
    assert _snapshot_id(driver) == before


def test_g4a_a_service_name_that_is_not_the_declared_title_mints_an_observed_only_service(driver):
    _import(driver, OVERLAY)

    batch = _ingest(driver, [_send("workshopmanagementapi")])
    answer = _ask(driver)

    # not dropped and not attached to the declared publisher: a second, observed-only Service appears
    assert [f.subject_id for f in batch.facts] == ["service:workshopmanagementapi"]
    assert _count(driver, "MATCH (x:Service) RETURN count(x) AS c") == 10
    assert set(_qualifications(answer).values()) == {"NOT_OBSERVED_IN_WINDOW"}


def test_g4a_the_messaging_system_attribute_is_not_a_requirement_without_a_namespace(driver):
    _import(driver, OVERLAY)

    batch = _ingest(driver, [_send(attributes={"messaging.system": "kafka"})])

    # only compared against a declared namespace (a virtual host); the overlay declares none
    assert [f.subject_id for f in batch.facts] == [PUBLISHER]
    assert set(_qualifications(_ask(driver)).values()) == {"CONFIRMED"}


def test_g4a_a_send_in_another_environment_does_not_qualify_the_requested_one(driver):
    _import(driver, OVERLAY)

    _ingest(driver, [_send(env="somewhere-else")])

    assert set(_qualifications(_ask(driver)).values()) == {"NOT_OBSERVED_IN_WINDOW"}


def test_g4b_the_declared_receiver_route_resolves_before_any_runtime_evidence(driver):
    _import(driver, OVERLAY)

    claim = _dependency_claims(_ask(driver))["ReportingService"]

    # the route (SUBSCRIPTION_OF + RECEIVES_FROM) is resolved from declared evidence alone
    assert claim.destination_resolution.value == "RESOLVED_SERVICE"
    assert len(claim.resolution_evidence_refs) == 1


def test_g4b_a_matching_receive_span_adds_observed_evidence_to_that_route_only(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])
    before = _ask(driver)

    batch = _ingest(driver, [_receive("ReportingService", "Reporting")])
    after = _ask(driver)

    assert batch.unresolved == []
    assert len(_resolution_refs(after, "ReportingService")) == 2
    for sibling in set(SUBSCRIPTIONS) - {"ReportingService"}:
        assert len(_resolution_refs(after, sibling)) == 1
    # the claim shape and every qualification are unchanged: observing a Subscription route does not
    # qualify the claim, which the publisher's PUBLISHES_TO alone drives
    assert _qualifications(after) == _qualifications(before)
    evidence = _service(driver).get_evidence(
        EvidenceRequest(
            evidence_refs=_resolution_refs(after, "ReportingService"),
            snapshot_id=after.snapshot.snapshot_id,
        )
    )
    assert evidence.data.missing_evidence_refs == []


@pytest.mark.parametrize(
    "span",
    [
        _receive("ReportingService", None),  # no subscription name
        _receive("ReportingService", "reporting"),  # not the declared queue name
        _receive(
            "ReportingService", None, attributes={"messaging.consumer.group.name": "Reporting"}
        ),
    ],
    ids=["missing-name", "mismatched-name", "consumer-group-only"],
)
def test_g4b_a_missing_or_mismatched_subscription_name_adds_no_receiver_evidence(driver, span):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])
    before = _ask(driver)

    batch = _ingest(driver, [span])
    after = _ask(driver)

    assert batch.facts == []
    assert len(batch.unresolved) == 1
    # the route still resolves from its declared evidence, with exactly the evidence it had
    claims = _dependency_claims(after)
    assert all(c.destination_resolution.value == "RESOLVED_SERVICE" for c in claims.values())
    assert {n: _resolution_refs(after, n) for n in SUBSCRIPTIONS} == {
        n: _resolution_refs(before, n) for n in SUBSCRIPTIONS
    }
    assert _qualifications(after) == _qualifications(before)


def test_g4b_another_declared_queues_name_mints_an_observed_receive_and_reroutes_the_claim(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])
    before = _dependency_claims(_ask(driver))["ReportingService"]
    assert before.delivery.subscription.name == "Reporting"

    batch = _ingest(driver, [_receive("ReportingService", "Auditlog")])
    answer = _ask(driver)
    after = _dependency_claims(answer)["ReportingService"]

    # the name matches *a* declared Subscription of the Topic, so the span is accepted and an
    # observed-only RECEIVES_FROM (Reporting -> Auditlog queue) is created that was never declared
    assert [f.relation_type for f in batch.facts] == ["RECEIVES_FROM"]
    assert (
        _count(
            driver,
            "MATCH (:Service {id: 'service:reporting-service'})-[r:RECEIVES_FROM]->(:Subscription) "
            "RETURN count(r) AS c",
        )
        == 2
    )
    # and the answer follows it: ReportingService is now routed through Auditlog's queue, with no
    # limitation raised and its declared Reporting route gone from the claim
    assert after.delivery.subscription.name == "Auditlog"
    assert answer.limitations == []
    assert set(_dependency_claims(answer)) == set(SUBSCRIPTIONS)


def test_g4b_a_receive_without_any_publisher_span_qualifies_no_claim(driver):
    _import(driver, OVERLAY)

    _ingest(driver, [_receive("ReportingService", "Reporting")])
    answer = _ask(driver)

    assert set(_qualifications(answer).values()) == {"NOT_OBSERVED_IN_WINDOW"}
    # the receive evidence is attached to the route and visible there, not in the claim's qualification
    assert len(_resolution_refs(answer, "ReportingService")) == 2


def test_g4_runtime_evidence_never_mints_an_observed_only_topic_or_subscription(driver):
    _import(driver, OVERLAY)

    batch = _ingest(
        driver,
        [
            _send(attributes={"messaging.destination.name": "Ghost"}),
            _receive("ReportingService", "Ghost"),
            _send(),
            _receive("ReportingService", "Reporting"),
        ],
    )

    assert len(batch.unresolved) == 2
    assert _names(driver, "MATCH (t:Topic) RETURN t.name AS n") == {"Pitstop"}
    assert _names(driver, "MATCH (s:Subscription) RETURN s.name AS n") == set(
        SUBSCRIPTIONS.values()
    )
    assert (
        _count(
            driver,
            "MATCH (n) WHERE (n:Topic OR n:Subscription) AND n.discovery_status IS NOT NULL "
            "RETURN count(n) AS c",
        )
        == 0
    )


def test_g4_no_per_subscription_qualification_is_observable_in_the_answer(driver):
    _import(driver, OVERLAY)
    _ingest(
        driver,
        [
            _send(),
            *[
                _receive(name, queue)
                for name, queue in SUBSCRIPTIONS.items()
                if name != "AuditlogService"
            ],
        ],
    )

    claims = _dependency_claims(_ask(driver))

    # Auditlog's queue was never observed receiving and the other four were, yet the claims cannot
    # say so: the only qualification a claim carries is the publisher's
    assert {c.qualification.value for c in claims.values()} == {"CONFIRMED"}
    assert len(claims["AuditlogService"].resolution_evidence_refs) == 1
    assert all(
        len(c.resolution_evidence_refs) == 2 for n, c in claims.items() if n != "AuditlogService"
    )
    assert not any("subscription_qualification" in c.model_dump() for c in claims.values())


# --- G5: observation windows and a stable answer for a completed window --------------------------------


def test_g5_windows_are_caller_chosen_and_messaging_qualifies_in_a_day_and_a_short_one(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])

    day = _qualifications(_ask(driver, context=FULL_DAY))
    short = _qualifications(_ask(driver, context=SHORT_WINDOW))
    elsewhere = _qualifications(
        _ask(
            driver,
            context={
                "environment": ENV,
                "window_start": "2026-10-05T00:00:00Z",
                "window_end": "2026-10-05T23:59:59Z",
            },
        )
    )

    assert set(day.values()) == {"CONFIRMED"}
    assert short == day
    assert set(elsewhere.values()) == {"NOT_OBSERVED_IN_WINDOW"}


def test_g5_later_publisher_traffic_leaves_the_claims_of_a_completed_window_unchanged(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send(), _receive("ReportingService", "Reporting")])
    completed = _ask(driver)

    _ingest(driver, [_send(when=DAY_2)])

    # the complete claim set, including claim ids, qualifications and evidence refs of the window
    assert _full_claims(_ask(driver)) == _full_claims(completed)


def test_g5_later_receiver_traffic_adds_out_of_window_evidence_to_a_completed_windows_claim(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])
    completed = _ask(driver)

    _ingest(driver, [_receive("InvoiceService", "Invoicing", when=DAY_2)])
    later = _ask(driver)

    # qualification holds, but the route's resolution evidence is not window-scoped: the claim for
    # the 2026-10-06 window now cites evidence observed on 2026-10-07
    assert _qualifications(later) == _qualifications(completed)
    before = _resolution_refs(completed, "InvoiceService")
    after = _resolution_refs(later, "InvoiceService")
    assert len(before) == 1 and len(after) == 2
    assert next(r for r in after if r not in before).startswith(
        "evidence:otel:pitstop-spike:2026-10-07:"
    )
    assert _full_claims(later) != _full_claims(completed)


def test_g5_the_snapshot_id_changes_with_later_traffic_and_a_stale_snapshot_is_refused(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send()])
    completed = _ask(driver)

    _ingest(driver, [_send(when=DAY_2)])
    later = _ask(driver)

    # same claims, different snapshot id: the id fingerprints live evidence, not just the window
    assert _full_claims(later) == _full_claims(completed)
    assert later.snapshot.snapshot_id != completed.snapshot.snapshot_id
    stale = _service(driver).get_evidence(
        EvidenceRequest(
            evidence_refs=completed.evidence_refs, snapshot_id=completed.snapshot.snapshot_id
        )
    )
    assert stale.data is None
    fresh = _service(driver).get_evidence(
        EvidenceRequest(evidence_refs=later.evidence_refs, snapshot_id=later.snapshot.snapshot_id)
    )
    assert fresh.data.missing_evidence_refs == []


def test_g5_repeating_the_same_import_and_ingest_reproduces_the_claims(driver):
    _import(driver, OVERLAY)
    _ingest(driver, [_send(), _receive("ReportingService", "Reporting")])
    first = _ask(driver)

    _wipe(driver)
    _import(driver, OVERLAY)
    _ingest(driver, [_send(), _receive("ReportingService", "Reporting")])
    second = _ask(driver)

    assert _full_claims(second) == _full_claims(first)
    assert second.snapshot.snapshot_id == first.snapshot.snapshot_id


# --- the OTLP endpoint wiring, for the fork-facing attribute set ---------------------------------------


def _otlp(service: str, operation: str, queue: str | None) -> bytes:
    def kv(key, value):
        return KeyValue(key=key, value=AnyValue(string_value=value))

    attributes = [
        kv("messaging.system", "rabbitmq"),
        kv("messaging.operation.type", operation),
        kv("messaging.destination.name", "Pitstop"),
    ]
    if queue is not None:
        attributes.append(kv("messaging.destination.subscription.name", queue))
    resource = Resource(
        attributes=[kv("service.name", service), kv("deployment.environment.name", ENV)]
    )
    start = int(DAY_1.timestamp() * 1_000_000_000)
    span = Span(
        trace_id=bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736"),
        span_id=bytes.fromhex("00f067aa0ba902b7"),
        name="Pitstop " + operation,
        kind=Span.SPAN_KIND_PRODUCER if operation == "send" else Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=start,
        end_time_unix_nano=start + 50_000_000,
        attributes=attributes,
    )
    return ExportTraceServiceRequest(
        resource_spans=[ResourceSpans(resource=resource, scope_spans=[ScopeSpans(spans=[span])])]
    ).SerializeToString()


def test_g4_the_otlp_endpoint_applies_the_same_rules_to_the_fork_facing_attribute_set(driver):
    _import(driver, OVERLAY)
    app = create_app()
    app.state.driver = driver
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {"graph": {"uri": "bolt://ignored:7687", "database": DATABASE}}
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored"),
    )
    client = TestClient(app)
    headers = {"content-type": "application/x-protobuf"}

    for payload in (
        _otlp("WorkshopManagementAPI", "send", None),
        _otlp("ReportingService", "process", "Reporting"),
    ):
        assert client.post("/v1/traces", content=payload, headers=headers).status_code == 200
    answer = _ask(driver)

    assert set(_qualifications(answer).values()) == {"CONFIRMED"}
    assert len(_resolution_refs(answer, "ReportingService")) == 2
