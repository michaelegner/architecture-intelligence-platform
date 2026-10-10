"""Recomputes the frozen v0.6.0 I1 contract vectors (docs/specifications/0.6.0/i1-vectors/).

The vectors are authored by hand from the I1 support matrix. This module checks them with the
standard library only and deliberately imports nothing from `app/`: it is an independent reference
for the frozen contract, not a test of AIP's implementation (I1 §13, §14).
"""

import hashlib
import itertools
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specifications" / "0.6.0"
VECTORS = SPEC_DIR / "i1-vectors"

_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _serialize(value: datetime) -> str:
    utc_value = value.astimezone(UTC)
    return utc_value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{utc_value.microsecond:06d}Z"


def _parse_day(value: str) -> date | None:
    if not _DAY.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _window(first: str, last: str) -> tuple[datetime, datetime] | None:
    first_day, last_day = _parse_day(first), _parse_day(last)
    if first_day is None or last_day is None or first_day > last_day:
        return None
    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
    # Normalized end: (last_day + 1 day) at midnight UTC minus 1 µs. The offset is summed first so
    # 9999-12-31 (whose next midnight is not representable) does not overflow.
    last_midnight = datetime(last_day.year, last_day.month, last_day.day, tzinfo=UTC)
    end = last_midnight + (timedelta(days=1) - timedelta(microseconds=1))
    return start, end


