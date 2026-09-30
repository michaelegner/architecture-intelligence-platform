"""v0.6.0 I2.4b end to end: the internal Qualified Local Evidence Assessment on real Neo4j (I2 spec
§1, §9-§10; decision record D14).

The I2 §1 minimum demonstration: two Deployment Workloads (`orders`, `orders-canary`) of one caller
Service, a declared `orders -> pricing` call, real captured envelopes and v2 written by the
production per-POST path. `ArchitectureIntelligenceService.assess_local_calls` must return the
declared Operation `CONFIRMED` for `orders` and the undeclared one `OBSERVED_ONLY` for
`orders-canary`.

It runs twice: once with the real OpenAPI/manifest adapters (whose Operation ids carry the full
Service id, `operation:service:pricing:...`), and once with the oracle's exact Operation ids loaded
through the real importer, where the assertion ids must equal the frozen I2.4a vectors A01/A03.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.architecture_intelligence import repository
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.repository import SnapshotUnstable
from app.architecture_intelligence.request import (
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical.ids import scoped_observed_call_v2_id
from app.canonical.model import ArchitectureModel, Operation, Relation, Service
from app.graph.importer import import_all_sources, import_source
from app.graph.revision_fence import read_revision
from app.graph.schema import ensure_schema
from app.provenance.model import Provenance
from app.qualification.declared_observed import CONFIRMED, OBSERVED_ONLY
from app.settings import ScopedEvidenceConfig
from app.sources.model import FilesystemSourceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.scoped_attribution import LocalityDisposition
from tests.integration.test_architecture_intelligence_deployment_path_c import (
    _pod_resource,
    _replica_set_resource,
    _workload_resource,
)
from tests.integration.test_scoped_applicability import _cap, _import, _seed
from tests.integration.test_scoped_evidence_persistence import _batch
from tests.unit.test_scoped_applicability import P1, P1_NAME, P2, P2_NAME, _record, _request

DATABASE = "neo4j"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
_VECTORS = {
    v["id"]: v
    for v in json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "docs/specifications/0.6.0/i2-vectors/local-assessment-id.json"
        ).read_text(encoding="utf-8")
    )["assertion_vectors"]
}
W1_UID = _VECTORS["A01-v01-w1-o1-day-d"]["fields"]["workload"]["uid"]
W2_UID = _VECTORS["A03-w2-o2"]["fields"]["workload"]["uid"]
ORACLE_O1 = "operation:pricing:GET:/prices"
ORACLE_O2 = "operation:legacy-pricing:GET:/prices"
REAL_O1 = "operation:service:pricing:GET:/prices"
REAL_O2 = "operation:service:legacy-pricing:GET:/prices"


@pytest.fixture
def graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)
    return driver


@pytest.fixture
def session(graph):
    with graph.session(database=DATABASE) as s:
        yield s


def _chain(deployment: str, workload_uid: str, pod_name: str, pod_uid: str) -> list[dict]:
    rs = f"{deployment}-rs"
    return [
        _workload_resource("Deployment", deployment, uid=workload_uid, namespace="shop"),
        _replica_set_resource(
            rs, uid=f"uid-{rs}", namespace="shop", owner_name=deployment, owner_uid=workload_uid
        ),
        _pod_resource(
            pod_name,
            uid=pod_uid,
            namespace="shop",
            owner_kind="ReplicaSet",
            owner_name=rs,
            owner_uid=f"uid-{rs}",
        ),
    ]


def _capture(graph, tmp_path, *, with_orders: bool = True, name: str = "CAP-A"):
    resources = _chain("orders-canary", W2_UID, P2_NAME, P2)
    if with_orders:
        resources = _chain("orders", W1_UID, P1_NAME, P1) + resources
    captured_at = "2026-09-28T12:00:00Z" if with_orders else "2026-09-28T18:00:00Z"
    return _import(graph, tmp_path, **_cap(name, resources=resources, captured_at=captured_at))


def _openapi(service: str, path: str, operation: str) -> str:
    return (
        f"openapi: 3.1.0\ninfo:\n  title: {service}\n  version: '1'\n"
        f"x-aip-service-id: service:{service}\npaths:\n  {path}:\n    get:\n"
        f"      operationId: {operation}\n      responses:\n        '200':\n"
        "          description: ok\n"
    )


def _declare_with_real_adapters(graph, root: Path, *, declare: bool = True) -> None:
    for service in ("pricing", "legacy-pricing"):
        (root / service).mkdir(parents=True, exist_ok=True)
        (root / service / "openapi.yaml").write_text(_openapi(service, "/prices", "getPrices"))
    (root / "orders").mkdir(parents=True, exist_ok=True)
    (root / "orders" / "openapi.yaml").write_text(_openapi("orders", "/orders", "listOrders"))
    manifest = root / "orders" / "architecture.yaml"
    if declare:
        manifest.write_text(
            "service: orders\nx-aip-service-id: service:orders\ncalls:\n"
            "  - service: service:pricing\n    operationId: getPrices\n"
        )
    elif manifest.exists():
        manifest.unlink()
    stats = import_all_sources(
        graph, database=DATABASE, source_config=FilesystemSourceConfig(id="decl", root=root)
    )
    assert stats.committed, stats.diagnostics


def _declare_oracle_ids(graph) -> None:
    """The oracle's exact Operation ids, declared through the real importer."""
    evidence = Provenance(
        id="evidence:declared:orders-calls-pricing",
        source_type="MANIFEST",
        source_file="orders/architecture.yaml",
    )
    model = ArchitectureModel(
        services=[
            Service(id="service:orders", name="orders"),
            Service(id="service:pricing", name="pricing"),
            Service(id="service:legacy-pricing", name="legacy-pricing"),
        ],
        operations=[
            Operation(id=ORACLE_O1, service_id="service:pricing", method="GET", path="/prices"),
            Operation(
                id=ORACLE_O2, service_id="service:legacy-pricing", method="GET", path="/prices"
            ),
        ],
        relations=[
            Relation(
                type="CALLS",
                source_id="service:orders",
                target_id=ORACLE_O1,
                evidence_ids=[evidence.id],
            )
        ],
        provenance=[evidence],
    )
    with graph.session(database=DATABASE) as session:
        import_source(
            session,
            source_instance_id="declared-source:orders",
            locator="orders/architecture.yaml",
            model=model,
            semantic_input_digest=hashlib.sha256(b"oracle-declaration").hexdigest(),
            discovery_scope_id="declared-scope:orders",
            scope_definition_digest=hashlib.sha256(b"declared-scope").hexdigest(),
        )


