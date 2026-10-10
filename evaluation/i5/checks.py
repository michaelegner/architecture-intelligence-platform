"""Assertions against the adopted source-derived dossier, never expectations from AIP output."""

import json
from pathlib import Path

from app.architecture_intelligence.canonical_json import canonical_json_bytes

canonical_bytes = canonical_json_bytes


def facts_from_dossier(path: Path) -> dict:
    text = path.read_text()
    assert "**Review/adoption:** ADOPTED by Michael Egner" in text, "owner adoption is required"
    return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])


def check_query(answer: dict, facts: dict, state: str) -> None:
    data = answer["data"]
    assert data["coverage"] == "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"
    inventory = data["inventory"]
    assert inventory["completeness"] == "COMPLETE"
    assert inventory["next_cursor"] is None and inventory["continuation"] is False
    assert inventory["evaluated_v2_candidate_count"] == 2
    assert inventory["admitted_pair_count"] == 2
    assert inventory["cap_reached"] == [] and inventory["i2_truncated"] is False
    assert inventory["evaluated_sources"] == [
        facts["captures"][state] | {"cluster_uid": facts["cluster_uid"]}
    ]
    candidates = {c["v2_evidence_id"]: c for c in data["candidates"]}
    assert set(candidates) == {c["v2_id"] for c in facts["candidates"].values()}
    localities = {l["workload"]["uid"]: l for l in data["localities"]}
    expected_labels = ("P1", "P2") if state == "c1" else ("P2",)
    assert set(localities) == {facts["candidates"][p]["workload_uid"] for p in expected_labels}
    for label, expected in facts["candidates"].items():
        candidate = candidates[expected["v2_id"]]
        [pair] = candidate["pairs"]
        capture = facts["captures"][state]
        assert pair["source"] == {k: capture[k] for k in ("source_instance_id", "revision")}
        assert pair["phase"] == 4
        if label not in expected_labels:
            assert candidate["disposition"] == pair["disposition"] == "UNRESOLVED"
            assert candidate["reasons"] == pair["reasons"] == ["LOCALITY_CAPTURE_MISSING_POD"]
            assert candidate["workload"] is pair["workload"] is None
            continue
        assert candidate["disposition"] == pair["disposition"] == "APPLICABLE"
        assert candidate["workload"]["uid"] == pair["workload"]["uid"] == expected["workload_uid"]
        chain_refs = facts["chains"][state][label]["capture_refs"]
        assert pair["evidence_refs"] == chain_refs
        locality = localities[expected["workload_uid"]]
        assert locality["target_runtime_scope"] == "UNKNOWN" and locality["lineage_complete"]
        [assessment] = locality["assessments"]
        assert assessment["applicability"] == "APPLICABLE"
        assert assessment["object_operation_id"] == expected["operation_id"]
        assert assessment["qualification"] == expected["qualification"]
        assert assessment["observation"]["evidence_ids"] == [expected["v2_id"]]
        assert assessment["capture_evidence_refs"] == chain_refs
        assert assessment["selected_captures"] == [
            {
                k: capture[k]
                for k in ("source_instance_id", "revision", "evidence_mode", "captured_at")
            }
        ]
        assert bool(assessment["declared_evidence_ids"]) == (label == "P1")
        assert assessment["source_limitations"] == []
        [group] = locality["provider_groups"]
        provider = "service:pricing" if label == "P1" else "service:legacy-pricing"
        assert group["provider_service_id"] == provider
        assert group["operation_ids"] == [expected["operation_id"]]
        assert locality["unresolved_owner_operations"] == []
    serialized = json.dumps(answer)
    assert "NOT_OBSERVED_IN_WINDOW" not in serialized


def check_comparison(answer: dict, facts: dict) -> None:
    comparison = answer["data"]["comparison"]
    assert comparison["completeness"] == "COMPLETE"
    assert [s["evaluation"] for s in comparison["scopes"]] == ["POSITIVE"] * 2
    assert comparison["in_both"] == comparison["qualification_differs"] == []
    for label, field in (("P1", "only_in_first"), ("P2", "only_in_second")):
        [membership] = comparison[field]
        assert membership["operation_id"] == facts["candidates"][label]["operation_id"]
        assert membership["side"]["qualification"] == facts["candidates"][label]["qualification"]


def check_evidence(answer: dict, facts: dict, state: str) -> None:
    entries = answer["data"]["entries"]
    assert all(entry["status"] == "RESOLVED" for entry in entries)
    by_ref = {entry["ref"]: entry for entry in entries}
    expected_refs = set()
    for label, expected in facts["candidates"].items():
        expected_refs.add(expected["v2_id"])
        record = by_ref[expected["v2_id"]]["scoped_record"]
        assert record["subject_id"] == "service:orders"
        assert record["object_id"] == expected["operation_id"]
        assert record["caller_pod_uid"] == expected["pod_uid"]
        assert record["caller_cluster_uid"] == facts["cluster_uid"]
        assert record["observation_count"] == expected["count"]
        assert record["bucket_utc_day"] == facts["day"]
        for ref in facts["chains"][state].get(label, {}).get("capture_refs", []):
            expected_refs.add(ref)
            capture = by_ref[ref]["capture_record"]
            assert capture["source_revision"] == facts["captures"][state]["revision"]
            assert capture["source_locator"] == "resources.yaml"
    assert set(by_ref) == expected_refs


def check_not_found(answer: dict) -> None:
    assert answer["outcome"] == "NOT_ANSWERED"
    assert all(
        entry["status"] == "NOT_FOUND"
        and entry["scoped_record"] is None
        and entry["capture_record"] is None
        for entry in answer["data"]["entries"]
    )


def check_stale(answer: dict) -> None:
    assert answer["outcome"] == "NOT_ANSWERED" and answer["data"] is None
    assert [l["code"] for l in answer["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
