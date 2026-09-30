"""v0.6.0 I2.5b: the two conditional snapshot keys (I2 spec §11, decision record D5 and D15; I1 v2
contract §8).

Real Neo4j, real persistence and imports. Gate (c): the D15.1 fixture graph, built from exactly the
inputs recorded in the independently frozen `i2-vectors/snapshot-after.json`, yields that vector's
bytes and `snapshot_id`. Gate (a): with no v2 record neither key exists and the state keeps its v0.5
key set; removing the last v2 record restores the prior bytes exactly. D5: a capture-only change
moves the snapshot when v2 exists and never when none does.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.architecture_intelligence import repository
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_kubernetes_source
from app.graph.revision_fence import read_revision
from app.graph.schema import ensure_schema
from app.provenance.model import ObservedEvidence
from app.settings import ScopedEvidenceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity
from app.telemetry.scoped_attribution import ScopedCallSeed
from tests.integration.test_local_assessment import PRODUCER
from tests.integration.test_scoped_applicability import _bundle, _inventory_revision
from tests.unit.test_scoped_applicability import _request

DATABASE = "neo4j"
VECTOR = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/specifications/0.6.0/i2-vectors/snapshot-after.json"
    ).read_text(encoding="utf-8")
)
UNIT = VECTOR["fixture"]["telemetry_unit"]
CAPTURE = VECTOR["fixture"]["kubernetes_capture"]
SCOPED_KEYS = {"scoped_observed_calls_v2", "scoped_capture_scopes_v2"}
V0_5_KEYS = set(VECTOR["expected_state"]) - SCOPED_KEYS
ON = ScopedEvidenceConfig(enabled=True)
OFF = ScopedEvidenceConfig(enabled=False)


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


def _fact(seed: dict) -> ObservedFactCandidate:
    """One recorded fixture seed as an accepted CALLS fact with its one-observation v1 seed (the
    vector's `v1_fact_evidence` rule) and its scoped v2 seed."""
    at = datetime.fromisoformat(seed["fact_timestamp"])
    day = datetime.fromisoformat(seed["bucket_utc_day"]).replace(tzinfo=UTC)
    names = ("k8s_namespace_name", "k8s_pod_name", "k8s_deployment_name")
    scoped = ScopedCallSeed(
        environment=seed["environment"],
        bucket_utc_day=seed["bucket_utc_day"],
        subject_id=seed["subject_id"],
        object_id=seed["object_id"],
        caller_cluster_uid=seed["caller_cluster_uid"],
        caller_pod_uid=seed["caller_pod_uid"],
        fact_timestamp=at,
        trace_id=seed["trace_id"],
        correlation_mode=seed["correlation_mode"],
        **{name: seed[name] for name in names if name in seed},
    )
    return ObservedFactCandidate(
        subject_id=seed["subject_id"],
        relation_type="CALLS",
        object_id=seed["object_id"],
        environment=seed["environment"],
        timestamp=at,
        trace_id=seed["trace_id"],
        evidence=ObservedEvidence(
            id=ids.observed_evidence_id(
                seed["environment"], day, seed["subject_id"], "CALLS", seed["object_id"]
            ),
            environment=seed["environment"],
            bucket_start=day,
            bucket_end=day + timedelta(days=1),
            first_seen=at,
            last_seen=at,
            observation_count=1,
            sample_trace_ids=[seed["trace_id"]],
            correlation_mode=seed["correlation_mode"],
        ),
        scoped_seed=scoped,
    )


def _persist(graph, seeds=UNIT["seeds"], *, scoped=ON) -> None:
    batch = ObservationBatch(
        entities=[ObservedOnlyEntity(**entity) for entity in UNIT["entities"]],
        facts=[_fact(seed) for seed in seeds],
    )
    persist_observation_batch(graph, DATABASE, batch, scoped=scoped)


def _capture(graph, tmp_path, **overrides):
    spec = {
        "source_id": CAPTURE["configured_source_id"],
        "scope_id": CAPTURE["configured_scope_id"],
        "cluster_uid": CAPTURE["cluster_uid"],
        "namespaces": CAPTURE["namespaces"],
        "resources": CAPTURE["resources"],
        "captured_at": CAPTURE["captured_at"],
        "revision": CAPTURE["revision"],
        **overrides,
    }
    root = tmp_path / "capture"  # one stable root: the root is part of the scope definition
    probe = _bundle(root, **spec)
    config = _bundle(root, prior=_inventory_revision(graph, probe), **spec)
    stats = import_kubernetes_source(graph, database=DATABASE, source_config=config)
    assert stats.committed, stats.diagnostics
    return stats


def _state(session) -> dict:
    return repository.canonical_snapshot_state(session, coverage_qualification_enabled=True)


def _stable(session):
    return repository.read_stable_snapshot_from_session(
        session, coverage_qualification_enabled=True
    )


# --- Gate (c): the real graph yields the independently frozen after vector ---------------------


def test_the_d15_fixture_graph_yields_the_frozen_after_snapshot(graph, session, tmp_path):
    _persist(graph)
    _capture(graph, tmp_path)

    state = _state(session)
    assert canonical_json_bytes(state).decode("utf-8") == VECTOR["canonical_bytes_utf8"]
    snapshot = _stable(session)
    assert (snapshot.snapshot_id, snapshot.model_revision) == (
        VECTOR["snapshot_id"],
        VECTOR["model_revision"],
    )
    # Gates (d)/(e) with the keys present: v2 only ever enters through its own key.
    v2_ids = {entry["id"] for entry in state["scoped_observed_calls_v2"]}
    assert v2_ids.isdisjoint({row["id"] for row in state["evidence"]})
    assert v2_ids.isdisjoint({i for r in state["relations"] for i in r.get("evidence_ids", [])})
    [row] = session.run(
        "MATCH (v:ScopedObservedCallV2) RETURN count(v) AS n, sum(COUNT { (v)--() }) AS degree, "
        "sum(CASE WHEN v.owner_source_ids IS NULL THEN 0 ELSE 1 END) AS owned"
    ).data()
    assert row == {"n": 2, "degree": 0, "owned": 0}


def test_every_answer_carries_the_same_one_snapshot(graph, session, tmp_path):
    """L14: one fingerprint - the stable read and the service's answer share the snapshot id."""
    _persist(graph)
    _capture(graph, tmp_path)
    service = ArchitectureIntelligenceService(graph, database=DATABASE, producer=PRODUCER)
    assert service.assess_local_calls(_request()).snapshot_id == VECTOR["snapshot_id"]


# --- Gate (a) and D15.2: the keys exist iff v2 exists -----------------------------------------


def test_without_v2_neither_key_exists_and_the_v0_5_keys_are_unchanged(graph, session, tmp_path):
    _persist(graph, scoped=OFF)
    _capture(graph, tmp_path)
    state = _state(session)
    assert set(state) == V0_5_KEYS
    assert state["version"] == 3
    # Exactly the v0.5 portion of the frozen after-state: v2 contributes nothing else.
    expected = {k: v for k, v in VECTOR["expected_state"].items() if k not in SCOPED_KEYS}
    assert canonical_json_bytes(state) == canonical_json_bytes(expected)


def test_the_last_v2_record_removed_restores_the_prior_bytes_exactly(graph, session, tmp_path):
    _persist(graph, scoped=OFF)
    _capture(graph, tmp_path)
    before = canonical_json_bytes(_state(session))

    _persist(graph, UNIT["seeds"][:1])
    with_v2 = _state(session)
    assert SCOPED_KEYS <= set(with_v2)

    session.run("MATCH (v:ScopedObservedCallV2) DETACH DELETE v").consume()
    session.run(
        "MATCH (e:Evidence) SET e.observation_count = e.observation_count - 1"
    ).consume()  # undo only the second unit's v1 contribution, so v1 is as before
    after = _state(session)
    assert set(after) == V0_5_KEYS
    assert canonical_json_bytes(after) == before


def test_v2_without_any_capture_has_an_empty_scope_list(graph, session):
    _persist(graph)
    state = _state(session)
    assert state["scoped_capture_scopes_v2"] == []
    assert len(state["scoped_observed_calls_v2"]) == 2


# --- D5: a capture-only change moves the snapshot exactly when v2 exists -----------------------


@pytest.mark.parametrize(
    "change",
    [
        {"namespaces": ["billing", "shop"]},
        {"revision": "after-vector-c2"},
        {"captured_at": "2026-09-28T13:00:00Z"},
    ],
    ids=["scope", "revision", "capturedAt"],
)
@pytest.mark.parametrize("with_v2", [True, False], ids=["with-v2", "without-v2"])
def test_a_capture_only_change_moves_the_snapshot_iff_v2_exists(
    graph, session, tmp_path, change, with_v2
):
    _persist(graph, scoped=ON if with_v2 else OFF)
    _capture(graph, tmp_path)
    before, before_revision = _stable(session), read_revision(session)

    _capture(graph, tmp_path, **change)
    after, after_revision = _stable(session), read_revision(session)

    assert (after.snapshot_id != before.snapshot_id) is with_v2
    assert (after_revision != before_revision) is with_v2
    if with_v2:
        [scope] = _state(session)["scoped_capture_scopes_v2"]
        field, value = next(iter(change.items()))
        assert scope[field] == value


def test_a_v2_only_change_moves_the_snapshot_and_nothing_else(graph, session, tmp_path):
    """Removing one of two v2 records changes only the scoped key: the v0.5 portion is untouched,
    yet the one fingerprint moves (the I2.3/I2.4 disclosure is closed)."""
    _persist(graph)
    _capture(graph, tmp_path)
    before_state, before = _state(session), _stable(session).snapshot_id
    [v03] = [
        e["id"] for e in before_state["scoped_observed_calls_v2"] if e["observation_count"] == 2
    ]

    session.run("MATCH (v:ScopedObservedCallV2 {id: $id}) DETACH DELETE v", id=v03).consume()
    after_state, after = _state(session), _stable(session).snapshot_id

    assert after != before
    assert [e["id"] for e in after_state["scoped_observed_calls_v2"]] != [v03]
    assert v03 not in {e["id"] for e in after_state["scoped_observed_calls_v2"]}
    assert {k: v for k, v in after_state.items() if k != "scoped_observed_calls_v2"} == {
        k: v for k, v in before_state.items() if k != "scoped_observed_calls_v2"
    }
