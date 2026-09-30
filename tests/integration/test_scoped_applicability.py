"""v0.6.0 I2.3b: selected-capture applicability end to end (I2 spec §8.1, decision record D4/D13).

Real Neo4j. The oracle's captures are real Kubernetes envelopes imported through the real
discoverer and importer, so a capture is selectable only if the importer actually accepted and
committed it. v2 records are stored as the persisted shape (and, for L15/L27, written by the
production per-POST persistence path). Expected values are read from the frozen I1 oracle via the
I2.3a unit test's realization tables; nothing here restates an oracle result.
"""

import hashlib
from datetime import UTC, datetime

import pytest
import yaml

from app.architecture_intelligence import repository
from app.architecture_intelligence.repository import SnapshotUnstable
from app.architecture_intelligence.scoped_applicability import (
    AdmissionBasis,
    ScopedLimitation,
    SourceSelector,
)
from app.architecture_intelligence.scoped_evidence_repository import (
    read_scoped_applicability,
    read_scoped_observed_calls,
)
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_kubernetes_source
from app.graph.schema import ensure_schema
from app.settings import ScopedEvidenceConfig
from app.sources.identity import discovery_scope_id, kubernetes_source_instance_id
from app.sources.model import KubernetesSourceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.scoped_attribution import LocalityDisposition, ScopedCallSeed
from tests.integration.test_architecture_intelligence_deployment_path_c import (
    EXPECTED_RESOURCE_TYPES,
    _pod_resource,
    _replica_set_resource,
    _workload_resource,
)
from tests.integration.test_scoped_evidence_persistence import _batch
from tests.unit.test_scoped_applicability import (
    _CAPTURE_RECORD,
    _ORACLE_CASES,
    _REALIZATION,
    D1,
    K1,
    K2,
    ORACLE,
    P1,
    P1_NAME,
    P2,
    P2_NAME,
    WORKLOADS,
    D,
    _record,
    _request,
)

DATABASE = "neo4j"
NS = "shop"


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


# --- Real envelopes ----------------------------------------------------------------------------


def _deployment_chain(deployment: str, pods: list[tuple[str, str]], *, namespace=NS):
    """A Deployment, one ReplicaSet and its Pods `(name, uid)`."""
    rs = f"{deployment}-rs"
    return [
        _workload_resource("Deployment", deployment, uid=f"uid-{deployment}", namespace=namespace),
        _replica_set_resource(
            rs,
            uid=f"uid-{rs}",
            namespace=namespace,
            owner_name=deployment,
            owner_uid=f"uid-{deployment}",
        ),
        *(
            _pod_resource(
                name,
                uid=uid,
                namespace=namespace,
                owner_kind="ReplicaSet",
                owner_name=rs,
                owner_uid=f"uid-{rs}",
            )
            for name, uid in pods
        ),
    ]


def _bundle(
    root,
    *,
    source_id: str,
    cluster_uid: str,
    namespaces,
    resources,
    captured_at: str,
    revision: str,
    mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
    prior: str | None = None,
    completeness: str = "COMPLETE",
    scope_id: str | None = None,
) -> KubernetesSourceConfig:
    scope_id = scope_id or f"{source_id}-scope"
    root.mkdir(parents=True, exist_ok=True)
    resource_bytes = yaml.safe_dump_all(resources).encode()
    (root / "resources.yaml").write_bytes(resource_bytes)
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": f"{source_id}-{revision}",
            "revision": revision,
            "producer": "aip-kubernetes-capture-agent",
            "capturedAt": captured_at,
        },
        "source": {
            "configuredSourceId": source_id,
            "configuredScopeId": scope_id,
            "clusterUid": cluster_uid,
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": mode.value,
        },
        "scope": {
            "namespaces": sorted(namespaces),
            "resourceTypes": sorted(EXPECTED_RESOURCE_TYPES),
        },
        "completeness": {
            "status": completeness,
            "authorityRef": f"{source_id}-authority",
            "expectedPriorInventoryRevision": prior,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resource_bytes).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id=source_id,
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id=scope_id,
        cluster_uid=cluster_uid,
        evidence_mode=mode,
        authorized_producer="aip-kubernetes-capture-agent",
        authority_record=f"{source_id}-authority",
    )


