"""v0.4.2 I2 - shell-level coverage for `examples/runtime-demo/mcp-demo.sh` itself (spec
`docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md` §42-45/§44.1).

`tests/unit/test_check_fixture_state.py` and `tests/integration/test_check_fixture_state_classification.py`
already cover `check_fixture_state.py`'s classification logic in isolation. Neither drives the shell
script's own orchestration - argument parsing, phase sequencing, the EMPTY/COMPLETE/PARTIAL branch
actually taken, or the promise that `--serve` never issues a scripted MCP call. This module closes
that gap by running the real script against the real `docker-compose.demo.yml` stack, the same way a
user would.

Isolation (PR #139 review, finding 1): the compose project name defaults to the checkout's directory
name - the same identity a developer's own manual demo uses. Running this suite with that default
would tear down and delete a real running demo's volumes on a developer machine (CI's fresh checkout
masks this). Every Compose invocation here therefore uses a unique, test-owned
`COMPOSE_PROJECT_NAME`, and the fixed host ports (8000/7474/7687/4317/4318, which are not
project-scoped) are checked free before touching anything.

`--serve` is exercised as one long journey (`TestServeLifecycle.test_full_lifecycle`) rather than as
independent tests: each phase is a real `docker compose up`/`down` cycle (image build included), and
idempotency (spec §15.4/§45) can only be proven relative to a prior EMPTY run, so splitting it up would
either re-pay the setup cost per test or silently depend on test execution order anyway.

The no-scripted-MCP-call assertion (spec §11/§43) is proven from the AIP container's own uvicorn access
log, not from the script's step headers - a "deterministic server request audit" per §43. PR #139
review (finding 4) noted this cannot assume the container is always recreated between runs: each
audit is bounded with `--since <timestamp captured immediately before that invocation>`, which is
correct whether or not Compose recreates the container, and the log-fetch's own exit code is checked
so a failed log read cannot silently read as "no requests".
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import stat
import subprocess
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_SCRIPT = REPO_ROOT / "examples" / "runtime-demo" / "mcp-demo.sh"
COMPOSE_FILE = REPO_ROOT / "docker-compose.demo.yml"
ENV_FILE = REPO_ROOT / ".env"
BASH = shutil.which("bash")
REAL_DOCKER = shutil.which("docker")
REAL_CURL = shutil.which("curl")

PROJECT_NAME = f"aip-mcp-demo-test-{uuid.uuid4().hex[:8]}"
COMPOSE = ["docker", "compose", "-f", str(COMPOSE_FILE)]
REQUIRED_PORTS = (8000, 7474, 7687, 4317, 4318)

AIP_URL = "http://localhost:8000"
SERVICE_ID = "service:order-service"
ENVIRONMENT = "demo"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

pytestmark = pytest.mark.skipif(
    REAL_DOCKER is None,
    reason="requires Docker + Compose to drive the real demo stack (spec §44.1)",
)


def _env(**overrides: str) -> dict[str, str]:
    merged = {**os.environ, "COMPOSE_PROJECT_NAME": PROJECT_NAME}
    merged.update(overrides)
    return merged


def _run_script(
    *args: str, timeout: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(DEMO_SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env if env is not None else _env(),
    )


def _compose(
    *args: str, timeout: int = 60, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env if env is not None else _env(),
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


def _utc_now_marker() -> str:
    # A couple of seconds of slack before "now" so a log line written in the gap between capturing
    # this marker and the subprocess call that follows is never dropped by `--since`.
    return (datetime.now(UTC) - timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _aip_logs(since: str | None = None) -> str:
    args = ["logs", "architecture-intelligence", "--no-color"]
    if since is not None:
        args += ["--since", since]
    result = _compose(*args, timeout=30)
    assert result.returncode == 0, f"docker compose logs failed: {result.stderr}"
    return result.stdout


def _neo4j_credentials() -> tuple[str, str]:
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values.get("NEO4J_USER", "neo4j"), values["NEO4J_PASSWORD"]


def _inject_stray_node() -> None:
    """Pollutes the graph with one node no manifest/import path ever creates, so the checker must
    classify the fixture as PARTIAL_OR_INCOMPATIBLE (spec §15.2) - proving §45's requirement that
    `--serve` then fails non-zero without importing, reseeding, or repairing anything (PR #139
    review, finding 3: the checker's own classifier tests never invoke `mcp-demo.sh`, so they alone
    cannot prove the *shell script's* reaction to PARTIAL)."""
    user, password = _neo4j_credentials()
    result = _compose(
        "exec",
        "-T",
        "neo4j",
        "cypher-shell",
        "-u",
        user,
        "-p",
        password,
        "CREATE (:Pr139ReviewStrayNode {marker: 'i2.3-review-partial-test'})",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _assert_required_ports_free() -> None:
    busy = []
    for port in REQUIRED_PORTS:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    assert not busy, (
        f"port(s) {busy} required by docker-compose.demo.yml are already in use - stop any "
        "running demo (examples/runtime-demo/mcp-demo.sh --down) before running this test module"
    )


def _ensure_env_file() -> None:
    # The documented prerequisite is `cp .env.example .env` (spec §2) - CI checkouts never carry a
    # (gitignored) .env, so create one rather than skip the whole module.
    if not ENV_FILE.exists():
        ENV_FILE.write_text((REPO_ROOT / ".env.example").read_text())


@pytest.fixture(scope="module")
def clean_demo_stack():
    _ensure_env_file()
    _assert_required_ports_free()
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


class TestPrerequisiteFailures:
    """spec §42: `missing .env` and `missing command` must fail non-zero. Neither needs the
    Compose stack - both are rejected during `validate_prerequisites()`, before any `docker`
    command that touches the demo's own containers."""

    def test_missing_env_exits_nonzero(self, tmp_path):
        _ensure_env_file()
        moved = tmp_path / ".env.bak"
        ENV_FILE.rename(moved)
        try:
            result = _run_script("--serve", timeout=15)
            assert result.returncode != 0
            assert ".env" in result.stderr
        finally:
            moved.rename(ENV_FILE)

    def test_missing_required_command_exits_nonzero(self, tmp_path):
        # A minimal PATH containing only `docker` and `curl` (as absolute-path symlinks) - `jq` is
        # deliberately absent so `validate_prerequisites`'s `command -v jq` fails. `bash` itself is
        # invoked by its own absolute path (BASH), so it never needs to be found via this PATH.
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        for real in (REAL_DOCKER, REAL_CURL):
            link = fake_bin / Path(real).name
            link.symlink_to(real)
        result = _run_script("--serve", timeout=15, env=_env(PATH=str(fake_bin)))
        assert result.returncode != 0
        assert "jq" in result.stderr


class TestServeLifecycle:
    def test_full_lifecycle(self, clean_demo_stack):
        # 1. First `--serve` run starts from EMPTY (spec §7 items 10-11, §8).
        marker_1 = _utc_now_marker()
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
        # the server's own access log (a "deterministic server request audit" per §43), bounded to
        # this invocation's own window so it works whether or not Compose recreated the container.
        logs_after_first = _aip_logs(since=marker_1)
        assert "POST /mcp" not in logs_after_first
        assert "POST /api/import" in logs_after_first  # sanity: the log does capture real requests

        snapshot_1 = _checker_json()
        assert snapshot_1["classification"] == "COMPLETE"
        relations_1 = _observed_relation_count()
        assert relations_1 > 0

        # 2. Second `--serve` run must detect COMPLETE and mutate nothing (spec §15.4/§45): no
        # re-import, no telemetry reseed, identical snapshot, identical observed-relation count.
        marker_2 = _utc_now_marker()
        second = _run_script("--serve", timeout=240)
        assert second.returncode == 0, second.stderr
        assert "fixture classification: COMPLETE" in second.stdout
        assert "skipping declaration re-import and telemetry reseed" in second.stdout
        assert "Importing the declared architecture" not in second.stdout
        assert "Seeding frozen runtime evidence" not in second.stdout

        logs_after_second = _aip_logs(since=marker_2)
        assert "POST /mcp" not in logs_after_second
        assert "POST /api/import" not in logs_after_second

        snapshot_2 = _checker_json()
        assert snapshot_2["classification"] == "COMPLETE"
        assert snapshot_2["actual_snapshot_id"] == snapshot_1["actual_snapshot_id"]
        assert _observed_relation_count() == relations_1

        # 3. No-argument hero mode is unaffected by I2 and still completes the full scripted MCP
        # walkthrough (spec §9/§42 "no args - existing hero flow preserved"), exercised here against
        # the already-COMPLETE fixture from steps 1-2 rather than paying a second EMPTY setup cost.
        hero = _run_script(timeout=120)
        assert hero.returncode == 0, hero.stderr
        assert "fixture classification: COMPLETE" in hero.stdout
        for tool in ("get_service_dependencies", "get_architecture_drift", "get_evidence"):
            assert tool in hero.stdout
        assert "Done - the stack is still running" in hero.stdout

        # 4. A polluted fixture must classify as PARTIAL_OR_INCOMPATIBLE and `--serve` must refuse
        # it non-zero, importing/reseeding/repairing nothing (spec §15.2/§45) - proven against the
        # shell script itself, not only against the checker's own classifier tests.
        _inject_stray_node()
        assert _checker_json()["classification"] == "PARTIAL_OR_INCOMPATIBLE"
        polluted = _run_script("--serve", timeout=60)
        assert polluted.returncode != 0
        assert "PARTIAL_OR_INCOMPATIBLE" in polluted.stderr
        assert "Importing the declared architecture" not in polluted.stdout
        assert "Seeding frozen runtime evidence" not in polluted.stdout

        # 5. Teardown succeeds cleanly (spec §56), including cleaning up the deliberately polluted
        # state from step 4.
        down = _run_script("--down", timeout=120)
        assert down.returncode == 0, down.stderr


class TestTeardownFailure:
    """spec §17/§56: a Compose teardown failure must be reported actionably and exit non-zero,
    never silently succeed. Real `docker compose down` cannot be forced to fail merely by removing
    or corrupting the `-f` file (PR #139 review, finding 2: confirmed on Docker Compose v5.3.1 -
    `down` resolves purely from project-labeled resources and exits 0 with a warning when none
    exist, regardless of whether the compose file is readable). This uses a `docker` test double on
    `PATH` that fails only `compose ... down`, passing every other invocation through to the real
    binary, so the failure is deterministic and independent of what resources happen to exist."""

    def test_down_reports_actionable_failure_when_compose_down_fails(self, tmp_path):
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        fake_docker = fake_bin / "docker"
        fake_docker.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'if [[ "$1" == "compose" ]]; then\n'
            '  for arg in "$@"; do\n'
            '    if [[ "$arg" == "down" ]]; then\n'
            '      echo "fake docker compose down failure (test double, PR #139 review)" >&2\n'
            "      exit 7\n"
            "    fi\n"
            "  done\n"
            "fi\n"
            f'exec "{REAL_DOCKER}" "$@"\n'
        )
        fake_docker.chmod(fake_docker.stat().st_mode | stat.S_IEXEC)

        result = _run_script(
            "--down", timeout=30, env=_env(PATH=f"{fake_bin}:{os.environ['PATH']}")
        )
        assert result.returncode != 0
        assert result.stderr.strip() != ""
