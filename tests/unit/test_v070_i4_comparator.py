"""The A/B comparator under the v0.7 profile (v0.7.0 I4.1b; I4 spec §3, §7, §10).

Synthetic ledgers, never qualification evidence. Each blocker class has a positive case (the
complete evidence passes) and a negative one (the defect blocks), so a comparator that accepts
everything fails here."""

import hashlib
import json
from pathlib import Path

import pytest

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from evaluation.i4.__main__ import compare_runs
from evaluation.i4.profiles import V06, V07

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/specifications/0.7.0"
SHA = "a" * 40  # synthetic; never qualification evidence
CASES = {
    case["id"]: case["kind"]
    for name in ("i3-vectors/expected-answers.json", "i4-vectors/expected-i4.json")
    for case in json.loads((SPEC / name).read_text(encoding="utf-8"))["cases"]
}
ANSWERS = sorted(c for c, kind in CASES.items() if kind == "answer")
PROPERTIES = sorted(c for c, kind in CASES.items() if kind == "property")
REQUESTS = sorted(c for c, kind in CASES.items() if kind == "request")
# the real-import questions with an independent-client record: two queries and one evidence
CLIENT = {"RT01a": "query", "RT01b": "query", "RT01c": "evidence"}


def _record(case, surface, payload, *, mode="query"):
    raw = canonical_json_bytes(payload)
    return raw, {
        "key": f"{case}/{surface}",
        "comparison_key": f"{case}/1",
        "case_id": case,
        "surface": surface,
        "canonical_digest": hashlib.sha256(raw).hexdigest(),
        "bytes_ref": f"{case}-{surface}.json",
        "oracle_match": True,
        "candidate_sha": SHA,
        "head": SHA,
        "producer_build_revision": SHA,
        "request": {"mode": mode},
    }


def _runs(root):
    for index, name in enumerate(("A", "B")):
        directory = root / name
        directory.mkdir()
        records = []

        def add(case, surface, payload, *, mode="query", directory=directory, records=records):
            raw, record = _record(case, surface, payload, mode=mode)
            (directory / record["bytes_ref"]).write_bytes(raw)
            records.append(record)

        answer = {
            "snapshot": {"snapshot_id": "s"},
            "rows": [1, 2],
            "producer": {"build_revision": SHA},
        }
        for case in [*ANSWERS, *CLIENT]:
            mode = CLIENT.get(case, "evidence" if case.startswith("E") else "query")
            surfaces = ["service", "rest", "mcp"] + (
                ["mcp-independent-client"] if case in CLIENT else []
            )
            for surface in surfaces:
                add(case, surface, answer, mode=mode)
        for case in REQUESTS:
            for surface in ("rest", "mcp"):
                add(case, surface, {"validation_error": True})
        for case in PROPERTIES:
            add(case, "derived-properties", {"property": case, "holds": True})
        ledger = {
            "run": name,
            "candidate_sha": SHA,
            "process_id": index + 1,
            "container_id": f"container-{name}",
            "resets": [{"nodes_before_schema": 0}],
            "records": records,
            "exit_code": 0,
            "tests": [{"outcome": "passed"}],
            "qualification_eligible": True,
        }
        (directory / "ledger.json").write_text(json.dumps(ledger))


def _change(root, mutation):
    path = root / "B/ledger.json"
    ledger = json.loads(path.read_text())
    mutation(ledger)
    path.write_text(json.dumps(ledger))


def test_the_profile_requires_exactly_the_frozen_cases():
    assert V07.required_cases == set(CASES)
    assert len(CASES) == 60 and V07.rejection_prefix == "V"


def test_complete_evidence_passes(tmp_path):
    _runs(tmp_path)
    result = compare_runs(tmp_path, V07)
    assert result["blockers"] == [] and result["ab_equal"] and result["cross_surface_equal"]


def test_the_v06_profile_still_blocks_a_v07_ledger(tmp_path):
    _runs(tmp_path)
    assert any("missing required cases" in b for b in compare_runs(tmp_path, V06)["blockers"])


def test_a_property_verdict_needs_no_adapter_surfaces(tmp_path):
    """The `derived-` surfaces carry a verdict, not an answer, so they skip the parity rule."""
    _runs(tmp_path)
    ledger = json.loads((tmp_path / "A/ledger.json").read_text())
    assert any(r["surface"] == "derived-properties" for r in ledger["records"])
    assert compare_runs(tmp_path, V07)["blockers"] == []


