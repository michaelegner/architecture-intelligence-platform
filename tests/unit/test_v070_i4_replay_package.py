"""The APISIX replay package is intact and is what the capture session was asked to capture
(v0.7.0 I4.1c; I4 spec §5, decision record D4).

No database and no AIP projection: the committed real captures are checked against the traffic plan
and the revisions the readings were written from, using only the I2 measurement contract's parser
(the lowest layer, the one that reads a normalized extract). If the bytes did not contain what the
plan says was sent, the captures would be wrong, not the readings."""

import ast
import importlib.util
import json

import pytest

from app.sources.apisix_measurement_contract import MANIFEST_FILE, validate_fixture
from evaluation.i4 import apisix_replay as replay

PLAN = replay.PLAN
REPLAY = replay.REPLAY
WINDOWS = {"W1": "r1", "W2": "r2"}
REVISIONS = {"r1": "R1", "r2": "R2"}


def test_the_package_is_intact_and_the_readings_are_the_ones_the_session_executed():
    assert replay.package_problems() == []


def test_the_readings_are_reproduced_by_their_stdlib_author():
    path = REPLAY / "author_replay_expected.py"
    spec = importlib.util.spec_from_file_location("author_replay_expected", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (REPLAY / "expected-replay.json").read_text(encoding="utf-8") == module.render()
    imports = {
        node.module.split(".")[0] if isinstance(node, ast.ImportFrom) else alias.name.split(".")[0]
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (getattr(node, "names", None) or [None])
    }
    assert imports <= {"__future__", "json", "pathlib", "typing"} and "app" not in imports


@pytest.mark.parametrize(("window", "directory"), sorted(WINDOWS.items()))
def test_each_real_window_is_valid_settled_and_covered_as_the_plan_asserts(window, directory):
    metrics = REPLAY / directory / "metrics"
    validated = validate_fixture(
        (metrics / MANIFEST_FILE).read_bytes(),
        (metrics / "apisix-metrics-start.txt").read_bytes(),
        (metrics / "apisix-metrics-end.txt").read_bytes(),
        gateway_instance_id=replay.GATEWAY,
        environment=replay.ENVIRONMENT,
    )
    manifest = validated.manifest
    assert validated.window_reasons == [] and manifest.no_restart
    assert manifest.start_stable_seconds >= 20 and manifest.end_stable_seconds >= 20
    revision = PLAN["revisions"][REVISIONS[directory]]
    assert manifest.route_coverage == {
        route: spec["prometheus"] for route, spec in revision.items()
    }


@pytest.mark.parametrize(("window", "directory"), sorted(WINDOWS.items()))
def test_the_captured_counters_are_exactly_the_planned_traffic(window, directory):
    """Every request of the plan is a counter; no series exists that the plan did not send. The
    start boundary is empty, so each series is first-in-window and its delta is its end value."""
    metrics = REPLAY / directory / "metrics"
    validated = validate_fixture(
        (metrics / MANIFEST_FILE).read_bytes(),
        (metrics / "apisix-metrics-start.txt").read_bytes(),
        (metrics / "apisix-metrics-end.txt").read_bytes(),
        gateway_instance_id=replay.GATEWAY,
        environment=replay.ENVIRONMENT,
    )
    observed = {
        (d.series.labels["consumer"], d.series.labels["route"], d.series.labels["code"],
         d.series.labels["response_source"]): d.delta
        for d in validated.series_deltas()
    }  # fmt: skip
    planned = {}
    for item in PLAN["traffic"][window]:
        if replay_has_series(item["route"], REVISIONS[directory]):
            planned[
                (item["consumer"], item["route"], str(item.get("code", 200)), item["answered_by"])
            ] = item["count"]
    assert observed == planned
    assert not validated.start, "nothing went through the gateway before the window"


def replay_has_series(route: str, revision: str) -> bool:
    """A Route without the prometheus plugin leaves no series (the planned N1 condition)."""
    return PLAN["revisions"][revision][route]["prometheus"]


@pytest.mark.parametrize(("directory", "revision"), sorted(REVISIONS.items()))
def test_each_real_configuration_capture_is_the_revision_it_was_applied_from(directory, revision):
    document = json.loads((REPLAY / directory / "gateway/apisix-capture.json").read_text())
    planned = PLAN["revisions"][revision]
    assert document["gateway_instance_id"] == replay.GATEWAY
    assert document["environment"] == replay.ENVIRONMENT
    assert document["apisix_version"] == "3.19.0"
    assert document["etcd_revision_before"] == document["etcd_revision_after"] > 0
    assert [c["username"] for c in document["consumers"]] == sorted(PLAN["consumers"])
    routes = {route["id"]: route for route in document["routes"]}
    assert set(routes) == set(planned)
    for name, spec in planned.items():
        plugins = routes[name]["plugins"]
        assert ("key-auth" in plugins) is spec["auth"], name
        assert ("prometheus" in plugins) is spec["prometheus"], name
        allow = plugins.get("consumer-restriction", {}).get("whitelist")
        assert allow == spec["allow"], name


def test_the_second_revision_is_a_later_state_of_the_same_gateway():
    first = json.loads((REPLAY / "r1/gateway/apisix-capture.json").read_text())
    second = json.loads((REPLAY / "r2/gateway/apisix-capture.json").read_text())
    assert second["etcd_revision_after"] > first["etcd_revision_after"]
    removed = {r["id"] for r in first["routes"]} - {r["id"] for r in second["routes"]}
    added = {r["id"] for r in second["routes"]} - {r["id"] for r in first["routes"]}
    assert removed == {"billing-route"} and added == {"reports-route"}


def test_the_replay_cases_are_classified_and_required():
    from evaluation.i4.profiles import V07

    assert set(replay.case_ids()) <= V07.required_cases
    assert all(V07.expected_classification(case) for case in replay.case_ids())
    origins = {case["id"]: case["origin"] for case in PLAN["cases"]}
    assert {c for c, origin in origins.items() if origin == "derived"} == {"W-INVALID", "W-NONE"}