# Derived source instance id -> the readable configured id, for assertions.
_NAMES: dict[str, str] = {}


def _instance_id(source_id: str, cluster_uid: str) -> str:
    instance_id = kubernetes_source_instance_id(
        configured_kubernetes_source_id=source_id, cluster_uid=cluster_uid
    )
    _NAMES[instance_id] = source_id
    return instance_id


def _inventory_revision(driver, config: KubernetesSourceConfig) -> str | None:
    scope_id = discovery_scope_id(
        configured_scope_id=config.resolved_scope_id,
        stable_target_identity=config.resolved_stable_target_identity,
    )
    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (i:CurrentInventory {discovery_scope_id: $scope}) "
            "RETURN i.inventory_revision AS r",
            scope=scope_id,
        ).single()
    return None if record is None else record["r"]


def _import(driver, tmp_path, *, expect_committed=True, **spec) -> SourceSelector:
    """Imports one envelope (as a reimport when the source already has an inventory) and returns
    the selector naming its capture."""
    source_id, revision = spec["source_id"], spec["revision"]
    # One stable root per source, as a real capture agent rewrites it in place: the root is part
    # of the scope definition, and a changed scope definition keeps the old inventory (v0.5).
    root = tmp_path / source_id
    probe = _bundle(root, **spec)
    config = _bundle(root, prior=_inventory_revision(driver, probe), **spec)
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed is expect_committed, stats.diagnostics
    return SourceSelector(_instance_id(source_id, spec["cluster_uid"]), revision)


CAP_A_RESOURCES = [
    *_deployment_chain("orders", [(P1_NAME, P1)]),
    *_deployment_chain("orders-canary", [(P2_NAME, P2)]),
]


def _cap(name: str, source_id: str = "cap", **overrides):
    """The oracle's abstract captures (dossier §2) as real envelope specs (D13.1)."""
    base = {
        "source_id": source_id,
        "cluster_uid": K1,
        "namespaces": [NS],
        "resources": CAP_A_RESOURCES,
        "captured_at": f"{D}T12:00:00Z",
        "revision": name,
    }
    variants = {
        "CAP-A": {},
        "CAP-B": {
            "resources": _deployment_chain("orders-canary", [(P2_NAME, P2)]),
            "captured_at": f"{D}T18:00:00Z",
        },
        "CAP-A-D1": {"captured_at": f"{D1}T12:00:00Z"},
        "CAP-A-NOTIME": {"captured_at": f"{D}T12:00:00"},
        "CAP-DM": {"mode": KubernetesEvidenceMode.DECLARED_MANIFEST},
        "CAP-AMB": {
            "resources": [
                *_deployment_chain("orders", [("orders-a", P1)]),
                *_deployment_chain("orders-canary", [("orders-b", P1)]),
            ]
        },
        "CAP-CONF": {"resources": _deployment_chain("orders-canary", [(P1_NAME, P1)])},
        "CAP-CONF-D1": {
            "resources": _deployment_chain("orders-canary", [(P1_NAME, P1)]),
            "captured_at": f"{D1}T12:00:00Z",
        },
        "CAP-PARTIAL": {
            "resources": _deployment_chain("orders-canary", [(P2_NAME, P2)]),
            "completeness": "PARTIAL",
        },
    }
    return {**base, **variants[name], **overrides}


# Captures that the oracle reaches only after an earlier accepted capture of the same source.
_HISTORY = {"CAP-B": ["CAP-A"]}
_CASE_HISTORY = {"L29": ["CAP-A", ("CAP-PARTIAL", False)]}


def _store(session, record) -> None:
    props = {k: v for k, v in record.model_dump().items() if v is not None}
    session.run(
        "MERGE (v:ScopedObservedCallV2 {id: $id}) SET v += $props", id=record.id, props=props
    )


def _read(session, request, **kwargs):
    return read_scoped_applicability(
        session, request, coverage_qualification_enabled=False, **kwargs
    )


def _v2(session, subject="service:orders"):
    return read_scoped_observed_calls(session, subject_id=subject).records


# --- Stop conditions of the plan (verified against the real importer) --------------------------


