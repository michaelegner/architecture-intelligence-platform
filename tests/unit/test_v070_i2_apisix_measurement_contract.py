"""v0.7.0 I2.2a: the production measurement contract module against the independent I2.1 vectors
(docs/specifications/0.7.0/i2-vectors/): manifest/extract/mapping rejections, window validity, series
deltas and ids all go through `app.sources.apisix_measurement_contract`, not a re-implementation."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.sources.apisix_measurement_contract import (
    MeasurementRejection,
    Series,
    first_in_window_allowed,
    measurement_evidence_id,
    measurement_window_id,
    parse_extract,
    parse_manifest,
    parse_mapping,
    series_deltas,
    series_status,
    validate_fixture,
    window_reasons,
)

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"


def _load(name: str) -> dict[str, Any]:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def _bytes(lines: list[str], ending: str = "LF") -> bytes:
    eol = "\r\n" if ending == "CRLF" else "\n"
    return "".join(line + eol for line in lines).encode("utf-8")


def _manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest).encode("utf-8")


def test_ids_match_the_frozen_vectors() -> None:
    doc = {v["id"]: v for v in _load("ids.json")["vectors"]}
    inputs = doc["M04"]["inputs"]
    manifest = parse_manifest(
        {
            **_load("manifest-rejections.json")["base_manifest"],
            "gateway_instance_id": inputs["gateway_instance_id"],
            "environment": inputs["environment"],
            "window_start": inputs["window_start"],
            "window_end": inputs["window_end"],
            "start_sha256": inputs["start_sha256"],
            "end_sha256": inputs["end_sha256"],
        }
    )
    assert measurement_window_id(manifest) == doc["M04"]["expected"]
    assert measurement_evidence_id(manifest) == doc["M05"]["expected"]
    lines = doc["M03"]["inputs"]["extract_lines"]
    assert hashlib.sha256(_bytes(lines)).hexdigest() == doc["M03"]["expected"]


def test_manifest_and_extract_rejections_through_the_production_validator() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    for case in doc["cases"]:
        if "registrations" in case:
            continue  # duplicate-source conflicts are a discoverer/import concern (I2.2b)
        manifest = json.loads(json.dumps(doc["base_manifest"]))
        start = list(case.get("start_lines_replace", doc["base_start_lines"]))
        end = list(doc["base_end_lines"]) + case.get("end_lines_patch", {}).get("append", [])
        ending = case.get("line_ending", "LF")
        start_b, end_b = _bytes(start, ending), _bytes(end, ending)
        if case.get("hash_policy") != "keep":
            manifest["start_sha256"] = hashlib.sha256(start_b).hexdigest()
            manifest["end_sha256"] = hashlib.sha256(end_b).hexdigest()
        manifest.update(case.get("manifest_patch", {}))
        for name in case.get("manifest_remove", []):
            manifest.pop(name)
        with pytest.raises(MeasurementRejection) as raised:
            validate_fixture(
                _manifest_bytes(manifest),
                start_b,
                end_b,
                gateway_instance_id=registration["gateway_instance_id"],
                environment=registration["environment"],
            )
        expected = case["expected"]
        assert (raised.value.result, raised.value.code) == (
            expected["result"],
            expected["code"],
        ), case["id"]


def test_the_unpatched_base_fixture_is_accepted() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    validated = validate_fixture(
        _manifest_bytes(doc["base_manifest"]),
        _bytes(doc["base_start_lines"]),
        _bytes(doc["base_end_lines"]),
        gateway_instance_id=registration["gateway_instance_id"],
        environment=registration["environment"],
    )
    assert validated.window_reasons == []
    [upstream, rejected] = validated.series_deltas()
    assert (upstream.status, upstream.delta, upstream.series.labels["code"]) == ("DELTA", 3, "200")
    assert (rejected.status, rejected.delta, rejected.series.labels["code"]) == ("DELTA", 1, "403")


def test_validation_order_is_schema_fields_registration_binding_extract() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    base = doc["base_manifest"]
    start, end = _bytes(doc["base_start_lines"]), _bytes(doc["base_end_lines"])
    bad_extract = b"not a sample\n"

    def code(manifest: dict[str, Any], start_b: bytes = start) -> str:
        with pytest.raises(MeasurementRejection) as raised:
            validate_fixture(
                _manifest_bytes(manifest),
                start_b,
                end,
                gateway_instance_id=registration["gateway_instance_id"],
                environment=registration["environment"],
            )
        return raised.value.code

    # a wrong schema outranks a missing field; a field defect outranks a registration mismatch;
    # a registration mismatch outranks a bad hash; a bad hash outranks a bad extract
    assert code({**base, "schema": "x/9", "no_restart": "?"}) == "GWM_SCHEMA_UNSUPPORTED"
    assert code({**base, "no_restart": "?", "environment": "staging"}) == "GWM_MANIFEST_INVALID"
    assert code({**base, "environment": "staging", "start_sha256": "0" * 64}) == (
        "GWM_INSTANCE_MISMATCH"
    )
    assert code({**base}, start_b=bad_extract) == "GWM_BINDING_MISMATCH"
    good_hash = {**base, "start_sha256": hashlib.sha256(bad_extract).hexdigest()}
    assert code(good_hash, start_b=bad_extract) == "GWM_EXTRACT_INVALID"


def test_non_object_duplicate_key_and_oversized_manifests_are_rejected() -> None:
    registration = _load("manifest-rejections.json")["registration"]
    kwargs = {
        "gateway_instance_id": registration["gateway_instance_id"],
        "environment": registration["environment"],
    }
    for raw, code in (
        (b"[]", "GWM_MANIFEST_INVALID"),
        (b"not json", "GWM_MANIFEST_INVALID"),
        (b'{"schema": "a", "schema": "b"}', "GWM_MANIFEST_INVALID"),
        (b" " * (1024 * 1024 + 1), "GWM_LIMIT_EXCEEDED"),
    ):
        with pytest.raises(MeasurementRejection) as raised:
            validate_fixture(raw, b"", b"", **kwargs)
        assert raised.value.code == code
    with pytest.raises(MeasurementRejection) as raised:
        validate_fixture(b"{}", b"x" * (8 * 1024 * 1024 + 1), b"", **kwargs)
    assert raised.value.code == "GWM_LIMIT_EXCEEDED"


def test_the_rejection_message_never_carries_a_source_value() -> None:
    canary = "CANARY-SECRET-VALUE"
    with pytest.raises(MeasurementRejection) as raised:
        parse_extract(f'apisix_http_status{{consumer="{canary}"}} 1\n'.encode())
    assert canary not in str(raised.value) and canary not in repr(raised.value)


def test_window_validity_vectors() -> None:
    doc = _load("series-deltas.json")
    base = _load("manifest-rejections.json")["base_manifest"]
    for case in doc["window_validity"]:
        manifest = parse_manifest({**base, **case["manifest_patch"]})
        assert window_reasons(manifest) == case["expected_reasons"], case["id"]


def test_series_delta_vectors() -> None:
    doc = _load("series-deltas.json")
    base = parse_manifest(_load("manifest-rejections.json")["base_manifest"])
    start = parse_extract(_bytes(doc["start_lines"]))
    end = parse_extract(_bytes(doc["end_lines"]))
    got = [
        {
            "route": d.series.labels["route"],
            "consumer": d.series.labels["consumer"],
            "code": d.series.labels["code"],
            "response_source": d.series.labels["response_source"],
            "matched_uri": d.series.labels["matched_uri"],
            "status": d.status,
            "delta": d.delta,
        }
        for d in series_deltas(start, end, base)
    ]
    key = lambda r: (r["route"], r["consumer"], r["code"], r["matched_uri"])
    assert sorted(got, key=key) == sorted(doc["expected_series"], key=key)


def test_first_in_window_vectors() -> None:
    doc = _load("series-deltas.json")
    base = _load("manifest-rejections.json")["base_manifest"]
    for case in doc["first_in_window"]:
        manifest = parse_manifest({**base, **case["manifest_patch"]})
        status, delta = series_status(
            case["start"],
            case["end"],
            first_in_window=first_in_window_allowed(manifest, case["route"]),
        )
        assert (status, delta) == (case["expected_status"], case["expected_delta"]), case["id"]


def test_a_series_that_exists_nowhere_is_an_error_not_a_zero() -> None:
    with pytest.raises(ValueError):
        series_status(None, None)


def test_series_identity_is_the_full_label_string() -> None:
    doc = _load("series-deltas.json")
    start = parse_extract(_bytes(doc["start_lines"]))
    keys = [s.key for s in start.values() if s.labels["consumer"] == "spike-alpha"]
    assert (
        len(set(keys)) == len(keys) == 4
    )  # two matched_uri variants, the 403 series and the billing route
    assert all(isinstance(s, Series) for s in start.values())


def test_mapping_artifact_vectors() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    for case in doc["mapping_cases"]:
        mapping = {**doc["mapping_base"], **case["patch"]}
        raw = json.dumps(mapping).encode()
        expected = case["expected"]
        if expected["result"] == "ACCEPTED":
            artifact = parse_mapping(raw, gateway_instance_id=registration["gateway_instance_id"])
            assert artifact.route_operation[0].route_id == "orders-route"
            assert {m.kind for m in artifact.target_service} == {"route", "service"}
            continue
        with pytest.raises(MeasurementRejection) as raised:
            parse_mapping(raw, gateway_instance_id=registration["gateway_instance_id"])
        assert (raised.value.result, raised.value.code) == (
            expected["result"],
            expected["code"],
        ), case["id"]


def test_mapping_duplicates_and_disagreements_are_inputs_not_rejections() -> None:
    raw = json.dumps(
        {
            "schema": "aip-apisix-mapping/1",
            "gateway_instance_id": "gw-prod-1",
            "route_operation": [
                {"route_id": "r1", "operation_id": "op:a"},
                {"route_id": "r1", "operation_id": "op:b"},
            ],
        }
    ).encode()
    artifact = parse_mapping(raw, gateway_instance_id="gw-prod-1")
    assert [m.operation_id for m in artifact.route_operation] == ["op:a", "op:b"]
    assert artifact.target_service == ()