def _persist_v2(graph, *operations: tuple[str, str]) -> None:
    """v2 through the production per-POST path, behind the enabled flag: one CLIENT_SERVER call
    per `(vector, operation id)`, carrying that Pod's CLIENT attributes."""
    seeds = []
    for vector, operation_id in operations:
        base = _record(vector)
        fields = {
            "environment": base.environment,
            "bucket_utc_day": base.bucket_utc_day,
            "subject_id": base.subject_id,
            "object_id": operation_id,
            "caller_cluster_uid": base.caller_cluster_uid,
            "caller_pod_uid": base.caller_pod_uid,
        }
        seeds.append(
            _seed(base.model_copy(update={**fields, "id": scoped_observed_call_v2_id(**fields)}))
        )
    persist_observation_batch(
        graph, DATABASE, _batch(*seeds), scoped=ScopedEvidenceConfig(enabled=True)
    )


def _service(graph) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(graph, database=DATABASE, producer=PRODUCER)


def _by_operation(result):
    return {a.object_operation_id: a for a in result.assertions}


# --- The I2 §1 minimum demonstration -----------------------------------------------------------


def test_the_two_workload_demonstration_with_the_real_adapters(graph, session, tmp_path):
    _declare_with_real_adapters(graph, tmp_path / "declarations")
    _capture(graph, tmp_path)
    _persist_v2(graph, ("V01-base", REAL_O1), ("V03-distinct-pod", REAL_O2))

    result = _service(graph).assess_local_calls(_request())

    assert result.disposition is LocalityDisposition.APPLICABLE
    assert result.candidate_limitations == ()
    by_operation = _by_operation(result)
    assert set(by_operation) == {REAL_O1, REAL_O2}
    confirmed, observed_only = by_operation[REAL_O1], by_operation[REAL_O2]
    assert (confirmed.qualification, confirmed.caller_workload.name) == (CONFIRMED, "orders")
    assert (observed_only.qualification, observed_only.caller_workload.name) == (
        OBSERVED_ONLY,
        "orders-canary",
    )
    assert confirmed.caller_workload.uid == W1_UID
    assert len(confirmed.declared_evidence_ids) == 1
    assert observed_only.declared_evidence_ids == ()
    for assertion in result.assertions:
        assert assertion.target_runtime_scope == "UNKNOWN"
        assert assertion.coverage == "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"
        assert assertion.snapshot_id == result.snapshot_id
        assert [c.revision for c in assertion.selected_captures] == ["CAP-A"]