@pytest.mark.parametrize("capture", ["CAP-A-NOTIME", "CAP-AMB", "CAP-CONF", "CAP-DM"])
def test_every_realized_capture_is_accepted_and_committed(graph, session, tmp_path, capture):
    _import(graph, tmp_path, **_cap(capture))
    [row] = session.run(
        "MATCH (s:SourceState) WHERE s.capture_cluster_uid IS NOT NULL "
        "RETURN s.capture_revision AS revision"
    ).data()
    assert row == {"revision": capture}


def test_a_rejected_envelope_writes_no_selectable_capture(graph, session, tmp_path):
    """L17e: an envelope without `capturedAt` is rejected, so nothing can select it."""
    config = _bundle(tmp_path / "x", **_cap("CAP-A"))
    envelope = yaml.safe_load((config.root / "envelope.yaml").read_text())
    del envelope["metadata"]["capturedAt"]
    (config.root / "envelope.yaml").write_text(yaml.safe_dump(envelope))
    stats = import_kubernetes_source(graph, database=DATABASE, source_config=config)
    assert stats.committed is False
    _store(session, _record("V01-base"))
    [candidate] = _read(session, _request()).result.candidates
    assert candidate.pairs == ()
    assert candidate.limitations == (ScopedLimitation.NO_SELECTABLE_COVERING_SOURCE,)


# --- The oracle rows, end to end ---------------------------------------------------------------


def _oracle_rows():
    for case in ORACLE["cases"]:
        if case["id"] not in _ORACLE_CASES:
            continue
        for variant in case["variants"]:
            for index, expected in enumerate(variant["expected"].get("query", [])):
                yield pytest.param(
                    case["id"],
                    variant["id"],
                    expected,
                    id=f"{case['id']}{variant['id']}-{index}-{expected['candidate']}",
                )


@pytest.mark.parametrize("explicit", [True, False], ids=["explicit", "implicit"])
@pytest.mark.parametrize(("case_id", "variant_id", "expected"), list(_oracle_rows()))
def test_every_single_capture_oracle_row_end_to_end(
    graph, session, tmp_path, case_id, variant_id, expected, explicit
):
    capture = expected["selected_capture"]
    history = _CASE_HISTORY.get(case_id, _HISTORY.get(capture, []))
    for step in history:
        name, committed = step if isinstance(step, tuple) else (step, True)
        _import(graph, tmp_path, expect_committed=committed, **_cap(name))
    if capture not in [s if isinstance(s, str) else s[0] for s in history]:
        selector = _import(graph, tmp_path, **_cap(capture))
    else:
        selector = SourceSelector(_instance_id("cap", K1), capture)

    realization = _REALIZATION.get((case_id, variant_id), {})
    record = _record(
        expected["candidate"], **_CAPTURE_RECORD.get(capture, {}), **realization.get("record", {})
    )
    _store(session, record)
    request = _request(selector=selector if explicit else None, **realization.get("request", {}))

    read = _read(session, request)
    [candidate] = read.result.candidates
    [pair] = candidate.pairs
    assert pair.source.revision == capture
    assert pair.phase == expected["phase"]
    assert pair.disposition == expected["disposition"]
    assert list(pair.reasons) == expected["reasons"]
    assert candidate.disposition == expected["disposition"]
    if "workload" in expected:
        want = WORKLOADS[expected["workload"]]
        got = candidate.workload
        assert (got.kind, got.namespace, got.name, got.cluster_uid) == (
            want.kind,
            want.namespace,
            want.name,
            K1,
        )
        assert got.uid == f"uid-{want.name}"
    else:
        assert candidate.workload is None
    # I1 §6.2: a query-time result never rewrites or removes the retained v2 record.
    assert _v2(session) == (record,)


def test_the_oracle_rows_cover_every_i2_3_query_case():
    assert {param.values[0] for param in _oracle_rows()} == _ORACLE_CASES


def test_c1_then_c2_changes_the_answer_and_keeps_the_record(graph, session, tmp_path):
    """L18/L27: the authoritative later capture no longer holds P1."""
    _import(graph, tmp_path, **_cap("CAP-A"))
    records = [_record("V01-base"), _record("V06-other-operation")]
    for record in records:
        _store(session, record)
    before = _read(session, _request())
    assert [c.disposition for c in before.result.candidates] == [LocalityDisposition.APPLICABLE] * 2

    _import(graph, tmp_path, **_cap("CAP-B"))
    after = _read(session, _request())
    by_pod = {c.record.caller_pod_uid: c for c in after.result.candidates}
    assert by_pod[P1].disposition is LocalityDisposition.UNRESOLVED
    assert list(by_pod[P1].reasons) == ["LOCALITY_CAPTURE_MISSING_POD"]
    assert by_pod[P2].workload.name == "orders-canary"
    assert after.snapshot_id != before.snapshot_id
    assert sorted(_v2(session), key=lambda r: r.id) == sorted(records, key=lambda r: r.id)


