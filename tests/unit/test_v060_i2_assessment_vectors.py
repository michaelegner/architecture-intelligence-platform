"""Recomputes the frozen v0.6.0 I2.4a local-assessment identity vectors
(`docs/specifications/0.6.0/i2-vectors/local-assessment-id.json`, decision record D9 and D14).

The canonical bytes were written by hand and hashed with `sha256sum` before any implementation.
This module checks them with the standard library only and deliberately imports nothing from
`app/`: it is an independent reference for the frozen identity contract, not a test of AIP.
I2.4b's own tests then require the implementation to reproduce these exact ids.
"""

import hashlib
import itertools
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VECTORS = json.loads(
    (ROOT / "docs/specifications/0.6.0/i2-vectors/local-assessment-id.json").read_text(
        encoding="utf-8"
    )
)
ASSERTIONS = VECTORS["assertion_vectors"]
ASSESSMENTS = VECTORS["assessment_vectors"]
ALL = ASSERTIONS + ASSESSMENTS

ASSERTION_FIELDS = {
    "version",
    "subject_service_id",
    "relation_type",
    "object_operation_id",
    "environment",
    "first_utc_day",
    "last_utc_day",
    "workload",
}
WORKLOAD_FIELDS = {"cluster_uid", "namespace", "kind", "uid"}
ASSESSMENT_FIELDS = {"version", "assertion_id", "snapshot_id", "capture_revisions", "rules"}
RULES = {
    ("declared-observed-qualification", 1),
    ("otel-calls-scoped-evidence-v2-key", 1),
    ("otel-client-caller-attribution", 1),
    ("scoped-caller-locality-applicability", 1),
}


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _normalized_assessment(fields: dict) -> dict:
    """D14.2: both lists are sorted before encoding."""
    return {
        **fields,
        "capture_revisions": sorted(
            fields["capture_revisions"], key=lambda c: (c["source_instance_id"], c["revision"])
        ),
        "rules": sorted(fields["rules"], key=lambda r: (r["id"], r["version"])),
    }


def _by_id(vector_id: str) -> dict:
    [vector] = [v for v in ALL if v["id"] == vector_id]
    return vector


@pytest.mark.parametrize("vector", ALL, ids=lambda v: v["id"])
def test_every_recorded_hash_and_id_matches_its_bytes(vector):
    digest = hashlib.sha256(vector["canonical_bytes_utf8"].encode("utf-8")).hexdigest()
    assert digest == vector["sha256"]
    prefix = (
        VECTORS["encoding"]["assertion_prefix"]
        if vector in ASSERTIONS
        else VECTORS["encoding"]["assessment_prefix"]
    )
    assert vector["expected_id"] == prefix + digest


@pytest.mark.parametrize("vector", ASSERTIONS, ids=lambda v: v["id"])
def test_assertion_bytes_are_the_canonical_form_of_exactly_the_d9_fields(vector):
    fields = vector["fields"]
    assert set(fields) == ASSERTION_FIELDS
    assert set(fields["workload"]) == WORKLOAD_FIELDS
    assert fields["version"] == 1 and fields["relation_type"] == "CALLS"
    assert fields["workload"]["kind"] in {"Deployment", "StatefulSet", "DaemonSet"}  # D14.1
    assert _canonical(fields) == vector["canonical_bytes_utf8"]


@pytest.mark.parametrize("vector", ASSESSMENTS, ids=lambda v: v["id"])
def test_assessment_bytes_are_the_canonical_form_of_exactly_the_d9_fields(vector):
    fields = vector["fields"]
    assert set(fields) == ASSESSMENT_FIELDS
    assert {(r["id"], r["version"]) for r in fields["rules"]} == RULES  # D14.2
    assert all(set(c) == {"source_instance_id", "revision"} for c in fields["capture_revisions"])
    assert _canonical(_normalized_assessment(fields)) == vector["canonical_bytes_utf8"]


@pytest.mark.parametrize("vector", ALL, ids=lambda v: v["id"])
def test_field_order_never_changes_the_bytes(vector):
    fields = vector["fields"]
    normalize = _normalized_assessment if vector in ASSESSMENTS else (lambda f: f)
    for order in itertools.permutations(fields):
        reordered = {key: fields[key] for key in order}
        assert _canonical(normalize(reordered)) == vector["canonical_bytes_utf8"]


def test_every_assessment_names_the_a01_assertion():
    a01 = _by_id("A01-v01-w1-o1-day-d")["expected_id"]
    assert {v["fields"]["assertion_id"] for v in ASSESSMENTS} == {a01}


def test_declared_equalities_hold_and_every_other_id_is_distinct():
    for vector in ALL:
        if "same_id_as" in vector:
            assert vector["expected_id"] == _by_id(vector["same_id_as"])["expected_id"]
    distinct = [v["expected_id"] for v in ALL if "same_id_as" not in v]
    assert len(distinct) == len(set(distinct))


def test_the_pod_is_lineage_not_identity():
    a01, a02 = _by_id("A01-v01-w1-o1-day-d"), _by_id("A02-other-pod-same-workload")
    assert a01["lineage"]["caller_pod_uid"] != a02["lineage"]["caller_pod_uid"]
    assert a01["fields"] == a02["fields"]
