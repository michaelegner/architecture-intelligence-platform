"""The v0.7 runner's recording, and the cost wrapper's identity rules (v0.7.0 I4.1b).

The frozen oracle and the bridge vector are executed through the real REST router and the real MCP
tool against the world service, as the runner does on a candidate; no database is needed for that
part. These tests prove the runner records what happened rather than what is expected: a sabotaged
matcher produces defects, and a rejected request never reaches the service."""

import json
from pathlib import Path

import pytest

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Producer
from app.version import package_version
from benchmarks import i4_metadata
from evaluation.i4 import api_usage_cost_run as cost_run
from evaluation.i4 import api_usage_runner as runner
from evaluation.i4.profiles import V07

ROOT = Path(__file__).resolve().parents[2]
SHA = "c" * 40  # synthetic; never qualification evidence
PRODUCER = Producer(
    name="architecture-intelligence-platform", version=package_version(), build_revision=SHA
)
I3 = json.loads((ROOT / "docs/specifications/0.7.0/i3-vectors/expected-answers.json").read_text())
I4 = json.loads((ROOT / "docs/specifications/0.7.0/i4-vectors/expected-i4.json").read_text())
ANSWERS = [c for doc in (I3, I4) for c in doc["cases"] if c["kind"] == "answer"]


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "verify_candidate", lambda sha, development=False: sha)
    return runner.Recorder(tmp_path, SHA, "A", development=True)


def test_the_oracle_step_records_every_case_on_every_surface_and_all_match(recorder):
    runner.run_oracle(recorder, PRODUCER)

    by_surface = {}
    for record in recorder.records:
        by_surface[record["surface"]] = by_surface.get(record["surface"], 0) + 1
    assert by_surface == {
        "service": len(ANSWERS),
        "rest": len(ANSWERS) + 22,
        "mcp": len(ANSWERS) + 22,
        "derived-properties": 3,
    }
    assert all(record["oracle_match"] is True for record in recorder.records)
    assert {r["case_id"] for r in recorder.records} == V07.required_cases
    assert all(
        r["producer_build_revision"] == SHA for r in recorder.records if r["surface"] == "service"
    )


def test_a_mismatch_is_recorded_as_a_defect_not_hidden(recorder, monkeypatch):
    monkeypatch.setattr(runner, "first_difference", lambda expected, actual: "$: sabotaged")

    runner.run_oracle(recorder, PRODUCER)

    answers = [
        r
        for r in recorder.records
        if r["surface"] in {"service", "rest", "mcp"} and r["case_id"][0] != "V"
    ]
    assert answers and all(
        r["oracle_match"] is False and r["classification"] == "I4_SEMANTIC_DEFECT" for r in answers
    )


def test_a_failing_property_is_recorded_as_a_defect(recorder, monkeypatch):
    def failing(item, *, cases, world_text):
        raise AssertionError("does not hold")

    monkeypatch.setattr(runner, "check_property", failing)

    runner.run_oracle(recorder, PRODUCER)

    properties = [r for r in recorder.records if r["surface"] == "derived-properties"]
    assert len(properties) == 3 and all(r["oracle_match"] is False for r in properties)


def test_expected_abstentions_are_labelled_only_when_they_matched(recorder):
    runner.run_oracle(recorder, PRODUCER)

    classes = {
        r["case_id"]: r["classification"] for r in recorder.records if r["surface"] == "service"
    }
    assert classes["A01"] == "I4_CORRECT" and classes["A02"] == "I4_CORRECT"
    for negative in ("A03", "A10", "A13", "A17", "B07a", "B07b"):
        assert classes[negative] == "I4_EXPECTED_NEGATIVE", negative


def test_recorded_bytes_are_the_canonical_serialization_of_the_payload(recorder):
    recorder.write(
        {"b": 1, "a": [2]},
        surface="service",
        comparison_key="X/1",
        case_id="X",
        request={},
        oracle_match=True,
        classification="I4_CORRECT",
    )
    [record] = recorder.records
    raw = (recorder.out / record["bytes_ref"]).read_bytes()
    assert raw == canonical_json_bytes({"a": [2], "b": 1}) == b'{"a":[2],"b":1}'
    assert record["candidate_sha"] == record["head"] == SHA
    with pytest.raises(AssertionError, match="duplicate capture key"):
        recorder.write(
            {}, surface="service", comparison_key="X/1", case_id="X", request={},
            oracle_match=True, classification="I4_CORRECT",
        )  # fmt: skip


