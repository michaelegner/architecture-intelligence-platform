"""v0.6.0 I2.6b: executable coverage for the I1 dossier variants the I2.1-I2.5 suites left without
a test of their exact expectation (I2 spec §16 DoD 8; `i2-conformance-matrix.md`).

Expected values are read from the frozen I1 oracle (`conformance-expected.json`) and vectors
(`v2-evidence-id.json`); fixtures reuse the I2.3b/I2.5b real-importer and persistence helpers.
"""

import json
from pathlib import Path

import pytest

from app.architecture_intelligence import repository
from app.canonical.ids import scoped_observed_call_v2_id
from app.graph.importer import import_kubernetes_source
from app.graph.schema import ensure_schema
from app.sources.model import DiagnosticCode
from tests.integration.test_scoped_applicability import _bundle, _cap, _import
from tests.integration.test_snapshot_scoped_keys import UNIT, _persist

DATABASE = "neo4j"
_VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.6.0/i1-vectors"
ORACLE = json.loads((_VECTORS / "conformance-expected.json").read_text(encoding="utf-8"))
KEYS = json.loads((_VECTORS / "v2-evidence-id.json").read_text(encoding="utf-8"))
V2 = {v["id"]: v["evidence_id"] for v in KEYS["key_vectors"]}
V1 = {v["id"]: v["evidence_id"] for v in KEYS["v1_unchanged"]}


def _expected(case_id: str, variant_id: str) -> dict:
    [case] = [c for c in ORACLE["cases"] if c["id"] == case_id]
    [variant] = [v for v in case["variants"] if v["id"] == variant_id]
    return variant["expected"]


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


def _seed(pod_uid: str, trace_id: str) -> dict:
    """V01's key (production, day D, service:orders -> O1, cluster K1) for any caller Pod."""
    [base] = [s for s in UNIT["seeds"] if s["correlation_mode"] == "CLIENT_SERVER"][:1]
    return {**base, "caller_pod_uid": pod_uid, "trace_id": trace_id}


def test_l12a_one_interaction_has_exactly_one_v1_and_one_v2_representation(graph, session):
    expected = _expected("L12", "a")
    [base] = [s for s in UNIT["seeds"] if s["correlation_mode"] == "CLIENT_SERVER"][:1]
    _persist(graph, [base])

    v1 = session.run("MATCH (e:Evidence) RETURN e.id AS id, e.observation_count AS count").data()
    v2 = [r["id"] for r in session.run("MATCH (v:ScopedObservedCallV2) RETURN v.id AS id")]
    [edge] = session.run(
        "MATCH (:Service {id: 'service:orders'})-[r:CALLS]->() RETURN r.evidence_ids AS ids"
    ).data()
    state = repository.canonical_snapshot_state(session, coverage_qualification_enabled=True)

    assert [row["id"] for row in v1] == [V1[i] for i in expected["v1_ids"]]
    assert v2 == [V2[i] for i in expected["v2_ids"]]
    assert [row["count"] for row in v1] == [expected["v1_observation_count"]]
    assert edge["ids"] == [V1[i] for i in expected["legacy_calls_edge_evidence_ids"]]
    in_evidence = any(row["id"] in v2 for row in state["evidence"])
    assert in_evidence is expected["snapshot_evidence_array_contains_v2"]


@pytest.mark.parametrize("n", [1, 5, 25])
def test_l28a_n_pods_of_one_workload_are_n_v2_records_and_one_v1_bucket(graph, session, n):
    expected = _expected("L28", "a")
    seeds = [_seed(f"11111111-aaaa-4bbb-8ccc-{i:012d}", f"{i:032x}") for i in range(1, n + 1)]
    _persist(graph, seeds)

    v2 = [r["id"] for r in session.run("MATCH (v:ScopedObservedCallV2) RETURN v.id AS id")]
    v1 = session.run("MATCH (e:Evidence) RETURN e.id AS id, e.observation_count AS c").data()

    assert expected["v2_record_count"] == "n"
    assert len(v2) == len(set(v2)) == n  # never compacted or truncated
    assert sorted(v2) == sorted(
        scoped_observed_call_v2_id(
            environment=s["environment"],
            bucket_utc_day=s["bucket_utc_day"],
            subject_id=s["subject_id"],
            object_id=s["object_id"],
            caller_cluster_uid=s["caller_cluster_uid"],
            caller_pod_uid=s["caller_pod_uid"],
        )
        for s in seeds
    )
    assert len(v1) == expected["v1_bucket_count"]
    assert v1[0]["c"] == n


def _codes(stats) -> set:
    return {d.code for d in stats.diagnostics} | {
        d.code for source in stats.per_source.values() for d in getattr(source, "diagnostics", [])
    }


def test_l17e_an_envelope_without_captured_at_is_rejected_invalid_and_never_selectable(
    graph, session, tmp_path
):
    expected = _expected("L17", "e")
    config = _bundle(tmp_path / "x", **_cap("CAP-A"))
    envelope = (config.root / "envelope.yaml").read_text(encoding="utf-8")
    (config.root / "envelope.yaml").write_text(
        "\n".join(line for line in envelope.splitlines() if "capturedAt" not in line) + "\n"
    )
    stats = import_kubernetes_source(graph, database=DATABASE, source_config=config)

    assert stats.committed is False
    assert expected["import"]["result"] == "REJECTED_INVALID"
    assert DiagnosticCode(expected["import"]["diagnostic"]) in _codes(stats)
    assert (
        session.run(
            "MATCH (s:SourceState) WHERE s.capture_cluster_uid IS NOT NULL RETURN count(s) AS n"
        ).single()["n"]
        == 0
    )
    assert expected["locality_evaluated"] is False


def test_l29a_an_incomplete_capture_is_rejected_and_the_committed_one_stays_selected(
    graph, session, tmp_path
):
    expected = _expected("L29", "a")
    _import(graph, tmp_path, **_cap("CAP-A"))
    before = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]

    partial = _cap("CAP-PARTIAL")
    config = _bundle(tmp_path / "cap", **partial)
    stats = import_kubernetes_source(graph, database=DATABASE, source_config=config)

    assert stats.committed is False
    assert expected["import"]["result"] == "REJECTED_INVALID"
    assert DiagnosticCode(expected["import"]["diagnostic"]) in _codes(stats)
    [revision] = [
        r["revision"]
        for r in session.run(
            "MATCH (s:SourceState) WHERE s.capture_cluster_uid IS NOT NULL "
            "RETURN s.capture_revision AS revision"
        )
    ]
    assert revision == expected["selected_capture_after"]
    assert expected["committed_state_preserved"] is True
    assert session.run("MATCH (n) RETURN count(n) AS n").single()["n"] == before