# --- The production write path -----------------------------------------------------------------


def _seed(record) -> ScopedCallSeed:
    return ScopedCallSeed(
        environment=record.environment,
        bucket_utc_day=record.bucket_utc_day,
        subject_id=record.subject_id,
        object_id=record.object_id,
        caller_cluster_uid=record.caller_cluster_uid,
        caller_pod_uid=record.caller_pod_uid,
        fact_timestamp=datetime(2026, 9, 28, 16, 45, tzinfo=UTC),
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        correlation_mode="CLIENT_SERVER",
        k8s_namespace_name=record.k8s_namespace_name,
        k8s_pod_name=record.k8s_pod_name,
        k8s_deployment_name=record.k8s_deployment_name,
    )


def test_records_written_by_the_per_post_path_resolve_two_localities(graph, session, tmp_path):
    """L15/L27a with v2 written by `persist_observation_batch` behind the enabled flag."""
    _import(graph, tmp_path, **_cap("CAP-A"))
    seeds = [_seed(_record("V01-base")), _seed(_record("V06-other-operation"))]
    persist_observation_batch(
        graph, DATABASE, _batch(*seeds), scoped=ScopedEvidenceConfig(enabled=True)
    )

    read = _read(session, _request())
    assert [c.disposition for c in read.result.candidates] == [LocalityDisposition.APPLICABLE] * 2
    assert {c.record.caller_pod_uid: c.workload.name for c in read.result.candidates} == {
        P1: "orders",
        P2: "orders-canary",
    }
    assert {c.record.id for c in read.result.candidates} == {
        _record("V01-base").id,
        _record("V06-other-operation").id,
    }


# --- Decision record D4: S01-S06 on real sources -----------------------------------------------


def _source_a(graph, tmp_path):
    _import(
        graph,
        tmp_path,
        **_cap("CAP-A", "a", resources=_deployment_chain("orders", [(P1_NAME, P1)])),
    )


def _pairs(candidate):
    return {
        _NAMES[pair.source.source_instance_id]: (pair.disposition, list(pair.reasons))
        for pair in candidate.pairs
    }


def _candidate(session, record=None):
    _store(session, record or _record("V01-base"))
    [candidate] = _read(session, _request()).result.candidates
    return candidate


def test_s01_an_unrelated_namespace_is_omitted(graph, session, tmp_path):
    _source_a(graph, tmp_path)
    _import(
        graph,
        tmp_path,
        **_cap(
            "CAP-A",
            "b",
            namespaces=["billing"],
            resources=_deployment_chain("invoices", [("invoices-x", "uid-x")], namespace="billing"),
        ),
    )
    candidate = _candidate(session)
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert candidate.workload.name == "orders"
    assert _pairs(candidate) == {"a": (LocalityDisposition.APPLICABLE, [])}


def test_s02_an_unrelated_cluster_is_omitted(graph, session, tmp_path):
    _source_a(graph, tmp_path)
    _import(
        graph,
        tmp_path,
        **_cap(
            "CAP-A", "b", cluster_uid=K2, resources=_deployment_chain("orders", [("o", "uid-o")])
        ),
    )
    candidate = _candidate(session)
    assert _pairs(candidate) == {"a": (LocalityDisposition.APPLICABLE, [])}


def test_s03_a_covering_source_keeps_its_missing_pod_limitation(graph, session, tmp_path):
    _source_a(graph, tmp_path)
    _import(
        graph,
        tmp_path,
        **_cap("CAP-A", "b", resources=_deployment_chain("orders-canary", [(P2_NAME, P2)])),
    )
    candidate = _candidate(session)
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert candidate.workload.name == "orders"
    assert _pairs(candidate) == {
        "a": (LocalityDisposition.APPLICABLE, []),
        "b": (LocalityDisposition.UNRESOLVED, ["LOCALITY_CAPTURE_MISSING_POD"]),
    }
    admissions = {_NAMES[p.source.source_instance_id]: p.admission for p in candidate.pairs}
    assert admissions == {
        "a": (AdmissionBasis.POD_UID, AdmissionBasis.CLUSTER_NAMESPACE),
        "b": (AdmissionBasis.CLUSTER_NAMESPACE,),
    }


