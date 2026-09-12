"""v0.4.2 I2 - shell-level coverage for `examples/runtime-demo/mcp-demo.sh` itself (spec
`docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md` §42-45/§44.1).

`tests/unit/test_check_fixture_state.py` and `tests/integration/test_check_fixture_state_classification.py`
already cover `check_fixture_state.py`'s classification logic in isolation. Neither drives the shell
script's own orchestration - argument parsing, phase sequencing, the EMPTY/COMPLETE branch actually
taken, or the promise that `--serve` never issues a scripted MCP call. This module closes that gap by
running the real script against the real `docker-compose.demo.yml` stack, the same way a user would.

`--serve` is exercised as one long journey (`TestServeLifecycle.test_full_lifecycle`) rather than as
independent tests: each phase is a real `docker compose up`/`down` cycle (image build included), and
idempotency (spec §15.4/§45) can only be proven relative to a prior EMPTY run, so splitting it up would
either re-pay the setup cost per test or silently depend on test execution order anyway.

The no-scripted-MCP-call assertion (spec §11/§43) is proven from the AIP container's own uvicorn access
log, not from the script's step headers - a "deterministic server request audit" per §43, independent of
how the script happens to narrate its own steps.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_SCRIPT = REPO_ROOT / "examples" / "runtime-demo" / "mcp-demo.sh"
COMPOSE_FILE = REPO_ROOT / "docker-compose.demo.yml"
COMPOSE = ["docker", "compose", "-f", str(COMPOSE_FILE)]

AIP_URL = "http://localhost:8000"
SERVICE_ID = "service:order-service"
ENVIRONMENT = "demo"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None,
    reason="requires Docker + Compose to drive the real demo stack (spec §44.1)",
)


def _run_script(*args: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(DEMO_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _compose(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _checker_json() -> dict:
    # The exact canonical invocation from spec §15.3/§44.1 - never a host-side `python
    # check_fixture_state.py` call.
    result = _compose(
        "exec",
        "-T",
        "architecture-intelligence",
        "python",
        "examples/runtime-demo/check_fixture_state.py",
        "--json",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _observed_relation_count() -> int:
    url = f"{AIP_URL}/api/runtime/relations?environment={ENVIRONMENT}&since={WINDOW_START}&until={WINDOW_END}"
    with urllib.request.urlopen(url, timeout=10) as response:
        return len(json.load(response)["relations"])


def _aip_logs() -> str:
    return _compose("logs", "architecture-intelligence", "--no-color", timeout=30).stdout


@pytest.fixture(scope="module")
def clean_demo_stack():
    # The documented prerequisite is `cp .env.example .env` (spec §2) - CI checkouts never carry a
    # (gitignored) .env, so create one rather than skip the whole module.
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        env_path.write_text((REPO_ROOT / ".env.example").read_text())

    _compose("down", "-v", timeout=120)
    yield
    _compose("down", "-v", timeout=120)


class TestArgumentContract:
    """spec §10: only `[no args]`, `--serve`, `--down` are accepted. Argument validation happens
    before any Docker/prerequisite check (mcp-demo.sh's own comment: "spec §10: only these exact
    shapes are accepted"), so these need no running stack and no `clean_demo_stack` fixture."""

    @pytest.mark.parametrize(
        "args",
        [("--serve", "--down"), ("--unknown",), ("serve",), ("--serve", "extra")],
        ids=[
            "conflicting-modes",
            "unknown-option",
            "bare-serve-without-dashes",
            "serve-plus-extra",
        ],
    )
    def test_invalid_arguments_exit_2(self, args):
        result = _run_script(*args, timeout=10)
        assert result.returncode == 2, result.stderr


class TestServeLifecycle:
    def test_full_lifecycle(self, clean_demo_stack):
        # 1. First `--serve` run starts from EMPTY (spec §7 items 10-11, §8).
        first = _run_script("--serve", timeout=240)
        assert first.returncode == 0, first.stderr
        assert "fixture classification: EMPTY" in first.stdout
        assert "AIP demo is ready." in first.stdout
        assert f"{AIP_URL}/mcp" in first.stdout
        assert "Service Explorer:" in first.stdout
        assert SERVICE_ID in first.stdout
        assert f"\n{ENVIRONMENT}\n" in first.stdout
        assert WINDOW_START in first.stdout
        assert WINDOW_END in first.stdout
        assert "examples/mcp-clients/README.md" in first.stdout
        assert "examples/runtime-demo/mcp-demo.sh --down" in first.stdout

        # spec §11/§43: --serve must never issue a scripted tools/list or tools/call - proven from
        # the server's own access log (a "deterministic server request audit" per §43), not merely
        # from the absence of the script's own step headers.
        logs_after_first = _aip_logs()
        assert "POST /mcp" not in logs_after_first
        assert "POST /api/import" in logs_after_first  # sanity: the log does capture real requests

        snapshot_1 = _checker_json()
        assert snapshot_1["classification"] == "COMPLETE"
        relations_1 = _observed_relation_count()
        assert relations_1 > 0

        # 2. Second `--serve` run must detect COMPLETE and mutate nothing (spec §15.4/§45): no
        # re-import, no telemetry reseed, identical snapshot, identical observed-relation count.
        second = _run_script("--serve", timeout=240)
        assert second.returncode == 0, second.stderr
        assert "fixture classification: COMPLETE" in second.stdout
        assert "skipping declaration re-import and telemetry reseed" in second.stdout
        assert "Importing the declared architecture" not in second.stdout
        assert "Seeding frozen runtime evidence" not in second.stdout

        # `docker compose up -d --build` can recreate the architecture-intelligence container even
        # when the fixture is untouched (a rebuilt image with unchanged content still gets a new
        # image id), which resets the container's own log history - so this must assert against
        # logs_after_second alone (zero calls since that container started), never a before/after
        # count comparison across a possible restart.
        logs_after_second = _aip_logs()
        assert "POST /mcp" not in logs_after_second
        assert "POST /api/import" not in logs_after_second

        snapshot_2 = _checker_json()
        assert snapshot_2["classification"] == "COMPLETE"
        assert snapshot_2["actual_snapshot_id"] == snapshot_1["actual_snapshot_id"]
        assert _observed_relation_count() == relations_1

        # 3. Teardown succeeds cleanly (spec §56).
        down = _run_script("--down", timeout=120)
        assert down.returncode == 0, down.stderr


class TestTeardownFailure:
    """spec §17/§56: a Compose teardown failure must be reported actionably and exit non-zero,
    never silently succeed. Independent of container state - it only needs the compose file itself
    to be temporarily unavailable."""

    def test_down_reports_actionable_failure_when_compose_file_is_missing(self, tmp_path):
        moved = tmp_path / "docker-compose.demo.yml.bak"
        COMPOSE_FILE.rename(moved)
        try:
            result = _run_script("--down", timeout=30)
            assert result.returncode != 0
            assert result.stderr.strip() != ""
        finally:
            moved.rename(COMPOSE_FILE)
