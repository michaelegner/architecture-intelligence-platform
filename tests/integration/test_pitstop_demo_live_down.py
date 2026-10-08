"""v0.6.2 I1c-1: `run.sh --live --down` really removes the live project (review of PR #469).

Needs only Docker (not the private fork): the test creates a stand-in project under the live project's
name from a compose file that lives outside the repository, with a container, an anonymous volume, a
named volume and a network, runs the real `run.sh --live --down` from the repository root (which has a
compose file of its own), and asserts that nothing of the project is left while an unrelated project is
untouched. It skips when the live demo is really running, so a developer's stack is never torn down.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_SH = REPO_ROOT / "examples" / "pitstop-demo" / "run.sh"
RUN_DIR = REPO_ROOT / ".aip-pitstop-live"
DOCKER = shutil.which("docker")
BASH = shutil.which("bash")
PROJECT = "aip-pitstop-live"
CONTROL = "aip-pitstop-down-control"
IMAGE = "python:3.14.7-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d"

pytestmark = [
    pytest.mark.demo_e2e,
    pytest.mark.skipif(DOCKER is None, reason="requires Docker + Compose"),
]

COMPOSE = f"""
services:
  worker:
    image: {IMAGE}
    command: ["sleep", "300"]
    volumes:
      - /anonymous
      - named:/named
    networks: [extra]
volumes:
  named:
networks:
  extra:
"""


def _docker(*args: str) -> str:
    result = subprocess.run(
        [DOCKER, *args], capture_output=True, text=True, timeout=300, check=True
    )
    return result.stdout.strip()


def _leftovers(project: str) -> dict[str, str]:
    label = f"label=com.docker.compose.project={project}"
    return {
        "containers": _docker("ps", "-aq", "--filter", label),
        "networks": _docker("network", "ls", "-q", "--filter", label),
        "volumes": _docker("volume", "ls", "-q", "--filter", label),
    }


def _up(project: str, compose_file: Path) -> None:
    subprocess.run(
        [DOCKER, "compose", "-p", project, "-f", str(compose_file), "up", "-d"],
        cwd=compose_file.parent,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )


def test_down_removes_every_container_volume_and_network_of_the_live_project(tmp_path):
    if any(_leftovers(PROJECT).values()):
        pytest.skip("the live demo project exists; not touching it")
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(COMPOSE)
    try:
        _up(PROJECT, compose_file)
        _up(CONTROL, compose_file)
        before = _leftovers(PROJECT)
        assert all(before.values()), before
        anonymous = _docker(
            "inspect", "-f", "{{range .Mounts}}{{.Name}} {{end}}", before["containers"]
        )
        assert len(anonymous.split()) == 2  # the anonymous and the named volume

        env = {k: v for k, v in os.environ.items() if k != "PITSTOP_FORK_DIR"}
        result = subprocess.run(
            [BASH, str(RUN_SH), "--live", "--down"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert not any(_leftovers(PROJECT).values()), _leftovers(PROJECT)
        assert not [v for v in anonymous.split() if v in _docker("volume", "ls", "-q").split()]
        assert not RUN_DIR.exists()
        assert all(_leftovers(CONTROL).values()), "an unrelated project must be untouched"
    finally:
        for project in (PROJECT, CONTROL):
            subprocess.run(
                [DOCKER, "compose", "-p", project, "-f", str(compose_file), "down", "-v"],
                cwd=tmp_path,
                capture_output=True,
                timeout=300,
                check=False,
            )
