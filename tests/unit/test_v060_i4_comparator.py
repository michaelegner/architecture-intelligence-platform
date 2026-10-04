"""Regression checks for raw comparison and refusal to qualify incomplete evidence."""

import hashlib
import json

import pytest

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from evaluation.i4.__main__ import REQUIRED_CASES, compare_runs

SHA = "a" * 40  # synthetic unit fixture; never qualification evidence


def _runs(root):
    for index, name in enumerate(("A", "B")):
        directory = root / name
        directory.mkdir()
        records = []
        for case in sorted(REQUIRED_CASES):
            surfaces = ("rest", "mcp") if case.startswith("Q") else ("service", "rest", "mcp")
            if case in {"X01", "X02", "X26"}:
                surfaces = (*surfaces, "mcp-independent-client")
            for surface in surfaces:
                payload = {
                    "snapshot": {"snapshot_id": "unchanged"},
                    "ordered": [1, 2],
                    "producer": {"build_revision": SHA},
                }
                raw = canonical_json_bytes(payload)
                filename = f"{case}-{surface}.json"
                (directory / filename).write_bytes(raw)
                records.append(
                    {
                        "key": f"{case}/{surface}",
                        "comparison_key": case,
                        "case_id": case,
                        "surface": surface,
                        "canonical_digest": hashlib.sha256(raw).hexdigest(),
                        "bytes_ref": filename,
                        "oracle_match": True,
                        "candidate_sha": SHA,
                        "head": SHA,
                        "producer_build_revision": SHA,
                        "request": {"mode": "evidence" if case == "X26" else "query"},
                    }
                )
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
    ledger_path = root / "B/ledger.json"
    ledger = json.loads(ledger_path.read_text())
    mutation(ledger)
    ledger_path.write_text(json.dumps(ledger))


def test_identical_raw_artifacts_and_complete_gates_pass(tmp_path):
    _runs(tmp_path)
    result = compare_runs(tmp_path)
    assert result["ab_equal"] and result["cross_surface_equal"]
    assert result["blockers"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("snapshot", {"snapshot_id": "changed"}),
        ("ordered", [2, 1]),
        ("producer", {"build_revision": "b" * 40}),
    ],
)
def test_semantic_identity_or_order_cannot_be_normalized_away(tmp_path, field, value):
    _runs(tmp_path)

    def mutation(ledger):
        record = next(
            r for r in ledger["records"] if r["case_id"] == "X01" and r["surface"] == "service"
        )
        path = tmp_path / "B" / record["bytes_ref"]
        payload = json.loads(path.read_bytes())
        payload[field] = value
        raw = canonical_json_bytes(payload)
        path.write_bytes(raw)
        record["canonical_digest"] = hashlib.sha256(raw).hexdigest()

    _change(tmp_path, mutation)
    result = compare_runs(tmp_path)
    assert not result["ab_equal"] and not result["cross_surface_equal"]
    assert result["differences"]


@pytest.mark.parametrize(
    "defect",
    [
        "missing_case",
        "same_process",
        "development",
        "unverified_oracle",
        "missing_surface",
        "missing_client",
    ],
)
def test_incomplete_or_ineligible_evidence_blocks_qualification(tmp_path, defect):
    _runs(tmp_path)

    def mutation(ledger):
        if defect == "missing_case":
            ledger["records"] = [r for r in ledger["records"] if r["case_id"] != "B01b"]
        elif defect == "missing_surface":
            ledger["records"] = [r for r in ledger["records"] if r["key"] != "X01/mcp"]
        elif defect == "missing_client":
            ledger["records"] = [
                r for r in ledger["records"] if r["surface"] != "mcp-independent-client"
            ]
        elif defect == "same_process":
            ledger["process_id"] = 1
        elif defect == "development":
            ledger["qualification_eligible"] = False
        else:
            ledger["records"][0]["oracle_match"] = None

    _change(tmp_path, mutation)
    assert compare_runs(tmp_path)["blockers"]