def test_the_oracle_ids_reproduce_the_frozen_assertion_vectors(graph, session, tmp_path):
    _declare_oracle_ids(graph)
    _capture(graph, tmp_path)
    _persist_v2(graph, ("V01-base", ORACLE_O1), ("V06-other-operation", ORACLE_O2))

    by_operation = _by_operation(_service(graph).assess_local_calls(_request()))

    assert by_operation[ORACLE_O1].assertion_id == _VECTORS["A01-v01-w1-o1-day-d"]["expected_id"]
    assert by_operation[ORACLE_O2].assertion_id == _VECTORS["A03-w2-o2"]["expected_id"]
    assert by_operation[ORACLE_O1].qualification == CONFIRMED
    assert by_operation[ORACLE_O2].qualification == OBSERVED_ONLY


# --- Changes in the graph ----------------------------------------------------------------------


def test_withdrawing_the_declaration_changes_the_instance_not_the_assertion(
    graph, session, tmp_path
):
    root = tmp_path / "declarations"
    _declare_with_real_adapters(graph, root)
    _capture(graph, tmp_path)
    _persist_v2(graph, ("V01-base", REAL_O1))
    before = _by_operation(_service(graph).assess_local_calls(_request()))[REAL_O1]

    _declare_with_real_adapters(graph, root, declare=False)
    after = _by_operation(_service(graph).assess_local_calls(_request()))[REAL_O1]

    assert (before.qualification, after.qualification) == (CONFIRMED, OBSERVED_ONLY)
    assert after.assertion_id == before.assertion_id
    assert after.assessment_id != before.assessment_id
    assert after.snapshot_id != before.snapshot_id


def test_a_later_capture_without_the_pod_turns_the_assertion_into_a_limitation(
    graph, session, tmp_path
):
    _declare_oracle_ids(graph)
    _capture(graph, tmp_path)
    _persist_v2(graph, ("V01-base", ORACLE_O1), ("V06-other-operation", ORACLE_O2))
    assert len(_service(graph).assess_local_calls(_request()).assertions) == 2

    _capture(graph, tmp_path, with_orders=False, name="CAP-B")
    result = _service(graph).assess_local_calls(_request())

    assert [a.caller_workload.name for a in result.assertions] == ["orders-canary"]
    [limitation] = result.candidate_limitations
    assert limitation.disposition is LocalityDisposition.UNRESOLVED
    assert limitation.reasons == ("LOCALITY_CAPTURE_MISSING_POD",)
    assert limitation.snapshot_id == result.snapshot_id