def _parse_instant(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


DAY_WINDOW = _load("utc-day-window.json")
WINDOWS = {w["id"]: w for w in DAY_WINDOW["windows"]}


@pytest.mark.parametrize("vector", DAY_WINDOW["windows"], ids=lambda v: v["id"])
def test_day_window_normalization(vector: dict) -> None:
    bounds = _window(vector["first_day"], vector["last_day"])
    if not vector["valid"]:
        assert bounds is None
        return
    assert bounds is not None
    assert (_serialize(bounds[0]), _serialize(bounds[1])) == (vector["start"], vector["end"])


@pytest.mark.parametrize("vector", DAY_WINDOW["membership"], ids=lambda v: v["id"])
def test_day_window_membership_is_inclusive(vector: dict) -> None:
    window = WINDOWS[vector["window"]]
    bounds = _window(window["first_day"], window["last_day"])
    instant = _parse_instant(vector["instant"])
    assert bounds is not None and instant is not None
    assert (bounds[0] <= instant <= bounds[1]) is vector["included"]


@pytest.mark.parametrize("vector", DAY_WINDOW["utc_day_assignment"], ids=lambda v: v["id"])
def test_utc_day_assignment(vector: dict) -> None:
    instant = _parse_instant(vector["instant"])
    assert instant is not None
    assert instant.astimezone(UTC).date().isoformat() == vector["utc_day"]


@pytest.mark.parametrize("vector", DAY_WINDOW["capture_instant_parsing"], ids=lambda v: v["id"])
def test_capture_instant_requires_explicit_offset(vector: dict) -> None:
    assert (_parse_instant(vector["value"]) is not None) is vector["parsable"]


def _utc_day(value: str) -> str:
    instant = _parse_instant(value)
    assert instant is not None
    return instant.astimezone(UTC).date().isoformat()


@pytest.mark.parametrize("vector", DAY_WINDOW["timestamp_roles"], ids=lambda v: v["id"])
def test_timestamp_roles(vector: dict) -> None:
    client_day, fact_day = _utc_day(vector["client_timestamp"]), _utc_day(vector["fact_timestamp"])
    # v1 is always bucketed by the accepted fact timestamp; ingestion guard I-4 compares UTC days.
    assert fact_day == vector["v1_bucket_day"]
    assert (client_day == fact_day) is vector["i4_passes"]
    if not vector["i4_passes"]:
        assert vector["reason"] == "LOCALITY_CLIENT_FACT_DAY_MISMATCH"
        assert "v2_bucket_utc_day" not in vector
        return
    # v2 takes its day and first/last_seen from the accepted fact timestamp, never the CLIENT's.
    assert vector["v2_bucket_utc_day"] == fact_day
    fact = _parse_instant(vector["fact_timestamp"])
    assert fact is not None
    assert vector["v2_first_seen"] == vector["v2_last_seen"] == _serialize(fact)


def test_vector_ids_are_unique() -> None:
    ids = [
        v["id"]
        for group in ("windows", "membership", "utc_day_assignment")
        for v in DAY_WINDOW[group]
    ]
    ids += [v["id"] for v in DAY_WINDOW["capture_instant_parsing"]]
    ids += [v["id"] for v in DAY_WINDOW["timestamp_roles"]]
    assert len(ids) == len(set(ids))


def _spec_reason_codes() -> set[str]:
    spec = (SPEC_DIR / "i1-locality-and-evidence-applicability.md").read_text(encoding="utf-8")
    block = spec.split("Internal diagnostic codes", 1)[1].split("```", 2)[1]
    return set(re.findall(r"LOCALITY_[A-Z0-9_]+", block))


def test_support_matrix_uses_only_frozen_reason_codes() -> None:
    frozen = _spec_reason_codes()
    assert len(frozen) == 23
    matrix = (SPEC_DIR / "i1-locality-support-matrix.md").read_text(encoding="utf-8")
    used = set(re.findall(r"LOCALITY_[A-Z0-9_]+", matrix))
    assert used <= frozen, sorted(used - frozen)


# --- I1.3 scoped observed-evidence v2 (i1-scoped-evidence-v2-contract.md) ---

V2 = _load("v2-evidence-id.json")
KEY_VECTORS = {v["id"]: v for v in V2["key_vectors"]}
V2_PREFIX = "evidence:otel:calls-scoped:v2:"
V2_KEY_FIELDS = {
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
}
V2_ENTRY_FIELDS = V2_KEY_FIELDS | {
    "id",
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


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _v2_id(key: dict) -> str:
    return V2_PREFIX + hashlib.sha256(_canonical(key)).hexdigest()


@pytest.mark.parametrize("vector", V2["key_vectors"], ids=lambda v: v["id"])
def test_v2_key_vector(vector: dict) -> None:
    key = vector["input"]
    assert set(key) == V2_KEY_FIELDS
    assert isinstance(key["contract_version"], int) and key["contract_version"] == 2
    assert _canonical(key) == vector["canonical_bytes_utf8"].encode("utf-8")
    assert hashlib.sha256(_canonical(key)).hexdigest() == vector["sha256"]
    assert _v2_id(key) == vector["evidence_id"]


def test_v2_key_distinctions() -> None:
    ids = {name: v["evidence_id"] for name, v in KEY_VECTORS.items()}
    assert ids["V02-reordered-input"] == ids["V01-base"]  # L01
    assert list(KEY_VECTORS["V02-reordered-input"]["input"]) != list(
        KEY_VECTORS["V01-base"]["input"]
    )
    assert ids["V03-distinct-pod"] != ids["V01-base"]  # L02
    assert ids["V04-same-pod-uid-other-cluster"] != ids["V01-base"]  # L03
    distinct = {k: v for k, v in ids.items() if k != "V02-reordered-input"}
    assert len(set(distinct.values())) == len(distinct)


def test_v2_non_ascii_is_raw_utf8() -> None:
    vector = KEY_VECTORS["V05-non-ascii-environment"]
    assert "ü" in vector["canonical_bytes_utf8"] and "\\u" not in vector["canonical_bytes_utf8"]


@pytest.mark.parametrize("vector", V2["v1_unchanged"], ids=lambda v: v["id"])
def test_v1_id_has_no_pod_or_cluster_component(vector: dict) -> None:
    digest = hashlib.sha256(vector["seed_utf8"].encode("utf-8")).hexdigest()[:12]
    assert digest == vector["sha256_first12"]
    assert (
        vector["evidence_id"]
        == f"evidence:otel:{vector['environment']}:{vector['bucket_day']}:{digest}"
    )
    for name in vector["same_as_v2"]:
        key = KEY_VECTORS[name]["input"]
        seed = f"{key['subject_id']}|{key['relation_type']}|{key['object_id']}"
        assert (key["environment"], key["bucket_utc_day"], seed) == (
            vector["environment"],
            vector["bucket_day"],
            vector["seed_utf8"],
        )


def test_v2_snapshot_fragment() -> None:
    fragment = V2["snapshot_fragment"]
    entries = fragment["entries"]
    assert fragment["state_key"] == "scoped_observed_calls_v2"
    assert entries, "the conditional key is never present with an empty list"
    assert _canonical(entries) == fragment["canonical_bytes_utf8"].encode("utf-8")
    assert hashlib.sha256(_canonical(entries)).hexdigest() == fragment["sha256"]
    assert [e["id"] for e in entries] == sorted(e["id"] for e in entries)
    for entry in entries:
        assert set(entry) == V2_ENTRY_FIELDS
        assert entry["id"] == _v2_id({f: entry[f] for f in V2_KEY_FIELDS})
        assert entry["sample_trace_ids"] == sorted(set(entry["sample_trace_ids"]))[:5]
        conflicts = entry["conflicting_consistency_attributes"]
        assert conflicts == sorted(set(conflicts))
        assert all(entry[name] is None for name in conflicts)
        assert entry["first_seen"] <= entry["last_seen"]


def test_golden_path_demo_pin_is_the_re_derived_v0_6_1_pin() -> None:
    """The frozen v0.6.0 pin (`0bfcbded…`) is superseded, not edited. v0.6.1 moves it (canonicalization
    4 and the demo's Broker node), so the golden path and the runtime-demo manifest must pin the same
    re-derived snapshot, and it must differ from the v0.6.0 one."""
    pin = V2["no_v2_snapshot_pin"]
    expected = json.loads((ROOT / pin["source"]).read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "examples/runtime-demo/fixture-state.json").read_text("utf-8"))
    [fixture_state] = [
        c for c in expected["phases"]["demo"]["checks"] if c["id"] == "fixture-state"
    ]
    golden_pin = fixture_state["expect"]["actual_snapshot_id"]
    assert golden_pin == manifest["expected_snapshot_id"]
    assert golden_pin != pin["snapshot_id"], "the v0.6.0 pin must not survive a snapshot change"
    assert manifest["total_node_count"] == 49  # the v0.6.0 demo's 48 plus the one Broker node


_CONSISTENCY_FIELDS = (
    "k8s_namespace_name",
    "k8s_pod_name",
    "k8s_deployment_name",
    "k8s_statefulset_name",
    "k8s_daemonset_name",
)
_MODE_STRENGTH = {"CLIENT_ONLY": 2, "CLIENT_SERVER": 3}


def _seed_record(seed: dict) -> dict:
    return {
        "first_seen": seed["fact_timestamp"],
        "last_seen": seed["fact_timestamp"],
        "observation_count": 1,
        "correlation_mode": seed["correlation_mode"],
        "sample_trace_ids": [seed["trace_id"]],
        **{f: seed[f] for f in _CONSISTENCY_FIELDS},
        "conflicting_consistency_attributes": [],
    }


def _merge(existing: dict, seed: dict, *, absorbing: bool) -> dict:
    new = _seed_record(seed)
    conflicts = set(existing["conflicting_consistency_attributes"])
    merged = {
        "first_seen": min(existing["first_seen"], new["first_seen"]),
        "last_seen": max(existing["last_seen"], new["last_seen"]),
        "observation_count": existing["observation_count"] + 1,
        "correlation_mode": max(
            existing["correlation_mode"], new["correlation_mode"], key=_MODE_STRENGTH.__getitem__
        ),
        "sample_trace_ids": sorted(
            set(existing["sample_trace_ids"]) | set(new["sample_trace_ids"])
        )[:5],
    }
    for field in _CONSISTENCY_FIELDS:
        old, value = existing[field], new[field]
        if absorbing and field in conflicts:
            merged[field] = None
        elif old is not None and value is not None and old != value:
            conflicts.add(field)
            merged[field] = None
        else:
            # The v0.5 fallback: a flagged field's null is refilled from the other side.
            merged[field] = old if old is not None else value
    merged["conflicting_consistency_attributes"] = sorted(conflicts)
    return merged


def _fold(seeds: tuple[dict, ...], *, absorbing: bool) -> dict:
    record = _seed_record(seeds[0])
    for seed in seeds[1:]:
        record = _merge(record, seed, absorbing=absorbing)
    return record


@pytest.mark.parametrize("vector", V2["merge_permutation_vectors"], ids=lambda v: v["id"])
def test_v2_merge_is_permutation_invariant(vector: dict) -> None:
    for order in itertools.permutations(vector["seeds"]):
        assert _fold(order, absorbing=True) == vector["expected"]


def test_v05_style_merge_would_be_order_dependent() -> None:
    """Why v2 freezes the absorbing rule: v0.5's refill-after-conflict merge differs by order."""
    seeds = {
        s["trace_id"][0] + s["fact_timestamp"][11:13]: s
        for s in V2["merge_permutation_vectors"][0]["seeds"]
    }
    a1, b, a2 = seeds["a10"], seeds["b12"], seeds["a11"]
    assert _fold((a1, b, a2), absorbing=False)["k8s_pod_name"] == "orders-a"
    assert _fold((a1, a2, b), absorbing=False)["k8s_pod_name"] is None


# --- I1.5 conformance dossier (i1-conformance-dossier.md) ---

CONFORMANCE = _load("conformance-expected.json")
DISPOSITIONS = {
    "APPLICABLE",
    "INAPPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "UNRESOLVED",
    "AMBIGUOUS",
    "CONFLICT",
    "UNSUPPORTED",
}
# Within-phase precedence (I1 §10.1); UNSUPPORTED is terminal in phases 1-2 and never ranked.
_PRECEDENCE = ["CONFLICT", "AMBIGUOUS", "INAPPLICABLE", "UNRESOLVED", "INSUFFICIENT_EVIDENCE"]
# Each code's disposition (support matrix §15). Codes that only ingestion can establish (§15.1).
_REASON_DISPOSITION = {
    "LOCALITY_CLIENT_IDENTITY_MISSING": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_SERVER_ONLY_NO_CLIENT": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_CLIENT_INTERNAL_CONFLICT": "CONFLICT",
    "LOCALITY_CLIENT_FACT_ENVIRONMENT_MISMATCH": "INAPPLICABLE",
    "LOCALITY_CLIENT_FACT_DAY_MISMATCH": "INAPPLICABLE",
    "LOCALITY_CLUSTER_UID_MISSING": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_CLUSTER_UID_CONFLICT": "CONFLICT",
    "LOCALITY_POD_UID_MISSING": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_CAPTURE_MISSING_POD": "UNRESOLVED",
    "LOCALITY_CAPTURE_MODE_UNSUPPORTED": "UNSUPPORTED",
    "LOCALITY_CAPTURE_TEMPORAL_MISMATCH": "INAPPLICABLE",
    "LOCALITY_CAPTURE_TIMESTAMP_MISSING": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_OBSERVATION_TEMPORAL_MISMATCH": "INAPPLICABLE",
    "LOCALITY_POD_OWNER_UNRESOLVED": "UNRESOLVED",
    "LOCALITY_POD_OWNER_AMBIGUOUS": "AMBIGUOUS",
    "LOCALITY_POD_OWNER_CONFLICT": "CONFLICT",
    "LOCALITY_NAMESPACE_CONFLICT": "CONFLICT",
    "LOCALITY_LEGACY_V1_UNSCOPED": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_UNSUPPORTED_DIMENSION": "UNSUPPORTED",
    "LOCALITY_UNSUPPORTED_RELATION": "UNSUPPORTED",
    "LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION": "UNSUPPORTED",
    "LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION": "INSUFFICIENT_EVIDENCE",
    "LOCALITY_LOCAL_COVERAGE_UNAVAILABLE": "INSUFFICIENT_EVIDENCE",
}
_INGESTION_ONLY = {
    "LOCALITY_CLIENT_IDENTITY_MISSING",
    "LOCALITY_SERVER_ONLY_NO_CLIENT",
    "LOCALITY_CLIENT_INTERNAL_CONFLICT",
    "LOCALITY_CLIENT_FACT_ENVIRONMENT_MISMATCH",
    "LOCALITY_CLIENT_FACT_DAY_MISMATCH",
    "LOCALITY_CLUSTER_UID_MISSING",
    "LOCALITY_POD_UID_MISSING",
}


def _results(expected: dict) -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = []
    if "ingestion" in expected:
        found.append(("ingestion", expected["ingestion"]))
    if "request" in expected:
        found.append(("request", expected["request"]))
    if "answer" in expected:
        found.append(("answer", expected["answer"]))
    found.extend(("query", r) for r in expected.get("query", []))
    return found


def _variants() -> list[tuple[str, dict]]:
    return [(f"{c['id']}{v['id']}", v) for c in CONFORMANCE["cases"] for v in c["variants"]]


def test_conformance_covers_exactly_l01_to_l37() -> None:
    ids = [case["id"] for case in CONFORMANCE["cases"]]
    assert ids == [f"L{n:02d}" for n in range(1, 38)]
    for case in CONFORMANCE["cases"]:
        assert case["variants"] and case["prohibited"], case["id"]
        variant_ids = [v["id"] for v in case["variants"]]
        assert len(variant_ids) == len(set(variant_ids)), case["id"]


def test_reason_disposition_table_matches_frozen_codes() -> None:
    assert set(_REASON_DISPOSITION) == _spec_reason_codes()


@pytest.mark.parametrize(("name", "variant"), _variants(), ids=[n for n, _ in _variants()])
def test_conformance_result_is_consistent(name: str, variant: dict) -> None:
    for kind, result in _results(variant["expected"]):
        disposition, reasons = result["disposition"], result["reasons"]
        assert disposition in DISPOSITIONS, name
        assert reasons == sorted(set(reasons)), name
        assert set(reasons) <= set(_REASON_DISPOSITION), name
        if kind != "ingestion":
            # §10.2: an ingestion-specific cause is never visible in a query answer.
            assert not set(reasons) & _INGESTION_ONLY, name
        if kind == "query":
            assert result["phase"] in (2, 3, 4), name
        if kind == "request":
            assert result["phase"] == 1 and disposition == "UNSUPPORTED", name
        if disposition == "UNSUPPORTED":
            assert kind == "request" or result.get("phase") == 2, name
        if not reasons:
            assert disposition == "APPLICABLE" or "limitation_without_code" in result, name
            continue
        implied = {_REASON_DISPOSITION[r] for r in reasons}
        if "UNSUPPORTED" in implied:
            assert implied == {"UNSUPPORTED"} and disposition == "UNSUPPORTED", name
        else:
            assert disposition == min(implied, key=_PRECEDENCE.index), name


def test_conformance_v2_references_exist() -> None:
    known = set(KEY_VECTORS) | {v["id"] for v in V2["v1_unchanged"]}
    text = json.dumps(CONFORMANCE["cases"])
    for ref in re.findall(r'"((?:V|U)\d{2}-[a-z0-9-]+)"', text):
        assert ref in known, ref
    for case in CONFORMANCE["cases"]:
        for variant in case["variants"]:
            for result in variant["expected"].get("query", []):
                assert result["candidate"] in KEY_VECTORS
                assert result["selected_capture"] in CONFORMANCE["fixtures"]["captures"]


def test_no_local_not_observed_in_window_is_ever_expected() -> None:
    for case in CONFORMANCE["cases"]:
        for variant in case["variants"]:
            assert variant["expected"].get("qualification") != "NOT_OBSERVED_IN_WINDOW", case["id"]


def test_dossier_headings_match_machine_readable_cases() -> None:
    dossier = (SPEC_DIR / "i1-conformance-dossier.md").read_text(encoding="utf-8")
    headings = re.findall(r"^### (L\d{2}) — (.+)$", dossier, flags=re.MULTILINE)
    assert headings == [(case["id"], case["title"]) for case in CONFORMANCE["cases"]]
    for name, _ in _variants():
        assert f"| {name} |" in dossier, name


def test_rejected_envelopes_are_never_selected_captures() -> None:
    """A capture the v0.5 envelope validation rejects cannot be a query's selected capture."""
    non_selectable = set(CONFORMANCE["fixtures"]["non_selectable_captures"])
    assert non_selectable <= set(CONFORMANCE["fixtures"]["captures"])
    for case in CONFORMANCE["cases"]:
        for variant in case["variants"]:
            expected = variant["expected"]
            for result in expected.get("query", []):
                assert result["selected_capture"] not in non_selectable, case["id"]
            if "import" in expected:
                assert expected["import"]["result"].startswith("REJECTED_")
                assert expected["import"]["selectable"] is False
                assert "query" not in expected, case["id"]
