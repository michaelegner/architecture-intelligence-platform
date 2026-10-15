"""The per-release qualification profiles (v0.7.0 I4.1b; I4 spec §3, decision record D8).

The v0.6 profile must be exactly what `evaluation/i4/__main__.py` carried before profiles existed
(a stored golden), so the v0.6 I4 record stays reproducible; the v0.7 profile must derive its
required cases and its worker tests from the frozen vectors and the register."""

import json
from pathlib import Path

import pytest

from evaluation.i4 import __main__ as qualification
from evaluation.i4.profiles import DEFAULT_PROFILE, PROFILES, REQUIRED_CI_CHECKS, V06, V07

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / "tests/fixtures/i4/v060-profile.json").read_text(encoding="utf-8"))
SHA = "a" * 40  # synthetic; never qualification evidence


def test_the_v06_profile_is_exactly_the_pre_profile_configuration():
    assert V06.worker_tests() == GOLDEN["worker_tests"]
    assert sorted(V06.required_cases) == GOLDEN["required_cases"]
    assert sorted(V06.required_ci_checks) == GOLDEN["required_ci_checks"]
    assert str(V06.register.relative_to(ROOT)) == GOLDEN["register"]
    assert V06.rejection_prefix == "Q" and V06.runner_module is None


def test_the_module_level_names_other_code_imports_are_the_v06_profile():
    assert qualification.REGISTER == V06.register
    assert qualification.REQUIRED_CASES == set(V06.required_cases)
    assert qualification.REQUIRED_CI_CHECKS == V06.required_ci_checks
    assert qualification.worker_tests() == V06.worker_tests()


def test_v06_is_the_default_so_every_existing_invocation_is_unchanged():
    assert DEFAULT_PROFILE == "v0.6" and PROFILES[DEFAULT_PROFILE] is V06
    assert set(PROFILES) == {"v0.6", "v0.7"}


def test_the_v06_run_is_one_pytest_command_with_the_capture_plugin_as_before():
    [command] = qualification.run_commands(V06, SHA, "A", Path("out"))
    assert command[1:6] == [
        "-m",
        "pytest",
        "-p",
        "evaluation.i4.pytest_plugin",
        *GOLDEN["worker_tests"][:1],
    ]
    assert command[-6:] == ["--i4-candidate-sha", SHA, "--i4-run", "A", "--i4-out", "out"]
    assert command[5:-6] == GOLDEN["worker_tests"]


def test_the_v07_run_is_the_runner_then_the_worker_tests():
    runner, workers = qualification.run_commands(V07, SHA, "B", Path("out"))
    assert runner[1:] == [
        "-m",
        "evaluation.i4.api_usage_runner",
        "--candidate-sha",
        SHA,
        "--run",
        "B",
        "--out",
        "out",
    ]
    assert workers[1:5] == ["-m", "pytest", "-p", "evaluation.i4.test_outcomes"]
    assert workers[5:-2] == V07.worker_tests() and workers[-2:] == ["--i4-out", "out"]


def test_v07_requires_the_57_frozen_i3_cases_and_the_three_bridge_cases():
    i3 = json.loads(
        (ROOT / "docs/specifications/0.7.0/i3-vectors/expected-answers.json").read_text()
    )
    ids = {case["id"] for case in i3["cases"]}
    assert len(ids) == 57
    assert V07.required_cases == ids | {"B07a", "B07b", "B07c"}
    assert V07.rejection_prefix == "V" and all(
        f"V{n:02d}" in V07.required_cases for n in range(1, 23)
    )


def test_v07_worker_tests_cover_every_register_anchor_and_exist():
    register = V07.register.read_text()
    anchors = {line.split("::")[0].strip("`") for line in register.splitlines() if "::" in line}
    paths = {test.split("::")[0] for test in V07.worker_tests()}
    for line in register.splitlines():
        if line.startswith("| S22-"):
            for cell in line.split("|")[3].split(","):
                path = cell.strip().strip("`").split("::")[0]
                if path.startswith("tests/"):
                    assert path in paths, path
    assert anchors  # the register cites checks
    for test in V07.worker_tests():
        assert (ROOT / test.split("::")[0]).is_file(), test


def test_both_profiles_require_the_same_ci_checks():
    assert V06.required_ci_checks == V07.required_ci_checks == REQUIRED_CI_CHECKS
    assert len(REQUIRED_CI_CHECKS) == 13


def test_worker_outcomes_are_folded_into_the_ledger(tmp_path):
    (tmp_path / "ledger.json").write_text(json.dumps({"tests": [], "exit_code": 0}))
    (tmp_path / "tests.json").write_text(
        json.dumps({"exit_code": 1, "tests": [{"nodeid": "t", "outcome": "failed"}]})
    )
    qualification.merge_test_outcomes(tmp_path)
    ledger = json.loads((tmp_path / "ledger.json").read_text())
    assert ledger["exit_code"] == 1 and ledger["tests"] == [{"nodeid": "t", "outcome": "failed"}]


@pytest.mark.parametrize("profile", [V06, V07])
def test_a_profile_without_outcomes_leaves_the_ledger_untouched(tmp_path, profile):
    (tmp_path / "ledger.json").write_text('{"exit_code": 0}')
    qualification.merge_test_outcomes(tmp_path)
    assert json.loads((tmp_path / "ledger.json").read_text()) == {"exit_code": 0}