def test_the_ledger_is_not_eligible_after_a_development_run(recorder):
    recorder.finish(0, development=True)
    ledger = json.loads((recorder.out / "ledger.json").read_text())
    assert ledger["qualification_eligible"] is False and ledger["profile"] == "v0.7"
    assert ledger["schema"] == "i4-ledger/1" and ledger["candidate_sha"] == SHA


def test_a_register_key_is_recorded_for_the_bridge_case():
    assert runner._register_keys()["B07a"] == ["S22-07"]


# --- The cost wrapper -------------------------------------------------------------------------


def test_the_cost_wrapper_refuses_a_wrong_candidate_before_docker():
    with pytest.raises((ValueError, AssertionError)):
        cost_run.main(["--candidate-sha", "f" * 40, "--out", "unused.json"])


def test_the_cost_wrapper_requires_an_explicit_candidate():
    with pytest.raises(SystemExit):
        cost_run.main(["--out", "unused.json"])


def _checks(sha, **changes):
    names = sorted(V07.required_ci_checks)
    runs = [
        {"id": i, "name": n, "status": "completed", "conclusion": "success", "head_sha": sha}
        for i, n in enumerate(names)
    ]
    for run in runs[:1]:
        run.update(changes)
    return runs


def test_the_cost_artifact_carries_the_candidates_check_runs_and_their_blockers(monkeypatch):
    monkeypatch.setattr(cost_run, "check_runs", lambda sha: (_checks(sha), None))
    section, blockers = cost_run.ci_section(SHA)
    assert blockers == [] and section["blockers"] == [] and len(section["checks"]) == 13

    monkeypatch.setattr(
        cost_run, "check_runs", lambda sha: (_checks(sha, conclusion="failure"), None)
    )
    assert cost_run.ci_section(SHA)[1]

    monkeypatch.setattr(cost_run, "check_runs", lambda sha: (_checks("b" * 40), None))
    assert any("identity mismatch" in b for b in cost_run.ci_section(SHA)[1])

    monkeypatch.setattr(cost_run, "check_runs", lambda sha: (None, "boom"))
    assert cost_run.ci_section(SHA)[1] == ["exact-SHA CI query failed"]


class _Container:
    image = "neo4j:test"

    def get_wrapped_container(self):
        return type("Wrapped", (), {"id": "container-id"})()


def test_the_default_metadata_pins_are_still_the_v06_inputs(monkeypatch):
    monkeypatch.setattr(i4_metadata, "verify_candidate", lambda sha: sha)
    result = i4_metadata.metadata(SHA, PRODUCER, _Container(), {"profile": "x"})
    pins = result["input_pins"]
    assert any(path.startswith("docs/specifications/0.6.0/") for path in pins)
    assert "tests/integration/test_locality_oracle.py" in pins
    assert not any(path.startswith("docs/specifications/0.7.0/") for path in pins)
    assert result["candidate_sha"] == SHA and result["qualification_eligible"] is True


def test_v07_metadata_pins_the_v07_inputs_and_not_the_recorded_result(monkeypatch):
    monkeypatch.setattr(i4_metadata, "verify_candidate", lambda sha: sha)
    result = i4_metadata.metadata(
        SHA,
        PRODUCER,
        _Container(),
        {"profile": "i3"},
        pin_roots=cost_run.PIN_ROOTS,
        pin_files=(),
        skip_pins=("-cost.json",),
    )
    pins = result["input_pins"]
    assert "docs/specifications/0.7.0/i4-coverage-register.md" in pins
    assert "evaluation/i4/profiles.py" in pins
    assert not any(path.endswith("-cost.json") for path in pins)
    assert not any(path.startswith("docs/specifications/0.6.0/") for path in pins)
