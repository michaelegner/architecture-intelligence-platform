"""v0.7.0 I2.1: the hand-authored vectors in docs/specifications/0.7.0/i2-vectors/ are internally
consistent with the frozen contract (docs/specifications/0.7.0/i2-measurement-contract.md).

Deliberately imports nothing from `app`: the id formulas, the manifest/extract validation, the delta
and coverage rules, the reconciliation rules and the qualification truth table are re-implemented
here from the contract text, so a later production implementation is checked against vectors that
did not come from it (I2 spec §13: "independently authored expected results").
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i2-vectors"

MANIFEST_SCHEMA = "aip-apisix-measurement/1"
MAPPING_SCHEMA = "aip-apisix-mapping/1"
UPSTREAM, APISIX = "upstream", "apisix"
REQUIRED_LABELS = {"code", "consumer", "response_source", "route"}
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SUPPORTED_VERSION = "3.19.0"
SERIES = re.compile(r"^apisix_http_status\{(.*)\} (\d+)$")
LABEL = re.compile(r'([a-z_]+)="((?:[^"\\]|\\.)*)"')
MIN_START_STABLE_SECONDS = 20
SUFFICIENT, UNKNOWN = "SUFFICIENT_FOR_ZERO", "UNKNOWN_COVERAGE"
CONFIGURED, NO_FACT = "CONFIGURED_ACCESS_ESTABLISHED", "NO_MATCHING_CONFIGURED_ACCESS_FACT"
OBSERVED, ZERO, UNESTABLISHED = "OBSERVED_USAGE", "MEASURED_ZERO", "USAGE_UNESTABLISHED"


def _ld(*parts: str) -> bytes:
    out = b""
    for part in parts:
        raw = part.encode("utf-8")
        out += len(raw).to_bytes(8, "big") + raw
    return out


def _h(*parts: str) -> str:
    return hashlib.sha256(_ld(*parts)).hexdigest()


def _load(name: str) -> dict[str, Any]:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


class Reject(Exception):
    def __init__(self, result: str, code: str) -> None:
        super().__init__(code)
        self.result, self.code = result, code


# ---- contract §2: manifest, extract, binding -------------------------------------------------


def _check_manifest(manifest: dict[str, Any], registration: dict[str, Any]) -> None:
    schema = manifest.get("schema")
    if not isinstance(schema, str):
        raise Reject("REJECTED_INVALID", "GWM_MANIFEST_INVALID")
    if schema != MANIFEST_SCHEMA:
        raise Reject("REJECTED_UNSUPPORTED", "GWM_SCHEMA_UNSUPPORTED")
    invalid = Reject("REJECTED_INVALID", "GWM_MANIFEST_INVALID")
    for name in ("gateway_instance_id", "environment", "apisix_version"):
        if not isinstance(manifest.get(name), str) or not manifest[name]:
            raise invalid
    for name in ("window_start", "window_end"):
        value = manifest.get(name)
        if not isinstance(value, str) or not TIMESTAMP.match(value):
            raise invalid
        try:
            datetime.fromisoformat(value)
        except ValueError:
            raise invalid from None
    for name in ("start_settled", "end_settled", "no_restart"):
        if not isinstance(manifest.get(name), bool):
            raise invalid
    for name in ("start_stable_seconds", "end_stable_seconds"):
        seconds = manifest.get(name)
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds < 0:
            raise invalid
    for boundary in ("start", "end"):
        count = manifest.get(f"{boundary}_scrape_count")
        if not isinstance(count, int) or isinstance(count, bool):
            raise invalid
        if count < (2 if manifest[f"{boundary}_settled"] else 1):
            raise invalid
    labels = manifest.get("disabled_labels")
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        raise invalid
    if labels != sorted(set(labels)):
        raise invalid
    coverage = manifest.get("route_coverage")
    if not isinstance(coverage, dict) or not all(
        isinstance(k, str) and isinstance(v, bool) for k, v in coverage.items()
    ):
        raise invalid
    for name in ("start_sha256", "end_sha256"):
        value = manifest.get(name)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise invalid
    if (
        manifest["gateway_instance_id"] != registration["gateway_instance_id"]
        or manifest["environment"] != registration["environment"]
    ):
        raise Reject("REJECTED_INVALID", "GWM_INSTANCE_MISMATCH")


def _parse_extract(raw: bytes) -> dict[str, tuple[dict[str, str], int]]:
    invalid = Reject("REJECTED_INVALID", "GWM_EXTRACT_INVALID")
    if not raw:
        return {}
    if b"\r" in raw or not raw.endswith(b"\n"):
        raise invalid
    try:
        lines = raw.decode("utf-8")[:-1].split("\n")
    except UnicodeDecodeError:
        raise invalid from None
    if lines != sorted(set(lines)):
        raise invalid
    series: dict[str, tuple[dict[str, str], int]] = {}
    for line in lines:
        match = SERIES.match(line)
        if not match:
            raise invalid
        pairs = LABEL.findall(match.group(1))
        names = [name for name, _ in pairs]
        rebuilt = ",".join(f'{n}="{v}"' for n, v in pairs)
        if rebuilt != match.group(1) or names != sorted(set(names)) or "node" in names:
            raise invalid
        labels = dict(pairs)
        if not REQUIRED_LABELS <= labels.keys() or labels["response_source"] not in {
            UPSTREAM,
            APISIX,
        }:
            raise invalid
        series[match.group(1)] = (labels, int(match.group(2)))
    return series


def _validate_import(
    registration: dict[str, Any], manifest: dict[str, Any], start: bytes, end: bytes
) -> None:
    _check_manifest(manifest, registration)  # schema, fields, then registration binding
    if (
        hashlib.sha256(start).hexdigest() != manifest["start_sha256"]
        or hashlib.sha256(end).hexdigest() != manifest["end_sha256"]
    ):
        raise Reject("REJECTED_INVALID", "GWM_BINDING_MISMATCH")
    _parse_extract(start)
    _parse_extract(end)


def _check_mapping(doc: dict[str, Any], registration: dict[str, Any]) -> None:
    schema = doc.get("schema")
    if schema != MAPPING_SCHEMA:
        raise Reject("REJECTED_UNSUPPORTED", "GWM_SCHEMA_UNSUPPORTED")
    if doc.get("gateway_instance_id") != registration["gateway_instance_id"]:
        raise Reject("REJECTED_INVALID", "GWM_INSTANCE_MISMATCH")
    invalid = Reject("REJECTED_INVALID", "GWM_MAPPING_INVALID")

    def entries(key: str, fields: set[str]) -> None:
        rows = doc.get(key, [])
        if not isinstance(rows, list):
            raise invalid
        for row in rows:
            if not isinstance(row, dict) or set(row) != fields:
                raise invalid
            if not all(isinstance(v, str) and v for v in row.values()):
                raise invalid
            if row.get("kind", "route") not in {"route", "service"}:
                raise invalid

    entries("route_operation", {"route_id", "operation_id"})
    entries("target_service", {"kind", "id", "service_id"})


def _lines_to_bytes(lines: list[str], ending: str = "LF") -> bytes:
    if not lines:
        return b""
    eol = "\r\n" if ending == "CRLF" else "\n"
    return "".join(line + eol for line in lines).encode("utf-8")


# ---- contract §3: window validity and series deltas -----------------------------------------


def _window_reasons(manifest: dict[str, Any]) -> list[str]:
    reasons: set[str] = set()
    if not (manifest["start_settled"] and manifest["end_settled"]):
        reasons.add("GWM_WINDOW_NOT_SETTLED")
    if not manifest["no_restart"]:
        reasons.add("GWM_WINDOW_RESTART")
    if manifest["window_start"] >= manifest["window_end"]:  # fixed-width UTC strings order
        reasons.add("GWM_WINDOW_ORDER_INVALID")
    if manifest["apisix_version"] != SUPPORTED_VERSION:
        reasons.add("GWM_VERSION_INCOMPATIBLE")
    return sorted(reasons)


def _first_in_window_ok(manifest: dict[str, Any], route: str) -> bool:
    """Contract §3 (amended in I2.2a): the preconditions for reading an absent start sample as 0."""
    return (
        not _window_reasons(manifest)
        and manifest["start_stable_seconds"] >= MIN_START_STABLE_SECONDS
        and manifest["route_coverage"].get(route) is True
        and "consumer" not in manifest["disabled_labels"]
    )


def _series_status(
    start: int | None, end: int | None, *, first_in_window: bool = False
) -> tuple[str, int | None]:
    if start is None and end is None:
        raise AssertionError("a series exists at at least one boundary")
    if start is None:
        if first_in_window:
            return "DELTA_FIRST_IN_WINDOW", end
        return "ONE_BOUNDARY_END", None
    if end is None:
        return "ONE_BOUNDARY_START", None
    if end < start:
        return "DECREASED", None
    return "DELTA", end - start


# ---- contract §7: coverage and qualification -------------------------------------------------


def _qualify(
    manifest: dict[str, Any],
    inventory: dict[str, Any],
    configured: set[tuple[str, str]],
    series: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    consumers, routes = set(inventory["consumers"]), set(inventory["routes"])
    reasons = _window_reasons(manifest)
    valid = not reasons
    broken: dict[str, set[str]] = {}  # Route -> route-wide series limitation codes
    totals: dict[tuple[str, str], dict[str, int]] = {}
    pairs = set(configured)
    for s in series:
        route, consumer, source = s["route"], s["consumer"], s["response_source"]
        status, delta = _series_status(
            s["start"], s["end"], first_in_window=_first_in_window_ok(manifest, route)
        )
        if route not in routes:
            continue
        attributed = consumer in consumers
        if attributed:
            pairs.add((consumer, route))
            bucket = totals.setdefault((consumer, route), {UPSTREAM: 0, APISIX: 0})
            if valid and delta is not None:
                bucket[source] += delta
        if source != UPSTREAM:
            continue  # rejected attempts never affect coverage or usage state
        if not attributed:
            broken.setdefault(route, set()).add("GWM_UNATTRIBUTED_UPSTREAM")
        if status == "DECREASED":
            broken.setdefault(route, set()).add("GWM_COUNTER_DECREASED")
        elif status.startswith("ONE_BOUNDARY"):
            broken.setdefault(route, set()).add("GWM_SERIES_ONE_BOUNDARY")
    rows = []
    for consumer, route in sorted(pairs):
        limits: set[str] = set()
        sufficient = valid
        if not valid:
            limits.update(reasons)
        else:
            if "consumer" in manifest["disabled_labels"]:
                limits.add("GWM_CONSUMER_LABEL_DISABLED")
            if route not in manifest["route_coverage"]:
                limits.add("GWM_ROUTE_COVERAGE_ABSENT")
            elif not manifest["route_coverage"][route]:
                limits.add("GWM_ROUTE_PROMETHEUS_DISABLED")
            limits.update(broken.get(route, set()))
            sufficient = not limits
        bucket = totals.get((consumer, route), {UPSTREAM: 0, APISIX: 0})
        is_configured = (consumer, route) in configured
        if valid and bucket[UPSTREAM] > 0:
            usage = OBSERVED
        elif valid and sufficient and is_configured:
            usage = ZERO
        else:
            usage = UNESTABLISHED
        rows.append(
            {
                "consumer": consumer,
                "route": route,
                "configured_status": CONFIGURED if is_configured else NO_FACT,
                "usage_status": usage,
                "coverage": SUFFICIENT if sufficient else UNKNOWN,
                "upstream_request_count": bucket[UPSTREAM] if valid else None,
                "rejected_attempt_count": bucket[APISIX] if valid else None,
                "limitations": sorted(limits),
            }
        )
    return rows


# ---- contract §6: reconciliation -------------------------------------------------------------


def _runtime_join(case: dict[str, Any]) -> dict[str, str]:
    inv, meas = case["inventory"], case["measurement"]
    same = (
        inv["gateway_instance_id"] == meas["gateway_instance_id"]
        and inv["environment"] == meas["environment"]
    )
    return {
        "consumer": "RESOLVED" if same and case["consumer"] in inv["consumers"] else "UNRESOLVED",
        "route": "RESOLVED" if same and case["route"] in inv["routes"] else "UNRESOLVED",
    }


def _route_operation(case: dict[str, Any]) -> dict[str, Any]:
    route, operations = case["route"], case["operations"]
    ids = {op["id"] for op in operations}
    stated = sorted(
        {
            m["operation_id"]
            for m in case["explicit_route_operation"]
            if m["route_id"] == route["id"]
        }
    )
    if len(stated) > 1:
        out: dict[str, Any] = {"operation": "CONFLICT", "operation_id": None}
    elif stated:
        known = stated[0] in ids
        out = {
            "operation": "RESOLVED" if known else "UNRESOLVED",
            "operation_id": stated[0] if known else None,
        }
    elif not route["uri"] or route["uris"] or "*" in route["uri"]:
        out = {"operation": "UNRESOLVED", "operation_id": None}
    else:
        methods = {m.upper() for m in route["methods"]}
        found = [
            op["id"]
            for op in operations
            if op["path"] == route["uri"] and (not methods or op["method"].upper() in methods)
        ]
        if len(found) == 1:
            out = {"operation": "RESOLVED", "operation_id": found[0]}
        else:
            out = {"operation": "AMBIGUOUS" if found else "UNRESOLVED", "operation_id": None}
    if out["operation"] != "RESOLVED":
        out.update(contract_version=None, contract_version_id=None)
    else:
        versions = sorted(set(case["operation_contract_versions"].get(out["operation_id"], [])))
        if len(versions) > 1:
            out.update(contract_version="CONFLICT", contract_version_id=None)
        elif versions:
            out.update(contract_version="RESOLVED", contract_version_id=versions[0])
        else:
            out.update(contract_version="UNRESOLVED", contract_version_id=None)
    return out


def _target_service(case: dict[str, Any]) -> dict[str, Any]:
    route = case["route"]
    objects = {("route", route["id"])}
    if route["service_id"]:
        objects.add(("service", route["service_id"]))
    stated = {
        m["service_id"] for m in case["explicit_target_service"] if (m["kind"], m["id"]) in objects
    }
    if "aip/service" in route["labels"]:
        stated.add(route["labels"]["aip/service"])
    for service in case["gateway_services"]:
        if service["id"] == route["service_id"] and "aip/service" in service["labels"]:
            stated.add(service["labels"]["aip/service"])
    if len(stated) > 1:
        return {"target": "CONFLICT", "service_id": None}
    if stated and next(iter(stated)) in case["canonical_service_ids"]:
        return {"target": "RESOLVED", "service_id": next(iter(stated))}
    return {"target": "UNRESOLVED", "service_id": None}


# ---- tests -----------------------------------------------------------------------------------


def test_id_vectors_match_the_frozen_formulas() -> None:
    by_id = {v["id"]: v for v in _load("ids.json")["vectors"]}
    m = by_id
    i = m["M01"]["inputs"]
    assert m["M01"]["expected"] == "urn:aip:source:apisix-measurement:" + _h(
        i["source_id"], i["gateway_instance_id"], i["environment"]
    )
    assert m["M02"]["expected"] != m["M01"]["expected"]
    lines = m["M03"]["inputs"]["extract_lines"]
    assert m["M03"]["expected"] == hashlib.sha256(_lines_to_bytes(lines)).hexdigest()
    w = m["M04"]["inputs"]
    window = (
        w["gateway_instance_id"], w["environment"], w["window_start"], w["window_end"],
        w["start_sha256"], w["end_sha256"],
    )  # fmt: skip
    assert m["M04"]["expected"] == "measurement-window:owned:" + _h(*window)
    assert m["M05"]["inputs"] == w
    assert m["M05"]["expected"] == "evidence:apisix-measurement:" + _h(*window)
    for key, prefix in (("M06", "observed-consumer-interaction"), ("M09", "usage-qualification")):
        p = m[key]["inputs"]
        assert m[key]["expected"] == f"{prefix}:owned:" + _h(
            p["consumer_id"], p["route_id"], p["environment"], p["window_start"], p["window_end"]
        )
    assert m["M09"]["expected"] != m["M06"]["expected"]
    assert len({m[k]["expected"] for k in ("M06", "M07", "M08")}) == 3
    s = m["M10"]["inputs"]
    assert m["M10"]["expected"] == "measurement-series:owned:" + _h(s["window_id"], s["series_key"])
    assert s["window_id"] == m["M04"]["expected"]
    li = m["M11"]["inputs"]
    assert m["M11"]["expected"] == "measurement-limitation:owned:" + _h(
        li["window_id"], li["code"], li["route"], li["response_source"]
    )
    for key in ("M12", "M13"):
        e = m[key]["inputs"]
        assert m[key]["expected"] == "measurement-mapping:owned:" + _h(
            e["gateway_instance_id"], e["environment"], e["kind"], e["source_id"], e["target_id"]
        )
    assert m["M12"]["expected"] != m["M13"]["expected"]
    # the I1 identities this contract builds on
    gw = w["gateway_instance_id"]
    assert m["M06"]["inputs"]["consumer_id"] == "gateway-consumer:owned:" + _h(gw, "spike-alpha")
    assert m["M06"]["inputs"]["route_id"] == "gateway-route:owned:" + _h(gw, "orders-route")
    for vector in m.values():
        assert vector["formula"]


def test_manifest_extract_and_registration_rejections() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    cases = doc["cases"]
    ids = [c["id"] for c in cases]
    assert len(set(ids)) == len(ids)
    for case in cases:
        expected = case["expected"]
        if "registrations" in case:
            keyed: dict[tuple[str, str], list[str]] = {}
            for r in case["registrations"]:
                keyed.setdefault((r["gateway_instance_id"], r["environment"]), []).append(r["id"])
            clashing = sorted(i for group in keyed.values() if len(group) > 1 for i in group)
            if expected["result"] == "REJECTED_CONFLICT":
                assert clashing == sorted(expected["applies_to"]), case["id"]
            else:
                assert not clashing and expected["result"] == "ACCEPTED", case["id"]
            continue
        manifest = json.loads(json.dumps(doc["base_manifest"]))
        start = list(doc["base_start_lines"])
        end = list(doc["base_end_lines"])
        if "start_lines_replace" in case:
            start = list(case["start_lines_replace"])
        end = end + case.get("end_lines_patch", {}).get("append", [])
        ending = case.get("line_ending", "LF")
        start_b, end_b = _lines_to_bytes(start, ending), _lines_to_bytes(end, ending)
        if case.get("hash_policy") != "keep":
            manifest["start_sha256"] = hashlib.sha256(start_b).hexdigest()
            manifest["end_sha256"] = hashlib.sha256(end_b).hexdigest()
        manifest.update(case.get("manifest_patch", {}))
        for name in case.get("manifest_remove", []):
            manifest.pop(name)
        with pytest.raises(Reject) as raised:
            _validate_import(registration, manifest, start_b, end_b)
        assert (raised.value.result, raised.value.code) == (
            expected["result"],
            expected["code"],
        ), case["id"]
    # the unpatched base is accepted
    base = doc["base_manifest"]
    start_b = _lines_to_bytes(doc["base_start_lines"])
    end_b = _lines_to_bytes(doc["base_end_lines"])
    _validate_import(registration, base, start_b, end_b)


def test_mapping_artifact_cases() -> None:
    doc = _load("manifest-rejections.json")
    registration = doc["registration"]
    for case in doc["mapping_cases"]:
        mapping = {**doc["mapping_base"], **case["patch"]}
        expected = case["expected"]
        if expected["result"] == "ACCEPTED":
            _check_mapping(mapping, registration)
            continue
        with pytest.raises(Reject) as raised:
            _check_mapping(mapping, registration)
        assert (raised.value.result, raised.value.code) == (
            expected["result"],
            expected["code"],
        ), case["id"]


def test_series_deltas_and_window_validity() -> None:
    doc = _load("series-deltas.json")
    base = _load("manifest-rejections.json")["base_manifest"]
    start = _parse_extract(_lines_to_bytes(doc["start_lines"]))
    end = _parse_extract(_lines_to_bytes(doc["end_lines"]))
    got = []
    broken: dict[str, int] = {}
    totals: dict[tuple[str, str, str], int] = {}
    for key in sorted(start.keys() | end.keys()):
        labels = (start[key] if key in start else end[key])[0]
        status, delta = _series_status(
            start[key][1] if key in start else None,
            end[key][1] if key in end else None,
            first_in_window=_first_in_window_ok(base, labels["route"]),
        )
        got.append(
            {
                "route": labels["route"],
                "consumer": labels["consumer"],
                "code": labels["code"],
                "response_source": labels["response_source"],
                "matched_uri": labels["matched_uri"],
                "status": status,
                "delta": delta,
            }
        )
        broken.setdefault(labels["route"], 0)
        if labels["response_source"] == UPSTREAM and delta is None:
            broken[labels["route"]] += 1
        if delta is not None:
            tkey = (labels["route"], labels["consumer"], labels["response_source"])
            totals[tkey] = totals.get(tkey, 0) + delta
    sort_key = lambda r: (r["route"], r["consumer"], r["code"], r["matched_uri"])
    assert sorted(got, key=sort_key) == sorted(doc["expected_series"], key=sort_key)
    assert broken == doc["expected_route_broken_upstream"]
    for pair in doc["expected_pair_totals"]:
        r, c = pair["route"], pair["consumer"]
        assert totals.get((r, c, UPSTREAM), 0) == pair["upstream_valid_delta_total"]
        assert totals.get((r, c, APISIX), 0) == pair["rejected_valid_delta_total"]
    for case in doc["window_validity"]:
        manifest = {**base, **case["manifest_patch"]}
        assert _window_reasons(manifest) == case["expected_reasons"], case["id"]
    for case in doc["first_in_window"]:
        manifest = {**base, **case["manifest_patch"]}
        status, delta = _series_status(
            case["start"],
            case["end"],
            first_in_window=_first_in_window_ok(manifest, case["route"]),
        )
        assert (status, delta) == (case["expected_status"], case["expected_delta"]), case["id"]


def test_qualification_truth_table_vectors() -> None:
    doc = _load("qualification.json")
    ids = [c["id"] for c in doc["cases"]]
    assert ids == [f"Q{n:02d}" for n in range(1, len(ids) + 1)]
    for case in doc["cases"]:
        manifest = {**doc["base_manifest"], **case["manifest_patch"]}
        configured = {(c, r) for c, r in case["configured_access"]}
        rows = _qualify(manifest, doc["inventory"], configured, case["series"])
        assert rows == case["expected_rows"], case["id"]


def test_reconciliation_vectors() -> None:
    doc = _load("reconciliation.json")
    assert doc["outcomes"] == ["RESOLVED", "UNRESOLVED", "AMBIGUOUS", "CONFLICT"]
    seen: set[str] = set()
    for case in doc["cases"]:
        inputs, kind = case["inputs"], case["kind"]
        if kind == "runtime-join":
            got = _runtime_join(inputs)
        elif kind == "route-operation":
            got = _route_operation(inputs)
        elif kind == "target-service":
            got = _target_service(inputs)
        else:
            assert kind == "independence"
            got = {}
            if "route_operation" in inputs:
                ro = _route_operation(inputs["route_operation"])
                got["operation"] = ro["operation"]
                if ro["operation_id"]:
                    got["operation_id"] = ro["operation_id"]
            ts = _target_service(inputs["target_service"])
            got["target"] = ts["target"]
            got["service_id"] = ts["service_id"]
        expected = case["expected"]
        assert {k: got[k] for k in expected} == expected, case["id"]
        seen.update(v for v in got.values() if isinstance(v, str))
    assert {"RESOLVED", "UNRESOLVED", "AMBIGUOUS", "CONFLICT"} <= seen


def test_every_i2_section9_case_is_covered_by_a_vector() -> None:
    tags = {c["spec_case"] for c in _load("qualification.json")["cases"]}
    assert tags >= {
        "P1", "P2", "P2-zero-delta", "N1-unsettled", "N1-restart", "N1-label-disabled",
        "N1-route-absent", "N1-prometheus-disabled", "N2", "N2-configured", "N3",
        "N3-rejected", "N3-unknown-consumer", "N4", "one-boundary", "decreased",
        "route-wide-downgrade", "positive-wins", "observed-only", "unknown-route",
        "invalid-window-positive", "invalid-window-observed-only", "multi-code-sum",
        "two-routes-two-consumers", "first-in-window", "first-in-window-uncovered",
        "first-in-window-rejected", "first-in-window-observed-only",
        "first-in-window-label-disabled",
    }  # fmt: skip
    kinds = {c["id"] for c in _load("reconciliation.json")["cases"]}
    assert {"J03", "J04", "J05", "K03", "T06", "T07"} <= kinds  # cross-join, unknown, conflicts
    rejections = {c["spec_case"] for c in _load("manifest-rejections.json")["cases"]}
    assert rejections >= {
        "schema-version", "instance-binding", "environment-mismatch", "binding", "malformed",
        "extract-not-normalized", "duplicate-source", "distinct-pairs-coexist",
    }  # fmt: skip


def test_vectors_import_nothing_from_app() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(from|import)\s+app\b", source, flags=re.MULTILINE)
