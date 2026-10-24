"""v0.5.0 I6 Slice 1b: guards for the release golden-path harness (I6 §7.4).

The harness is `examples/release-golden-path/run.sh`, `golden_path.py` and `compose/`. These tests
pin:
- its frozen Compose invocation and run identity (`:?`-only interpolation, digest-pinned
  third-party images, per-phase mounts that equal the frozen `phase.yaml`);
- a one-to-one mapping from `expected.json` check ids to implementations;
- the verbatim reuse of the pubsub component's own oracle queries and projections;
- the pure comparison functions on passing and failing inputs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import tests.integration.test_i4_pubsub_qualification as i4

REPO = Path(__file__).resolve().parents[2]
GP_DIR = REPO / "examples" / "release-golden-path"
PHASES = ("demo", "pubsub", "k8s-agree", "k8s-conflict", "k8s-unresolved")


def _load_harness():
    spec = importlib.util.spec_from_file_location("golden_path", GP_DIR / "golden_path.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gp = _load_harness()


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


# --- frozen Compose invocation -------------------------------------------------------------------


def test_base_compose_interpolates_only_the_three_required_variables():
    text = "\n".join(
        line
        for line in (GP_DIR / "compose" / "docker-compose.base.yml").read_text().splitlines()
        if not line.lstrip().startswith("#")
    )
    references = re.findall(r"\$\{[^}]*\}", text)
    assert references
    for reference in references:
        assert re.fullmatch(r"\$\{[A-Z0-9_]+:\?[^}]*\}", reference), reference
    assert {re.match(r"\$\{([A-Z0-9_]+)", r)[1] for r in references} == {
        "GP_IMAGE",
        "GP_CONFIG_PATH",
        "GP_NEO4J_PASSWORD",
    }


def test_base_compose_runs_the_image_under_test_and_pins_every_other_image():
    services = _yaml(GP_DIR / "compose" / "docker-compose.base.yml")["services"]
    assert set(services) == {"architecture-intelligence", "neo4j", "otel-collector"}
    assert all("build" not in service for service in services.values())
    assert services["architecture-intelligence"]["image"].startswith("${GP_IMAGE:?")
    assert services["architecture-intelligence"]["environment"]["OPENAI_API_KEY"] == ""
    for name in ("neo4j", "otel-collector"):
        assert re.search(r"@sha256:[0-9a-f]{64}$", services[name]["image"]), name
    # The MCP host allowlist admits localhost:8000 only (app/settings.py).
    assert services["architecture-intelligence"]["ports"] == ["127.0.0.1:8000:8000"]


@pytest.mark.parametrize("phase", PHASES)
def test_phase_override_mounts_equal_the_frozen_phase_yaml(phase):
    override = _yaml(GP_DIR / "compose" / f"{phase}.yml")
    assert set(override["services"]) == {"architecture-intelligence"}
    [service] = override["services"].values()
    assert set(service) == {"volumes"}
    mounts = _yaml(GP_DIR / "profile" / phase / "phase.yaml")["mounts"]
    assert service["volumes"] == [f"./{m['from']}:{m['to']}:ro" for m in mounts]


def test_compose_argv_is_the_frozen_invocation():
    assert gp.compose_argv("pubsub", "up", "-d") == [
        "docker",
        "compose",
        "-p",
        "gp-pubsub",
        "--project-directory",
        str(REPO),
        "-f",
        str(GP_DIR / "compose" / "docker-compose.base.yml"),
        "-f",
        str(GP_DIR / "compose" / "pubsub.yml"),
        "--env-file",
        "/dev/null",
        "up",
        "-d",
    ]


def test_compose_is_invoked_only_through_the_frozen_helper():
    source = (GP_DIR / "golden_path.py").read_text()
    # One docker-compose argv (compose_argv); `_docker` is only ever used for inspect calls.
    assert len(re.findall(r'"docker",\s*"compose"', source)) == 1
    assert not re.search(r'_docker\(\s*"compose"', source)
    assert not re.search(r'"docker-compose"\s*,', source)  # no legacy v1 binary
    assert "compose" not in (GP_DIR / "run.sh").read_text().replace("compose/", "")


def test_stack_environment_drops_compose_profiles(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "surprise")
    stack = gp.Stack("demo", image_ref="img", config_path="c.yaml", password="pw")
    assert "COMPOSE_PROFILES" not in stack.env
    assert stack.env["GP_IMAGE"] == "img"


# --- run.sh preflight ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("args", "sha"),
    [
        (["img", "/tmp/out"], None),
        (["img", "/tmp/out"], "HEAD"),
        (["img", "/tmp/out"], "A" * 40),
        (["img"], "a" * 40),
    ],
)
def test_run_sh_requires_an_explicit_full_candidate_sha_and_two_arguments(args, sha, tmp_path):
    env = {"PATH": "/usr/bin:/bin"}
    if sha is not None:
        env["RELEASE_CANDIDATE_SHA"] = sha
    result = subprocess.run(
        ["bash", str(GP_DIR / "run.sh"), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "usage" in result.stderr


# --- expected.json <-> implementation ------------------------------------------------------------


def test_every_expected_check_has_exactly_one_implementation():
    expected = json.loads((GP_DIR / "expected.json").read_text())["phases"]
    assert tuple(gp.PHASES) == PHASES
    assert set(gp.CHECKS) == set(expected) == set(gp.DRIVERS)
    for phase, spec in expected.items():
        assert list(gp.CHECKS[phase]) == [check["id"] for check in spec["checks"]], phase


# --- verbatim reuse of the pubsub component oracle -----------------------------------------------


def test_pubsub_oracle_queries_are_the_component_tests_own():
    assert gp.FACTS_QUERY == i4._FACTS_QUERY
    assert gp.DEAD_LETTER_QUERY == i4._DEAD_LETTER_QUERY
    assert gp.ENTITY_QUERY.format(label="Topic") == "MATCH (n:Topic) RETURN n.name AS name"


_CLAIM = {
    "object": {"type": "SERVICE", "name": "fulfillment"},
    "delivery": {"via": {"type": "TOPIC", "name": "orders"}, "subscription": {"name": "f"}},
    "destination_resolution": "RESOLVED_SERVICE",
    "qualification": "NOT_OBSERVED_IN_WINDOW",
    "evidence_refs": ["e:2", "e:1"],
    "resolution_evidence_refs": ["r:1"],
    "subject": {"id": "service:checkout"},
}


def test_claim_shape_and_answer_refs_match_the_component_tests():
    assert gp.claim_shape(_CLAIM) == i4._claim_shape(_CLAIM)
    answer = {"evidence_refs": ["e:0"], "claims": [_CLAIM]}
    assert gp.answer_refs(answer) == i4._answer_refs(answer) == ["e:0", "e:1", "e:2", "r:1"]


# --- pure comparisons, passing and failing -------------------------------------------------------


def test_drift_projection_matches_the_fixture_state_shape():
    answer = {"outcome": "PARTIAL", "claims": [_CLAIM]}
    assert gp.project_drift_claims(answer) == [
        {
            "subject": "service:checkout",
            "target": "fulfillment",
            "via": "orders",
            "qualification": "NOT_OBSERVED_IN_WINDOW",
            "evidence_refs": ["e:1", "e:2"],
        }
    ]
    assert gp.project_drift_claims({"outcome": "NOT_ANSWERED", "claims": [_CLAIM]}) == []


def test_producer_identity_flags_every_wrong_field():
    good = {
        "tool": "get_architecture_drift",
        "schema_version": "0.5",
        "producer": {"version": "0.5.0", "build_revision": "a" * 40},
    }
    assert gp.producer_identity_mismatches([good], version="0.5.0", sha="a" * 40) == []
    bad = {
        "tool": "get_architecture_drift",
        "schema_version": "0.4",
        "producer": {"version": "0.4.2", "build_revision": "b" * 40},
    }
    assert len(gp.producer_identity_mismatches([bad], version="0.5.0", sha="a" * 40)) == 3


_BROKER_CLAIM = {"predicate": "USES_BROKER"}
_DEP_CLAIM = {"predicate": "DIRECT_DEPENDENCY", "qualification": "OBSERVED_ONLY"}
_BROKER_RECORD = {"supports": [{"relation_type": "USES_BROKER"}]}
_PLAIN_RECORD = {"supports": [{"relation_type": "CALLS"}]}


@pytest.mark.parametrize(
    ("answer", "version"),
    [
        ({"tool": "get_service_dependencies", "claims": [_DEP_CLAIM]}, "0.5"),
        ({"tool": "get_service_dependencies", "claims": [_BROKER_CLAIM, _DEP_CLAIM]}, "0.6"),
        ({"tool": "get_evidence", "data": {"records": [_PLAIN_RECORD]}}, "0.5"),
        ({"tool": "get_evidence", "data": {"records": [_PLAIN_RECORD, _BROKER_RECORD]}}, "0.6"),
        ({"tool": "get_architecture_drift", "claims": [_DEP_CLAIM]}, "0.5"),
        ({"tool": "get_service_dependencies_by_locality"}, "0.6"),
        ({"tool": "something_else"}, None),
    ],
)
def test_expected_schema_version_is_tool_specific(answer, version):
    assert gp.expected_schema_version(answer) == version


def test_producer_identity_rejects_the_wrong_version_for_the_content():
    producer = {"version": "0.6.1", "build_revision": "a" * 40}
    with_broker = {
        "tool": "get_service_dependencies",
        "claims": [_BROKER_CLAIM],
        "producer": producer,
    }
    for claimed, problems in (("0.6", 0), ("0.5", 1)):
        answer = {**with_broker, "schema_version": claimed}
        found = gp.producer_identity_mismatches([answer], version="0.6.1", sha="a" * 40)
        assert len(found) == problems


def test_drift_subset_ignores_broker_claims():
    answer = {"claims": [_BROKER_CLAIM, _DEP_CLAIM]}
    assert gp.drift_subset(answer) == [_DEP_CLAIM]
    assert gp.dependency_claims(answer) == [_DEP_CLAIM]


def _phase(records: dict, expected_checks: dict | None = None, **extra) -> SimpleNamespace:
    return SimpleNamespace(
        records=records,
        expected={"checks": expected_checks or {}},
        answers=[],
        sha="a" * 40,
        **extra,
    )


def test_zero_writes_fails_on_an_advanced_or_missing_fence():
    assert gp.check_zero_writes(_phase({"fence_before": 3, "fence_after": 3}))[0] is True
    assert gp.check_zero_writes(_phase({"fence_before": 3, "fence_after": 4}))[0] is False
    assert gp.check_zero_writes(_phase({"fence_before": None, "fence_after": None}))[0] is False


def test_producer_identity_check_fails_with_no_answers():
    assert gp.check_producer_identity(_phase({}))[0] is False


def _k8s_report(fs_result="ACCEPTED", k8s_status="COMPLETE") -> dict:
    return {
        "committed": True,
        "report_version": "aip-import-report/1",
        "runs": [
            {
                "kind": "filesystem",
                "inventory_status": "COMPLETE",
                "committed": True,
                "source_results": [{"result": fs_result, "diagnostics": []}],
            },
            {
                "kind": "kubernetes",
                "configured_source_id": "aip-i2-independent-capture",
                "inventory_status": k8s_status,
                "committed": True,
                "source_results": [{"result": "ACCEPTED", "diagnostics": []}],
            },
        ],
    }


def test_k8s_import_check_passes_and_fails():
    assert gp.check_import_k8s(_phase({"import": _k8s_report()}))[0] is True
    assert (
        gp.check_import_k8s(_phase({"import": _k8s_report(fs_result="REJECTED_INVALID")}))[0]
        is False
    )
    assert gp.check_import_k8s(_phase({"import": _k8s_report(k8s_status="PARTIAL")}))[0] is False


def test_pubsub_source_results_are_keyed_by_locator_parent():
    report = {
        "runs": [
            {
                "source_results": [
                    {
                        "locator": "checkout/asyncapi.yaml",
                        "result": "ACCEPTED",
                        "diagnostics": [],
                    }
                ]
            }
        ]
    }
    assert gp.source_results_by_slug(report) == {
        "checkout": {"result": "ACCEPTED", "diagnostics": []}
    }


def _resolution(rid, status="UNRESOLVED", service_id=None, workload=None):
    return {"resolution_id": rid, "status": status, "service_id": service_id, "workload": workload}


def test_unresolved_deployment_check_counts_only_null_service_and_workload():
    expected = {
        "deployment": {
            "expect": {"unresolved_resolutions": {"count": 2, "distinct_resolution_ids": 2}}
        }
    }
    explicit = _resolution(
        "r0", status="RESOLVED_EXPLICIT", service_id="service:runtime-demo", workload={"name": "w"}
    )
    two = [explicit, _resolution("r1"), _resolution("r2")]

    def run(resolutions, rest=None):
        records = {
            "deployment_mcp": {"data": {"deployment_resolutions": resolutions}},
            "deployment_rest": {"deployment_resolutions": resolutions if rest is None else rest},
        }
        return gp.check_deployment_unresolved(_phase(records, expected))[0]

    assert run(two) is True
    assert run(two[:2]) is False
    assert run([explicit, _resolution("r1"), _resolution("r1")]) is False
    assert run(two, rest=two[:2]) is False


def test_validate_schema_selects_the_frozen_schema_of_the_required_version(monkeypatch):
    seen = []
    monkeypatch.setattr(gp.jsonschema, "validate", lambda instance, schema: seen.append(schema))
    base = {"tool": "get_service_dependencies", "claims": []}
    gp.validate_schema("dependencies", {**base, "schema_version": "0.5"})
    gp.validate_schema("dependencies", {**base, "claims": [_BROKER_CLAIM], "schema_version": "0.6"})
    assert [s["properties"]["schema_version"]["const"] for s in seen] == ["0.5", "0.6"]
    for wrong in (
        {**base, "claims": [_BROKER_CLAIM], "schema_version": "0.5"},
        {**base, "schema_version": "0.6"},
        {"tool": "unknown", "schema_version": "0.5"},
    ):
        with pytest.raises(gp.HarnessError):
            gp.validate_schema("dependencies", wrong)


# --- v0.7.0 I5: five tools and the `api-usage` phase ----------------------------------------------


def _load_api_usage_replay():
    import sys

    sys.path.insert(0, str(GP_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "api_usage_replay", GP_DIR / "api_usage_replay.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(GP_DIR))


def test_the_release_profile_advertises_the_six_tools_in_lexicographic_order():
    assert len(gp.TOOLS) == 6 and gp.TOOLS == sorted(gp.TOOLS)
    assert gp.TOOLS[0] == "get_api_consumer_usage"
    assert gp.TOOLS[2] == "get_destination_consumers"


def test_the_api_usage_phase_mounts_only_its_frozen_configuration():
    override = _yaml(GP_DIR / "compose" / "api-usage.yml")
    [service] = override["services"].values()
    assert set(service) == {"volumes"}
    assert service["volumes"] == [
        "./examples/release-golden-path/profile/api-usage/config.yaml:/app/golden-path/config.yaml:ro"
    ]
    assert gp.compose_argv("api-usage", "up")[3] == "gp-api-usage"


def test_the_api_usage_configuration_registers_the_roots_the_harness_fills():
    api = _load_api_usage_replay()
    sources = _yaml(GP_DIR / "profile" / "api-usage" / "config.yaml")["architecture_intelligence"][
        "sources"
    ]
    [gateway] = sources["gateways"]
    [measurement] = sources["gateway_measurements"]
    assert gateway["root"] == f"{api.CONTAINER_ROOT}/gateway"
    assert measurement["root"] == f"{api.CONTAINER_ROOT}/metrics"
    assert gateway["gateway_instance_id"] == measurement["gateway_instance_id"]
    assert measurement["environment"] == "replay"


def test_the_api_usage_cases_are_frozen_i4_cases_and_the_harness_authors_none():
    api = _load_api_usage_replay()
    frozen = {c["id"] for c in api.replay.PLAN["cases"]}
    assert set(api.R1_CASES) | set(api.R2_CASES) <= frozen
    assert (GP_DIR / "api_usage_replay.py").read_text().count("expected-replay.json") >= 1
    block = json.loads((GP_DIR / "expected.json").read_text())["api_usage_phase"]
    assert block["id"] == "api-usage"
    assert all((REPO / path).exists() for path in block["source"])


def test_the_api_usage_pure_checks_pass_and_fail():
    api = _load_api_usage_replay()
    stale = {"data": None, "limitations": [{"code": "SNAPSHOT_NOT_AVAILABLE"}]}
    assert api._refused_as_stale(stale)
    assert not api._refused_as_stale({"data": None, "limitations": [{"code": "UNKNOWN_TARGET"}]})
    assert not api._refused_as_stale({"data": {}, "limitations": []})
    assert api._agree("x", {"a": 1, "b": 2}, {"b": 2, "a": 1}) == []
    assert api._agree("x", {"a": 1}, {"a": 2}) == ["x: REST and MCP differ"]
    resolved = {"outcome": "ANSWERED", "data": {"entries": [{"status": "RESOLVED"}]}}
    assert api._resolved(resolved)
    assert not api._resolved(
        {"outcome": "ANSWERED", "data": {"entries": [{"status": "NOT_RESOLVED"}]}}
    )
    wrong = [("P1", "rest", {"schema_version": "0.6", "producer": {"version": "0.6.3"}})]
    assert len(api._identity_problems(wrong, "0.7.0", "a" * 40)) >= 3


# --- v0.7.1 I5: six tools and the `destination-consumers` phase -----------------------------------


def _load_destination_consumers_replay():
    import sys

    sys.path.insert(0, str(GP_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "destination_consumers_replay", GP_DIR / "destination_consumers_replay.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(GP_DIR))


def test_the_destination_consumers_phase_mounts_only_its_frozen_configuration():
    override = _yaml(GP_DIR / "compose" / "destination-consumers.yml")
    [service] = override["services"].values()
    assert set(service) == {"volumes"}
    mount = "./examples/release-golden-path/profile/destination-consumers/config.yaml"
    assert service["volumes"] == [f"{mount}:/app/golden-path/config.yaml:ro"]
    assert gp.compose_argv("destination-consumers", "up")[3] == "gp-destination-consumers"


def test_the_destination_consumers_configuration_registers_the_roots_the_harness_fills():
    dc = _load_destination_consumers_replay()
    sources = _yaml(GP_DIR / "profile" / "destination-consumers" / "config.yaml")[
        "architecture_intelligence"
    ]["sources"]
    [declarations] = sources["directories"]
    [capture] = sources["kafka_consumer_state"]
    [mapping] = sources["kafka_service_mappings"]
    assert declarations["root"] == f"{dc.CONTAINER_ROOT}/declarations"
    assert capture["root"] == f"{dc.CONTAINER_ROOT}/kafka"
    assert mapping["root"] == f"{dc.CONTAINER_ROOT}/mapping"
    for source in (capture, mapping):
        assert source["broker_id"] == dc.EXPECTED["broker_id"]
        assert source["environment"] == dc.EXPECTED["environment"]
    assert capture["consumer_groups"] == dc.EXPECTED["capture_allow_list"]


def test_the_destination_consumers_expectations_are_the_frozen_i4_ones():
    dc = _load_destination_consumers_replay()
    digest = hashlib.sha256((dc.KAFKA / "expected.json").read_bytes()).hexdigest()
    assert (dc.KAFKA / "EXPECTED.sha256").read_text().split()[0] == digest
    for capture in ("c1", "c2"):
        assert set(dc.EXPECTED[capture]["with_mapping"]) == set(dc.TOPICS)
    block = json.loads((GP_DIR / "expected.json").read_text())["destination_consumers_phase"]
    assert block["id"] == "destination-consumers"
    assert all((REPO / path).exists() for path in block["source"])


def test_the_destination_consumers_reading_check_passes_and_fails():
    dc = _load_destination_consumers_replay()
    want = dc.EXPECTED["c1"]["with_mapping"]["orders.created"]
    t = "2026-10-19T06:21:23Z"
    rows = [
        {
            "group_id": "ops-tail",
            "outcome": "UNRESOLVED",
            "reason": "NO_MAPPING",
            "captured_at": t,
            "attachment_evidence_refs": ["r1"],
            "mapping_evidence_refs": [],
        },
        {
            "group_id": "payment-service",
            "outcome": "RESOLVED",
            "service_id": "service:payment-service",
            "captured_at": t,
            "attachment_evidence_refs": ["r2"],
            "mapping_evidence_refs": ["r3"],
        },
    ]
    good = {
        "outcome": "PARTIAL",
        "limitations": [{"code": "CAPTURE_SCOPE_LIMITED"}],
        "data": {"rows": rows},
    }
    assert dc.reading_problems(good, want, t) == []
    assert dc.reading_problems(good, want, "2026-10-19T06:23:28Z")
    assert dc.reading_problems({**good, "data": {"rows": rows + rows[:1]}}, want, t)
    assert dc.reading_problems({**good, "data": {"rows": rows[1:]}}, want, t)
    assert dc.reading_problems({**good, "note": "analytics-tap"}, want, t)
    assert dc.reading_problems({**good, "note": "console-consumer-1"}, want, t)
    resolved = {"outcome": "ANSWERED", "data": {"entries": [{"ref": "r1", "status": "RESOLVED"}]}}
    assert dc._resolved(resolved, ["r1"])
    assert not dc._resolved(resolved, ["r1", "r2"])
    wrong = [("c1", "rest", {"schema_version": "0.7", "producer": {"version": "0.7.0"}})]
    assert len(dc._identity_problems(wrong, "0.7.1", "a" * 40)) >= 3
