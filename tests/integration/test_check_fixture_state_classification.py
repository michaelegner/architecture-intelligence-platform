"""v0.4.2 I2 - Neo4j-integration coverage for `check_fixture_state.py`'s Neo4j-backed half
(spec `docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md` §44.1/§45):
`classify_fixture()` against a real database, including the `(:AipInternalState)` revision-fence
singleton that only a real import creates and that `tests/unit/test_check_fixture_state.py`'s pure
`classify()` tests cannot exercise (spec §19 - it is deliberately excluded from
`canonical_snapshot_state`, so a whole-database node count is the only thing that sees it).

Each manifest here is captured the same way `examples/runtime-demo/fixture-state.json` itself was
generated: read the live state right after preparing it, fingerprint it, freeze it - then mutate the
graph and prove the checker classifies the mutation as `PARTIAL_OR_INCOMPATIBLE` with a specific
mismatch code, never silently as `COMPLETE` or `EMPTY` (the release blockers spec §62 names)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.revision_fence import bump_revision
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "examples"
    / "runtime-demo"
    / "check_fixture_state.py"
)
_spec = importlib.util.spec_from_file_location("check_fixture_state", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
check_fixture_state = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_fixture_state)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
SERVICE_ID = ids.service_id("order-service")
LEGACY_OPERATION_ID = ids.operation_id(
    ids.service_id("legacy-pricing-service"), "GET", "/pricing/{sku}"
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _observe_order_service_calls_legacy_pricing(driver) -> None:
    bucket_start = datetime(2026, 8, 26, 12, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(
            ENVIRONMENT, bucket_start, SERVICE_ID, "CALLS", LEGACY_OPERATION_ID
        ),
        environment=ENVIRONMENT,
        bucket_start=bucket_start,
        bucket_end=bucket_start,
        first_seen=bucket_start,
        last_seen=bucket_start,
        observation_count=1,
        sample_trace_ids=["a" * 32],
    )
    batch = ObservationBatch(
        # LEGACY_OPERATION_ID is deliberately never declared anywhere - persist_observation_batch's
        # fact-relation MERGE only matches existing nodes (app/telemetry/aggregator.py's
        # _MERGE_FACT_RELATION_QUERY), so the stub Operation node must be supplied explicitly here,
        # the way app.telemetry.adapter's real resolver would for any undeclared destination.
        entities=[
            ObservedOnlyEntity(
                id=LEGACY_OPERATION_ID, label="Operation", name="LegacyPricingService"
            )
        ],
        facts=[
            ObservedFactCandidate(
                subject_id=SERVICE_ID,
                relation_type="CALLS",
                object_id=LEGACY_OPERATION_ID,
                environment=ENVIRONMENT,
                timestamp=bucket_start,
                trace_id="a" * 32,
                evidence=evidence,
            )
        ],
    )
    persist_observation_batch(driver, DATABASE, batch)


def _prepare_fixture(driver) -> None:
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_legacy_pricing(driver)


def _capture_manifest(driver) -> dict:
    """Captures a manifest from whatever state is currently in the database - the same method used
    to generate the real `examples/runtime-demo/fixture-state.json`."""
    node_count, relationship_count = check_fixture_state._read_whole_database_counts(
        driver, database=DATABASE
    )
    state = check_fixture_state._read_actual_state(
        driver, database=DATABASE, coverage_qualification_enabled=True
    )
    snapshot_id, _ = check_fixture_state.snapshot_fingerprint(state)
    manifest_identity = {
        "service_id": SERVICE_ID,
        "environment": ENVIRONMENT,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
    }
    drift_claims = check_fixture_state._read_actual_drift_claims(
        driver, database=DATABASE, manifest=manifest_identity
    )
    return {
        "manifest_version": 1,
        "fixture_id": "test-fixture",
        **manifest_identity,
        "seed_timestamp": "2026-08-26T12:00:00.000000Z",
        "expected_snapshot_id": snapshot_id,
        "total_node_count": node_count,
        "total_relationship_count": relationship_count,
        "expected_drift_claims": drift_claims,
        "canonical_state": json.loads(check_fixture_state.canonical_json_bytes(state)),
    }


def _classify(driver, manifest: dict) -> dict:
    return check_fixture_state.classify_fixture(
        manifest, driver, database=DATABASE, coverage_qualification_enabled=True
    )


def test_empty_on_a_clean_database(driver):
    manifest = {"fixture_id": "test-fixture", "expected_snapshot_id": "aip:snapshot:v1:unused"}
    result = _classify(driver, manifest)
    assert result["classification"] == "EMPTY"
    assert result["mismatches"] == []


def test_complete_matches_a_freshly_captured_state(driver):
    _prepare_fixture(driver)
    manifest = _capture_manifest(driver)

    result = _classify(driver, manifest)

    assert result["classification"] == "COMPLETE"
    assert result["mismatches"] == []
    assert result["actual_snapshot_id"] == manifest["expected_snapshot_id"]
    # The OBSERVED_ONLY drift finding this fixture exists to demonstrate is really in the manifest.
    assert any(
        claim["target"] == "LegacyPricingService" and claim["qualification"] == "OBSERVED_ONLY"
        for claim in manifest["expected_drift_claims"]
    )


def test_repeated_capture_is_deterministic(driver):
    """Proves the same idempotency property `--serve` relies on: preparing once and reading twice
    produces byte-identical manifests, so a second `--serve` run never needs to reseed."""
    _prepare_fixture(driver)
    first = _capture_manifest(driver)
    second = _capture_manifest(driver)
    assert first["expected_snapshot_id"] == second["expected_snapshot_id"]
    assert first["canonical_state"] == second["canonical_state"]


def test_partial_from_an_unrelated_node(driver):
    _prepare_fixture(driver)
    manifest = _capture_manifest(driver)

    with driver.session(database=DATABASE) as session:
        session.run("CREATE (n:Junk {id: 'junk:1'})")

    result = _classify(driver, manifest)

    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert any(m["code"] == "NODE_COUNT_MISMATCH" for m in result["mismatches"])


def test_partial_from_an_unrelated_node_with_no_revision_singleton(driver):
    """The exact I2 §45 case, on a database that has never been imported into at all: one
    unrelated node and nothing else, so no `(:AipInternalState)` singleton exists yet either.
    `get_architecture_drift`'s own stable-read requires that singleton and would otherwise raise
    `RevisionSingletonMissing` uncaught - the checker must still report a normative classification,
    not crash."""
    manifest = {"fixture_id": "test-fixture", "expected_snapshot_id": "aip:snapshot:v1:unused"}

    with driver.session(database=DATABASE) as session:
        session.run("CREATE (n:Junk {id: 'junk:1'})")

    result = _classify(driver, manifest)

    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert any(m["code"] == "MISSING_REVISION_SINGLETON" for m in result["mismatches"])


def test_partial_from_a_missing_observed_relation(driver):
    _prepare_fixture(driver)
    manifest = _capture_manifest(driver)

    with driver.session(database=DATABASE) as session:
        session.run(
            "MATCH (:Service {id: $subject})-[r:CALLS]->(:Operation {id: $object}) DELETE r",
            subject=SERVICE_ID,
            object=LEGACY_OPERATION_ID,
        )

    result = _classify(driver, manifest)

    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    codes = {m["code"] for m in result["mismatches"]}
    assert "RELATIONSHIP_COUNT_MISMATCH" in codes
    assert "OBSERVED_RELATION_MISMATCH" in codes


def test_partial_from_duplicated_telemetry(driver):
    """The exact double-seed scenario `--serve` must refuse to silently accept as COMPLETE
    (spec §15.4/§45): observing the same fact twice changes `observation_count`."""
    _prepare_fixture(driver)
    manifest = _capture_manifest(driver)

    _observe_order_service_calls_legacy_pricing(driver)

    result = _classify(driver, manifest)

    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert any(m["code"] == "OBSERVATION_COUNT_MISMATCH" for m in result["mismatches"])


def test_composite_read_retries_when_the_database_mutates_mid_read(driver, monkeypatch):
    """Injects a real, revision-bumping write in the middle of `_read_consistent_fixture_data`'s
    single read attempt - between its `canonical_snapshot_state` call and its second
    `(:AipInternalState).revision` check - and proves the fence discards that attempt and retries
    rather than combining pre- and post-write data into one classification. The injected write uses
    `bump_revision` inside its own transaction, exactly like every real production write path
    (`app.graph.revision_fence.bump_revision`'s docstring), since an ordinary `CREATE` alone would
    never advance the fence and so would never be caught by it."""
    _prepare_fixture(driver)
    manifest = _capture_manifest(driver)

    real_canonical_snapshot_state = check_fixture_state.canonical_snapshot_state
    call_count = {"n": 0}

    def _inject_racy_write(tx):
        tx.run("CREATE (n:Junk {id: 'junk:race'})")
        bump_revision(tx)

    def _racy_canonical_snapshot_state(session, *, coverage_qualification_enabled):
        call_count["n"] += 1
        state = real_canonical_snapshot_state(
            session, coverage_qualification_enabled=coverage_qualification_enabled
        )
        if call_count["n"] == 1:
            with driver.session(database=DATABASE) as other_session:
                other_session.execute_write(_inject_racy_write)
        return state

    monkeypatch.setattr(
        check_fixture_state, "canonical_snapshot_state", _racy_canonical_snapshot_state
    )

    result = _classify(driver, manifest)

    assert call_count["n"] >= 2, "the revision fence should have retried after the injected write"
    # The retried attempt reads the database only after the injected write has fully landed, so it
    # sees a stable (post-write) revision throughout and correctly reports the mutation - never a
    # mix of the manifest's pre-write expectations with some partial slice of the post-write state.
    assert result["classification"] == "PARTIAL_OR_INCOMPATIBLE"
    assert any(m["code"] == "NODE_COUNT_MISMATCH" for m in result["mismatches"])