def test_without_v2_the_answer_abstains(graph, session, tmp_path):
    """L23: a declaration and the capture alone mint no positive local CALLS."""
    _declare_oracle_ids(graph)
    _capture(graph, tmp_path)
    result = _service(graph).assess_local_calls(_request())
    assert result.assertions == ()
    assert result.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert result.reasons == (
        "LOCALITY_LOCAL_COVERAGE_UNAVAILABLE",
        "LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION",
    )


# --- v0.5 compatibility, read-only and the fence -----------------------------------------------


def test_the_v0_5_dependency_answer_ignores_v2_and_the_assessment_writes_nothing(
    graph, session, tmp_path
):
    _declare_oracle_ids(graph)
    _capture(graph, tmp_path)
    _persist_v2(graph, ("V01-base", ORACLE_O1))
    service = _service(graph)
    request = ServiceDependenciesRequest(
        service_id="service:orders",
        observation_context=ObservationContextInput(
            environment="production",
            window_start=datetime(2026, 9, 28, tzinfo=UTC),
            window_end=datetime(2026, 9, 28, 23, 59, 59, tzinfo=UTC),
        ),
    )
    with_v2 = service.get_service_dependencies(request)
    revision = read_revision(session)

    service.assess_local_calls(_request())
    assert read_revision(session) == revision

    session.run("MATCH (v:ScopedObservedCallV2) DETACH DELETE v").consume()
    without_v2 = service.get_service_dependencies(request)
    # I2.5 (D15.2, L14): v2 now enters the one snapshot fingerprint every answer carries, so only
    # the snapshot identity differs; the v0.5 answer content itself is unchanged by v2.
    assert with_v2.snapshot != without_v2.snapshot
    unchanged = {"generated_at", "snapshot"}
    assert with_v2.model_dump(exclude=unchanged) == without_v2.model_dump(exclude=unchanged)


def test_a_graph_that_never_settles_fails_closed(graph, session, tmp_path, monkeypatch):
    _declare_oracle_ids(graph)
    counter = iter(range(100))
    monkeypatch.setattr(repository, "read_revision", lambda _session: next(counter))
    with pytest.raises(SnapshotUnstable):
        _service(graph).assess_local_calls(_request())


def test_two_current_incarnations_of_one_logical_workload_stay_two_assertions(
    graph, session, tmp_path
):
    """PR #365 review, on real imports: two sources imported in separate runs can both hold the
    logical Workload `shop/orders` under different captured UIDs. The UID is part of the assertion
    identity (D14.1), so each incarnation keeps its own assertion, lineage and capture."""
    _declare_oracle_ids(graph)
    _import(graph, tmp_path, **_cap("CAP-A", "a", resources=_chain("orders", W1_UID, P1_NAME, P1)))
    second_uid = "22222222-bbbb-4ccc-8ddd-0000000000ff"
    _import(
        graph,
        tmp_path,
        **_cap("CAP-A", "b", resources=_chain("orders", second_uid, "orders-x", P2)),
    )
    records = []
    for vector in ("V01-base", "V03-distinct-pod"):
        base = _record(vector)
        records.append(
            base.model_copy(
                update={
                    "k8s_pod_name": P1_NAME if base.caller_pod_uid == P1 else "orders-x",
                    "k8s_deployment_name": "orders",
                }
            )
        )
    persist_observation_batch(
        graph, DATABASE, _batch(*map(_seed, records)), scoped=ScopedEvidenceConfig(enabled=True)
    )

    result = _service(graph).assess_local_calls(_request())

    by_uid = {a.caller_workload.uid: a for a in result.assertions}
    assert set(by_uid) == {W1_UID, second_uid}
    assert {a.caller_workload.workload_id for a in result.assertions} == {
        result.assertions[0].caller_workload.workload_id
    }
    assert by_uid[W1_UID].assertion_id == _VECTORS["A01-v01-w1-o1-day-d"]["expected_id"]
    assert by_uid[W1_UID].observation.evidence_ids == (records[0].id,)
    assert by_uid[second_uid].observation.evidence_ids == (records[1].id,)
    assert {a.qualification for a in result.assertions} == {CONFIRMED}
