"""Record the outcome of every worker test (v0.7.0 I4.1b).

The v0.7 runner (`evaluation.i4.api_usage_runner`) captures the semantic records itself; the worker
tests (the register's executable checks and the end-to-end and frozen-contract gates) only need their
outcomes in the ledger. This plugin writes `tests.json` next to the run's ledger and never touches a
payload. A skipped or failed worker test is visible to the comparator, which blocks on either."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--i4-out", type=Path, required=True)


_TESTS: list[dict] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _TESTS.append(
            {
                "nodeid": item.nodeid,
                "outcome": report.outcome,
                "detail": str(report.longrepr) if report.outcome != "passed" else None,
            }
        )
    elif report.when == "teardown" and report.failed:
        _TESTS.append({"nodeid": item.nodeid, "outcome": "failed", "detail": str(report.longrepr)})


def pytest_sessionfinish(session, exitstatus):
    out: Path = session.config.getoption("--i4-out")
    out.mkdir(parents=True, exist_ok=True)
    (out / "tests.json").write_text(
        json.dumps({"exit_code": int(exitstatus), "tests": _TESTS}, indent=2, sort_keys=True) + "\n"
    )
