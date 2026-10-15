"""v0.7.0 I4.1c: the real APISIX captures, imported through the production source path, asked of the
service, REST and negotiated MCP, against the frozen readings (I4 spec §5; decision record D4).

The readings (`expected-replay.json`) were written before the captures were taken. These tests run
the same steps as the I4 runner (`evaluation.i4.api_usage_runner.run_replay`) with a synthetic
candidate identity, then check what only a real database shows: every reading holds on every
surface, a second clean import reproduces every answer byte for byte, the revision step replaces
the state authoritatively, and no credential reaches an answer."""

from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import Producer
from app.version import package_version
from evaluation.i4 import api_usage_runner as runner
from evaluation.i4 import apisix_replay as replay

SHA = "d" * 40  # synthetic; never qualification evidence


@pytest.fixture
def identity(monkeypatch, neo4j_container):
    monkeypatch.setattr(runner, "verify_candidate", lambda sha, development=False: sha)
    monkeypatch.setenv("I4_CANDIDATE_SHA", SHA)
    monkeypatch.setenv("AIP_BUILD_REVISION", SHA)
    return Producer(
        name="architecture-intelligence-platform", version=package_version(), build_revision=SHA
    )


def _replay_run(name: str, driver, producer, tmp_path: Path) -> runner.Recorder:
    recorder = runner.Recorder(tmp_path / f"out-{name}", SHA, name, development=True)
    runner.run_replay(recorder, driver, producer, tmp_path / f"world-{name}")
    return recorder


def test_every_frozen_reading_holds_on_the_service_rest_and_mcp(driver, identity, tmp_path):
    recorder = _replay_run("A", driver, identity, tmp_path)

    by_case = {}
    for record in recorder.records:
        by_case.setdefault(record["case_id"], {})[record["surface"]] = record
    assert set(by_case) == set(replay.case_ids())
    for case, surfaces in by_case.items():
        assert set(surfaces) == {"service", "rest", "mcp"}, case
        assert all(r["oracle_match"] is True for r in surfaces.values()), case
    # the abstentions are the readings that were expected to abstain, nothing else
    negative = {
        c for c, s in by_case.items() if s["service"]["classification"] == "I4_EXPECTED_NEGATIVE"
    }
    assert negative == {"N1", "N2", "N3", "REVb", "REVd", "REVe", "W-INVALID", "W-NONE"}


def test_a_second_clean_import_reproduces_every_answer_byte_for_byte(driver, identity, tmp_path):
    first = _replay_run("A", driver, identity, tmp_path)
    second = _replay_run("B", driver, identity, tmp_path)

    digests = lambda recorder: {r["key"]: r["canonical_digest"] for r in recorder.records}
    assert digests(first) == digests(second) and len(digests(first)) == 3 * len(replay.case_ids())
    assert first.resets == second.resets == [{"nodes_before_schema": 0}]


def test_no_credential_reaches_an_answer(driver, identity, tmp_path):
    recorder = _replay_run("A", driver, identity, tmp_path)

    blob = b"".join(
        (recorder.out / record["bytes_ref"]).read_bytes() for record in recorder.records
    )
    assert recorder.records and not any(secret.encode() in blob for secret in replay.FAKE_SECRETS)
    assert b"key-auth" not in blob and b"apikey" not in blob


def test_the_second_revision_replaces_the_first_authoritatively(driver, identity, tmp_path):
    runner._clean_state(runner.Recorder(tmp_path / "o", SHA, "A", development=True), driver)
    replay.import_revision(driver, "r1", tmp_path / "w")
    first = replay.read_state(driver)
    replay.import_revision(driver, "r2", tmp_path / "w")
    second = replay.read_state(driver)

    routes = lambda state: set(replay.route_ids(state))
    assert routes(first) - routes(second) == {"billing-route"}
    assert routes(second) - routes(first) == {"reports-route"}
    allow = {
        (row["consumer_id"], row["route_id"])
        for row in second["gateway_configuration_v1"]["configured_access"]
    }
    consumers = replay.consumer_ids(second)
    orders = replay.route_ids(second)["orders-route"]
    assert {c for c, r in allow if r == orders} == {consumers["alice"], consumers["erin"]}
    assert first["api_usage_v1"]["windows"][0]["id"] != second["api_usage_v1"]["windows"][0]["id"]
    assert len(second["api_usage_v1"]["windows"]) == 1, "one window per gateway and environment"
    assert "bob" in consumers  # the consumer remains; its access does not
