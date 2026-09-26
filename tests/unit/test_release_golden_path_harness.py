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
        "schema_version": "0.5",
        "producer": {"version": "0.5.0", "build_revision": "a" * 40},
    }
    assert gp.producer_identity_mismatches([good], version="0.5.0", sha="a" * 40) == []
    bad = {"schema_version": "0.4", "producer": {"version": "0.4.2", "build_revision": "b" * 40}}
    assert len(gp.producer_identity_mismatches([bad], version="0.5.0", sha="a" * 40)) == 3


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