def test_a_request_case_needs_only_rest_and_mcp(tmp_path):
    _runs(tmp_path)
    assert compare_runs(tmp_path, V07)["blockers"] == []

    def drop_mcp(ledger):
        ledger["records"] = [r for r in ledger["records"] if r["key"] != f"{REQUESTS[0]}/mcp"]

    _change(tmp_path, drop_mcp)
    assert any("missing adapter rejection" in b for b in compare_runs(tmp_path, V07)["blockers"])


@pytest.mark.parametrize(
    "defect",
    [
        "missing_case",
        "missing_bridge_case",
        "same_process",
        "same_container",
        "no_reset",
        "development",
        "unverified_oracle",
        "failed_oracle",
        "missing_surface",
        "missing_client",
        "failed_worker_test",
        "producer_mismatch",
        "candidate_mismatch",
    ],
)
def test_incomplete_or_ineligible_evidence_blocks_qualification(tmp_path, defect):
    _runs(tmp_path)

    def mutation(ledger):
        records = ledger["records"]
        if defect == "missing_case":
            ledger["records"] = [r for r in records if r["case_id"] != "A15e"]
        elif defect == "missing_bridge_case":
            ledger["records"] = [r for r in records if r["case_id"] != "B07a"]
        elif defect == "missing_surface":
            ledger["records"] = [r for r in records if r["key"] != "A01/mcp"]
        elif defect == "missing_client":
            ledger["records"] = [r for r in records if r["surface"] != "mcp-independent-client"]
        elif defect == "same_process":
            ledger["process_id"] = 1
        elif defect == "same_container":
            ledger["container_id"] = "container-A"
        elif defect == "no_reset":
            ledger["resets"] = []
        elif defect == "development":
            ledger["qualification_eligible"] = False
        elif defect == "unverified_oracle":
            records[0]["oracle_match"] = None
        elif defect == "failed_oracle":
            records[0]["oracle_match"] = False
        elif defect == "failed_worker_test":
            ledger["tests"] = [{"outcome": "skipped"}]
        elif defect == "producer_mismatch":
            next(r for r in records if r["case_id"] == "A01")["producer_build_revision"] = "b" * 40
        else:
            records[0]["candidate_sha"] = "b" * 40

    _change(tmp_path, mutation)
    assert compare_runs(tmp_path, V07)["blockers"]


@pytest.mark.parametrize("surface", ["service", "rest", "mcp", "mcp-independent-client"])
def test_one_surface_differing_by_a_byte_is_a_cross_surface_mismatch(tmp_path, surface):
    _runs(tmp_path)
    for run in ("A", "B"):
        path = tmp_path / run / f"RT01a-{surface}.json"
        payload = json.loads(path.read_bytes())
        payload["rows"] = [2, 1]
        raw = canonical_json_bytes(payload)
        path.write_bytes(raw)
        ledger_path = tmp_path / run / "ledger.json"
        ledger = json.loads(ledger_path.read_text())
        next(r for r in ledger["records"] if r["key"] == f"RT01a/{surface}")["canonical_digest"] = (
            hashlib.sha256(raw).hexdigest()
        )
        ledger_path.write_text(json.dumps(ledger))
    result = compare_runs(tmp_path, V07)
    assert not result["cross_surface_equal"] and result["blockers"]


def test_a_byte_difference_between_the_runs_is_never_normalized_away(tmp_path):
    _runs(tmp_path)
    path = tmp_path / "B/A01-service.json"
    payload = json.loads(path.read_bytes())
    payload["snapshot"] = {"snapshot_id": "changed"}
    raw = canonical_json_bytes(payload)
    path.write_bytes(raw)
    ledger = json.loads((tmp_path / "B/ledger.json").read_text())
    next(r for r in ledger["records"] if r["key"] == "A01/service")["canonical_digest"] = (
        hashlib.sha256(raw).hexdigest()
    )
    (tmp_path / "B/ledger.json").write_text(json.dumps(ledger))
    result = compare_runs(tmp_path, V07)
    assert not result["ab_equal"] and result["differences"]