def test_s04_the_same_pod_uid_in_another_cluster_is_a_conflict(graph, session, tmp_path):
    _source_a(graph, tmp_path)
    _import(
        graph,
        tmp_path,
        **_cap(
            "CAP-A", "b", cluster_uid=K2, resources=_deployment_chain("orders", [(P1_NAME, P1)])
        ),
    )
    candidate = _candidate(session)
    assert candidate.disposition is LocalityDisposition.CONFLICT
    assert _pairs(candidate) == {
        "a": (LocalityDisposition.APPLICABLE, []),
        "b": (LocalityDisposition.CONFLICT, ["LOCALITY_CLUSTER_UID_CONFLICT"]),
    }


def test_s05_only_the_later_capture_without_the_pod(graph, session, tmp_path):
    _import(graph, tmp_path, **_cap("CAP-B", "c2"))
    candidate = _candidate(session)
    assert (candidate.disposition, list(candidate.reasons)) == (
        LocalityDisposition.UNRESOLVED,
        ["LOCALITY_CAPTURE_MISSING_POD"],
    )


def test_s06_no_covering_source_is_insufficient_evidence(graph, session, tmp_path):
    _import(graph, tmp_path, **_cap("CAP-B", "c2"))
    candidate = _candidate(session, _record("V01-base", k8s_namespace_name=None))
    assert candidate.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert list(candidate.reasons) == ["LOCALITY_LOCAL_COVERAGE_UNAVAILABLE"]
    assert candidate.limitations == (ScopedLimitation.NO_SELECTABLE_COVERING_SOURCE,)
    assert candidate.pairs == ()


def test_a_stale_explicit_selector_selects_nothing(graph, session, tmp_path):
    _import(graph, tmp_path, **_cap("CAP-A"))
    _import(graph, tmp_path, **_cap("CAP-B"))
    _store(session, _record("V01-base"))
    stale = SourceSelector(_instance_id("cap", K1), "CAP-A")
    [candidate] = _read(session, _request(selector=stale)).result.candidates
    assert candidate.pairs == ()
    assert candidate.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE


# --- One fence ---------------------------------------------------------------------------------


def test_the_read_is_bound_to_the_stable_snapshot(graph, session, tmp_path):
    _import(graph, tmp_path, **_cap("CAP-A"))
    _store(session, _record("V01-base"))
    read = _read(session, _request())
    plain = repository.read_stable_snapshot_from_session(
        session, coverage_qualification_enabled=False
    )
    assert (read.snapshot_id, read.model_revision) == (plain.snapshot_id, plain.model_revision)


def test_a_graph_that_never_settles_fails_closed(graph, session, tmp_path, monkeypatch):
    _import(graph, tmp_path, **_cap("CAP-A"))
    _store(session, _record("V01-base"))
    counter = iter(range(100))
    monkeypatch.setattr(repository, "read_revision", lambda _session: next(counter))
    with pytest.raises(SnapshotUnstable):
        _read(session, _request())


def test_a_phase_one_refusal_reads_no_candidates(graph, session, tmp_path):
    _store(session, _record("V01-base"))
    read = _read(session, _request(relation_type="SENDS"))
    assert read.result.candidates == ()
    assert read.result.refusal is not None


def test_paging_passes_the_truncation_through(graph, session, tmp_path):
    _import(graph, tmp_path, **_cap("CAP-A"))
    for vector in ("V01-base", "V03-distinct-pod"):
        _store(session, _record(vector))
    # The reader's page is fixed at 500 (D3); continuation after the first id yields the rest.
    first = min(_record("V01-base").id, _record("V03-distinct-pod").id)
    rest = _read(session, _request(), after_id=first).result
    assert [c.record.id for c in rest.candidates] == [
        max(_record("V01-base").id, _record("V03-distinct-pod").id)
    ]
    assert rest.truncated is False
