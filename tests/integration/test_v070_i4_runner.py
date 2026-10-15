"""v0.7.0 I4.1b: the v0.7 runner and comparator agree on real output (wiring, never qualification).

Two runs of the runner's steps are produced in this process against the integration Neo4j, with a
synthetic candidate identity and the checkout check stubbed (a CI checkout is shallow). The ledger
fields that identify two separate processes and containers are set by hand, then the A/B comparator
under the v0.7 profile must find no blocker: the runner records what the comparator requires, every
surface's bytes agree, the frozen oracle and the bridge vector match, and the independent client
saw the same answers. Run in development mode, so the result is never eligible to qualify."""

import json
from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import Producer
from app.version import package_version
from evaluation.i4 import api_usage_runner as runner
from evaluation.i4.__main__ import compare_runs
from evaluation.i4.profiles import V07

SHA = "c" * 40  # synthetic; never qualification evidence


@pytest.fixture
def identity(monkeypatch, neo4j_container):
    monkeypatch.setattr(runner, "verify_candidate", lambda sha, development=False: sha)
    monkeypatch.setenv("I4_CANDIDATE_SHA", SHA)
    monkeypatch.setenv("AIP_BUILD_REVISION", SHA)
    monkeypatch.setenv("NEO4J_URI", neo4j_container.get_connection_url())
    monkeypatch.setenv("NEO4J_USER", neo4j_container.username)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_container.password)
    return Producer(
        name="architecture-intelligence-platform", version=package_version(), build_revision=SHA
    )


def _one_run(name: str, out: Path, driver, producer: Producer, tmp_path: Path) -> None:
    recorder = runner.Recorder(out, SHA, name, development=True)
    recorder.ledger["container_id"] = f"container-{name}"
    runner.run_oracle(recorder, producer)
    runner.run_real_import(recorder, driver, producer, tmp_path / f"world-{name}")
    runner.run_replay(recorder, driver, producer, tmp_path / f"replay-{name}")
    for record in recorder.records:
        record["container_id"] = recorder.ledger["container_id"]
    recorder.ledger["process_id"] = {"A": 1, "B": 2}[name]
    recorder.finish(0, development=True)
    ledger_path = out / "ledger.json"
    ledger = json.loads(ledger_path.read_text())
    ledger["qualification_eligible"] = True  # the synthetic stand-in for two clean processes
    ledger["tests"] = [{"nodeid": "synthetic", "outcome": "passed"}]
    ledger_path.write_text(json.dumps(ledger))


def test_the_runner_records_what_the_comparator_requires(driver, identity, tmp_path):
    for name in ("A", "B"):
        (tmp_path / name).mkdir()
        _one_run(name, tmp_path / name, driver, identity, tmp_path)

    result = compare_runs(tmp_path, V07)

    assert result["blockers"] == []
    assert result["ab_equal"] and result["cross_surface_equal"]
    ledger = json.loads((tmp_path / "A/ledger.json").read_text())
    cases = {record["case_id"] for record in ledger["records"]}
    assert V07.required_cases <= cases
    assert {"RT01a", "RT01b", "RT01c", "RT01d"} <= cases
    assert all(record["oracle_match"] is True for record in ledger["records"])
    assert sum(r["surface"] == "mcp-independent-client" for r in ledger["records"]) == 3
    # one reset per world: the real import and the replay each start from an empty graph
    assert ledger["resets"] == [{"nodes_before_schema": 0}] * 2
    assert ledger["profile"] == "v0.7" and ledger["schema"] == "i4-ledger/1"
