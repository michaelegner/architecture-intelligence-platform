"""Recomputes the frozen v0.6.0 I2.5a full-graph after-`snapshot_id` vector
(`docs/specifications/0.6.0/i2-vectors/snapshot-after.json`; I2 spec §11 gate (b), decision record
D5 and D15).

The expected state was written by hand and hashed with `sha256sum` before the conditional keys
were implemented. This module checks it with the standard library only and deliberately imports
nothing from `app/`: it is an independent reference, not a test of AIP. It also folds the recorded
fixture seeds by the documented merge rules, so the recorded inputs demonstrably produce the
recorded state. I2.5b then requires a real graph built from those inputs to yield this exact id.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/specifications/0.6.0"
VECTOR = json.loads((SPEC / "i2-vectors/snapshot-after.json").read_text(encoding="utf-8"))
I1 = json.loads((SPEC / "i1-vectors/v2-evidence-id.json").read_text(encoding="utf-8"))
STATE = VECTOR["expected_state"]
FIXTURE = VECTOR["fixture"]
SEEDS = FIXTURE["telemetry_unit"]["seeds"]

V0_5_KEYS = {
    "version",
    "services",
    "operations",
    "queues",
    "topics",
    "subscriptions",
    "messages",
    "schemas",
    "evidence",
    "relations",
    "semantic_config",
    "deployment_workloads",
    "deployment_captured_pods",
    "deployment_workload_owns_pod",
    "deployment_runtime_identity_observations",
    "deployment_reconciliation_rule",
}
V2_ENTRY_FIELDS = {
    "id",
    "contract_version",
    "source_type",
    "evidence_type",
    "relation_type",
    "environment",
    "bucket_utc_day",
    "subject_id",
    "object_id",
    "caller_cluster_uid",
    "caller_pod_uid",
    "first_seen",
    "last_seen",
    "observation_count",
    "correlation_mode",
    "sample_trace_ids",
    "k8s_namespace_name",
    "k8s_pod_name",
    "k8s_deployment_name",
    "k8s_statefulset_name",
    "k8s_daemonset_name",
    "conflicting_consistency_attributes",
    "key_rule_id",
    "key_rule_version",
    "normalization_rule_id",
    "normalization_rule_version",
}
K8S_NAMES = (
    "k8s_namespace_name",
    "k8s_pod_name",
    "k8s_deployment_name",
    "k8s_statefulset_name",
    "k8s_daemonset_name",
)
SCOPE_FIELDS = {
    "source_instance_id",
    "discovery_scope_id",
    "revision",
    "cluster_uid",
    "namespaces",
    "evidence_mode",
    "captured_at",
}
MODE_STRENGTH = {"CLIENT_ONLY": 2, "CLIENT_SERVER": 3}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _length_delimited(*parts: str) -> bytes:
    """I1 spec §5.1: each UTF-8 part prefixed by its byte length, unsigned 8-byte big-endian."""
    return b"".join(len(p.encode()).to_bytes(8, "big") + p.encode() for p in parts)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


def test_the_digest_and_ids_match_the_recorded_bytes():
    digest = hashlib.sha256(VECTOR["canonical_bytes_utf8"].encode("utf-8")).hexdigest()
    assert digest == VECTOR["sha256"]
    assert VECTOR["snapshot_id"] == f"aip:snapshot:v1:{digest}"
    assert VECTOR["model_revision"] == f"sha256:{digest}"


def test_the_bytes_are_the_canonical_form_of_the_expected_state():
    assert _canonical(STATE) == VECTOR["canonical_bytes_utf8"]


def test_the_state_is_version_3_with_exactly_the_two_conditional_keys_added():
    assert STATE["version"] == 3
    assert set(STATE) == V0_5_KEYS | {"scoped_observed_calls_v2", "scoped_capture_scopes_v2"}


def test_the_scoped_calls_value_is_the_frozen_i1_fragment():
    fragment = I1["snapshot_fragment"]
    assert _canonical(STATE["scoped_observed_calls_v2"]) == fragment["canonical_bytes_utf8"]
    entries = STATE["scoped_observed_calls_v2"]
    assert [e["id"] for e in entries] == sorted(e["id"] for e in entries)
    for entry in entries:
        assert set(entry) == V2_ENTRY_FIELDS
        assert all(name in entry for name in K8S_NAMES)  # explicit null, never dropped (D15.3)


def test_the_scope_entries_have_exactly_the_d5_fields():
    scopes = STATE["scoped_capture_scopes_v2"]
    assert [s["source_instance_id"] for s in scopes] == sorted(
        s["source_instance_id"] for s in scopes
    )
    for scope in scopes:
        assert set(scope) == SCOPE_FIELDS
        assert scope["namespaces"] == sorted(scope["namespaces"])


def test_the_kubernetes_ids_follow_their_documented_formulas():
    capture = FIXTURE["kubernetes_capture"]
    [scope] = STATE["scoped_capture_scopes_v2"]
    source_key = _length_delimited(capture["configured_source_id"], capture["cluster_uid"])
    scope_key = _length_delimited(
        capture["configured_scope_id"], f"urn:aip:k8s-cluster:{capture['cluster_uid']}"
    )
    assert scope["source_instance_id"] == (
        f"urn:aip:source:kubernetes:{hashlib.sha256(source_key).hexdigest()}"
    )
    assert scope["discovery_scope_id"] == (
        f"urn:aip:discovery-scope:{hashlib.sha256(scope_key).hexdigest()}"
    )
    assert (scope["revision"], scope["cluster_uid"], scope["captured_at"]) == (
        capture["revision"],
        capture["cluster_uid"],
        capture["captured_at"],
    )
    assert (scope["namespaces"], scope["evidence_mode"]) == (capture["namespaces"], capture["mode"])
    # Zero resources: no deployment state at all.
    assert all(
        STATE[key] == []
        for key in V0_5_KEYS
        if key.startswith("deployment_") and key != "deployment_reconciliation_rule"
    )


def test_the_seeds_fold_into_exactly_the_recorded_v2_records():
    """I1 v2 contract §§1-3: the ten-field key, min/max seen, summed count, strongest mode, the
    sorted smallest five distinct samples and the absorbing per-field conflict."""
    folded: dict[str, dict] = {}
    for seed in SEEDS:
        key = {
            "contract_version": 2,
            "source_type": "OPENTELEMETRY",
            "evidence_type": "OBSERVED",
            "relation_type": "CALLS",
            **{
                k: seed[k]
                for k in (
                    "environment",
                    "bucket_utc_day",
                    "subject_id",
                    "object_id",
                    "caller_cluster_uid",
                    "caller_pod_uid",
                )
            },
        }
        vid = (
            "evidence:otel:calls-scoped:v2:" + hashlib.sha256(_canonical(key).encode()).hexdigest()
        )
        record = folded.setdefault(vid, {"seeds": []})
        record["seeds"].append(seed)
    by_id = {e["id"]: e for e in STATE["scoped_observed_calls_v2"]}
    assert set(folded) == set(by_id)
    for vid, group in folded.items():
        seeds = group["seeds"]
        expected = by_id[vid]
        assert expected["observation_count"] == len(seeds)
        assert _instant(expected["first_seen"]) == min(_instant(s["fact_timestamp"]) for s in seeds)
        assert _instant(expected["last_seen"]) == max(_instant(s["fact_timestamp"]) for s in seeds)
        assert expected["correlation_mode"] == max(
            (s["correlation_mode"] for s in seeds), key=MODE_STRENGTH.__getitem__
        )
        assert expected["sample_trace_ids"] == sorted({s["trace_id"] for s in seeds})[:5]
        flagged = []
        for name in K8S_NAMES:
            values = {s[name] for s in seeds if s.get(name) is not None}
            if len(values) > 1:
                flagged.append(name)
                assert expected[name] is None
            else:
                assert expected[name] == (values.pop() if values else None)
        assert expected["conflicting_consistency_attributes"] == sorted(flagged)


def test_the_seeds_fold_into_exactly_the_recorded_v1_bucket_and_relation():
    [u01] = [v for v in I1["v1_unchanged"] if v["id"] == "U01-v1-for-V01-and-V03"]
    [evidence] = STATE["evidence"]
    assert evidence["id"] == u01["evidence_id"]
    first12 = hashlib.sha256(u01["seed_utf8"].encode()).hexdigest()[:12]
    assert u01["evidence_id"].endswith(first12)
    assert evidence["observation_count"] == len(SEEDS)
    assert _instant(evidence["first_seen"]) == min(_instant(s["fact_timestamp"]) for s in SEEDS)
    assert _instant(evidence["last_seen"]) == max(_instant(s["fact_timestamp"]) for s in SEEDS)
    assert evidence["sample_trace_ids"] == sorted({s["trace_id"] for s in SEEDS})
    assert evidence["correlation_mode"] == "CLIENT_SERVER"
    assert STATE["relations"] == [
        {
            "type": "CALLS",
            "source_id": SEEDS[0]["subject_id"],
            "target_id": SEEDS[0]["object_id"],
            "evidence_ids": [u01["evidence_id"]],
        }
    ]


def test_no_v2_id_reaches_the_legacy_evidence_or_relations():
    v2_ids = {e["id"] for e in STATE["scoped_observed_calls_v2"]}
    assert v2_ids.isdisjoint({e["id"] for e in STATE["evidence"]})
    assert v2_ids.isdisjoint({i for r in STATE["relations"] for i in r["evidence_ids"]})
