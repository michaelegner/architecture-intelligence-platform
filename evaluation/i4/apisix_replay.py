"""The APISIX replay package of I4 (v0.7.0 I4.1c; I4 spec §5, decision record D4): integrity, import,
requests and the frozen readings. Shared by the I4 runner and the replay tests; it decides nothing
about equality between runs (the comparator does) and normalizes no answer.

The package (`docs/specifications/0.7.0/i4-replay/`) holds two real captures taken from the pinned
APISIX with the repository's capture tools: `r1` (configuration R1 and window W1) and `r2` (R2, after
a gateway restart, and window W2). The readings the answers are checked against are written in
`expected-replay.json` before any capture; `EXPECTED.sha256` records the digest of the file the
capture session executed, so a reading cannot change after the capture."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.model import (
    ApisixMeasurementSourceConfig,
    ApisixSourceConfig,
    FilesystemSourceConfig,
)
from evaluation.i4.profiles import ROOT

REPLAY = ROOT / "docs/specifications/0.7.0/i4-replay"
PLAN = json.loads((REPLAY / "expected-replay.json").read_text(encoding="utf-8"))
GATEWAY, ENVIRONMENT = PLAN["gateway_instance_id"], PLAN["environment"]
DATABASE = "neo4j"
MANIFEST = "apisix-measurement-manifest.json"
FAKE_SECRETS = ["spike-admin-key-fake", *(f"I4-REPLAY-FAKE-KEY-{c}" for c in PLAN["consumers"])]
# Structural questions of the revision step; they are fences, not readings of captured data.
STRUCTURAL_CASES = ("EV", "REVd", "REVe")


def case_ids() -> list[str]:
    return [case["id"] for case in PLAN["cases"]] + list(STRUCTURAL_CASES)


def package_problems() -> list[str]:
    """The package is intact: every file is listed with its digest, the readings are the ones the
    capture session executed, and no credential is anywhere in it."""
    problems: list[str] = []
    files = {
        str(path.relative_to(REPLAY)): path
        for path in sorted(REPLAY.rglob("*"))
        if path.is_file() and path.parts[-2] in {"gateway", "metrics"}
    }
    listed = {}
    for line in (REPLAY / "SHA256SUMS").read_text().splitlines():
        digest, _, name = line.partition("  ")
        listed[name] = digest
    if set(listed) != set(files):
        problems.append(f"SHA256SUMS lists {sorted(set(listed) ^ set(files))} differently")
    for name, path in files.items():
        if listed.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
            problems.append(f"{name} does not match SHA256SUMS")
        blob = path.read_bytes()
        problems += [f"{name} carries a credential" for s in FAKE_SECRETS if s.encode() in blob]
    expected = hashlib.sha256((REPLAY / "expected-replay.json").read_bytes()).hexdigest()
    if (REPLAY / "EXPECTED.sha256").read_text().strip() != expected:
        problems.append("the readings changed after the capture session executed them")
    return problems


def stage(revision: str, work: Path, *, unsettled_end: bool = False) -> SourcesConfig:
    """Copy a revision into `work` (the package is never written to) and describe its sources. The
    one derived variant, the unsettled end boundary, edits only the copied manifest. Every revision
    lands in the same directory: the source instance is keyed by its root, so one gateway captured
    again is one root updated in place."""
    target = work / "source"
    shutil.copytree(REPLAY / revision, target, dirs_exist_ok=True)
    if unsettled_end:
        manifest = target / "metrics" / MANIFEST
        document = json.loads(manifest.read_text())
        manifest.write_text(json.dumps({**document, "end_settled": False}, indent=2) + "\n")
    return SourcesConfig(
        directories=[FilesystemSourceConfig(id="examples", root=ROOT / "examples")],
        gateways=[
            ApisixSourceConfig(
                id="apisix-replay", root=target / "gateway", gateway_instance_id=GATEWAY
            )
        ],
        gateway_measurements=[
            ApisixMeasurementSourceConfig(
                id="apisix-replay-metrics",
                root=target / "metrics",
                gateway_instance_id=GATEWAY,
                environment=ENVIRONMENT,
            )
        ],
    )


def import_revision(driver: Any, revision: str, work: Path, *, unsettled_end: bool = False) -> None:
    """Import through the production source path. The same source ids make `r2` an authoritative
    update of `r1`, as a second capture of one gateway would be."""
    run_all_configured_sources(
        stage(revision, work, unsettled_end=unsettled_end), driver=driver, database=DATABASE
    )


def read_state(driver: Any) -> dict[str, Any]:
    from app.architecture_intelligence.repository import canonical_snapshot_state

    with driver.session(database=DATABASE) as session:
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def route_ids(state: dict[str, Any]) -> dict[str, str]:
    return {r["route_id"]: r["id"] for r in state["gateway_configuration_v1"]["routes"]}


def consumer_ids(state: dict[str, Any]) -> dict[str, str]:
    return {c["username"]: c["id"] for c in state["gateway_configuration_v1"]["consumers"]}


def request_for(
    case: dict[str, Any], state: dict[str, Any], *, removed_routes: dict[str, str] | None = None
) -> dict[str, Any]:
    """The request of a reading. A Route that no longer exists in `state` is addressed by the id it
    had in the earlier revision (`removed_routes`)."""
    window = state["api_usage_v1"]["windows"][0]
    route = case["target"]["route"]
    ids = route_ids(state) | (removed_routes or {})
    request: dict[str, Any] = {
        "mode": "query",
        "target": {"kind": "GATEWAY_ROUTE", "id": ids[route]},
        "gateway_instance_id": GATEWAY,
        "environment": ENVIRONMENT,
        "window_start": window["window_start"],
        "window_end": window["window_end"],
    }
    if case["consumer"]:
        request["consumer_id"] = consumer_ids(state)[case["consumer"]]
    if case["id"] == "W-NONE":
        request["window_end"] = _one_hour_later(window["window_end"])
    return request


def _one_hour_later(timestamp: str) -> str:
    from datetime import UTC, datetime, timedelta

    moment = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return (moment + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reading_problems(
    case: dict[str, Any], answer: dict[str, Any], state: dict[str, Any]
) -> list[str]:
    """Where the answer departs from the frozen reading of the case (empty: it agrees). `state` is
    the snapshot state the answer was projected from, used only to name consumers."""
    expect = case["expect"]
    codes = sorted(item["code"] for item in answer["limitations"])
    if "refusal" in expect:
        return (
            []
            if answer["data"] is None and codes == [expect["refusal"]]
            else [f"{case['id']}: expected the refusal {expect['refusal']}, got {codes}"]
        )
    problems: list[str] = []
    data = answer["data"]
    if data is None:
        return [f"{case['id']}: refused with {codes}"]
    if answer["outcome"] != expect["outcome"] or codes != expect["limitations"]:
        problems.append(f"{case['id']}: outcome {answer['outcome']} {codes}")
    if data["window"]["valid"] is not expect["window_valid"]:
        problems.append(f"{case['id']}: window validity")
    selected = sorted({c for route in data["selected_routes"] for c in route["limitations"]})
    if selected != sorted(expect["route_limitations"]):
        problems.append(f"{case['id']}: route limitations {selected}")
    names = {v: k for k, v in consumer_ids(state).items()}
    actual = {
        names[row["consumer"]["id"]]: (
            row["configured_access"]["status"],
            row["usage"]["status"],
            row["usage"].get("upstream_request_count"),
            row["usage"].get("rejected_attempt_count"),
            row["usage"]["coverage"],
            [c for c in row["limitations"]],
        )
        for row in data["rows"]
    }
    wanted = {
        row["consumer"]: (
            row["configured_access"],
            row["usage"],
            row["upstream_request_count"],
            row["rejected_attempt_count"],
            row["coverage"],
            row["limitations"],
        )
        for row in expect["rows"]
    }
    if actual != wanted or len(data["rows"]) != len(expect["rows"]):
        problems.append(f"{case['id']}: rows {actual} != {wanted}")
    return problems
