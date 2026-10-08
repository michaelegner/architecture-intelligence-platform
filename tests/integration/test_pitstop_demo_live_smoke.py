"""v0.6.2 I1c-1 smoke test for `run.sh --live` (spec §4.2, §4.3).

The Pitstop fork is private, so CI cannot run this: it SKIPS unless `PITSTOP_FORK_DIR` points at the
instrumented fork (commit 15b21c6 or later) and Docker is available. When it runs it starts the real stack
(instrumented Pitstop -> Collector -> AIP, traffic generator at a short interval), waits for the launcher to
report the first ingest, and then asserts only what does not need a completed UTC day: the live shape of the
publisher's answer for today's (still open) window, i.e. all five receiver routes CONFIRMED with declared and
observed route evidence, one Broker claim and no limitations. `--check` must refuse today's window. The
completed-day check is the hosted one and is evidenced after the first UTC midnight.

Isolation: fixed project `aip-pitstop-live` and port 8000; the test skips when either is taken and tears down
only a stack it started itself.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "pitstop-demo"
RUN_SH = DEMO_DIR / "run.sh"
LIVE_COMPOSE = DEMO_DIR / "live" / "docker-compose.yml"
PROJECT = "aip-pitstop-live"
BASH = shutil.which("bash")
DOCKER = shutil.which("docker")
FORK_DIR = os.environ.get("PITSTOP_FORK_DIR")

pytestmark = [
    pytest.mark.demo_e2e,
    pytest.mark.skipif(DOCKER is None, reason="requires Docker + Compose"),
    pytest.mark.skipif(
        not FORK_DIR, reason="requires PITSTOP_FORK_DIR (the private instrumented Pitstop fork)"
    ),
]


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _compose(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            DOCKER,
            "compose",
            "-p",
            PROJECT,
            "--project-directory",
            str(REPO_ROOT),
            "-f",
            str(LIVE_COMPOSE),
            "--env-file",
            "/dev/null",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env={
            **os.environ,
            "PITSTOP_DEMO_NEO4J_PASSWORD": "unused",
            "PITSTOP_FORK_DIR": FORK_DIR or "",
        },
    )


def _run(
    *args: str, timeout: int, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        [BASH, str(RUN_SH), *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env={**os.environ, **(env or {})},
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _check_ready():
    spec = importlib.util.spec_from_file_location(
        "pitstop_check_ready_live_smoke", DEMO_DIR / "check_ready.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_stack_ingests_real_spans_and_answers_with_every_route_observed():
    if _port_open(8000) or _compose("ps", "-a", "-q").stdout.strip():
        pytest.skip("port 8000 or the live demo project is in use; not touching it")
    try:
        start = _run("--live", timeout=1500, env={"TRAFFIC_INTERVAL_SECONDS": "30"})
        assert start.returncode == 0, start.stdout[-2000:] + start.stderr[-2000:]
        assert "COMPLETED UTC day" in start.stdout

        # `--check` never answers for a window that is not wholly in the past.
        refused = _run("--live", "--check", timeout=120)
        assert refused.returncode == 3 and "No completed window yet" in refused.stdout

        # The launcher reports the first ingested span; the publishers' `send` evidence and every consumer's
        # `process` evidence follow within a few cycles, so poll instead of asserting at once.
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        check_ready = _check_ready()
        problems: list[str] = ["no answer yet"]
        deadline = time.monotonic() + 420
        while problems and time.monotonic() < deadline:
            answer = _compose(
                "exec",
                "-T",
                "architecture-intelligence",
                "python",
                "pitstop/check_ready.py",
                "--live",
                "--date",
                today,
                timeout=300,
            )
            if answer.returncode == 0:
                problems = check_ready.check_answer(json.loads(answer.stdout), live=True)
            else:
                problems = [answer.stdout[-1500:] + answer.stderr[-500:]]
            if problems:
                time.sleep(20)
        assert not problems, problems
    finally:
        _run("--live", "--down", timeout=300)
