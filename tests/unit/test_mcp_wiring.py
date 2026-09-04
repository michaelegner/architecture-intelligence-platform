"""v0.4.0 I2.2 review fix - `app.mcp.wiring._resolve_build_revision` must never crash application
startup, in particular in this repo's production container (`Dockerfile`'s `python:3.13-slim` base
has no `git` binary and no `.git` directory copied in). The first version of this module ran
`git rev-parse HEAD` with `check=True` unconditionally, which would have crashed every real
deployment before serving any endpoint - this is the regression test for that fix.
"""

from __future__ import annotations

import subprocess

import pytest

from app.mcp import wiring

_VALID_SHA = "a" * 40


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(wiring._BUILD_REVISION_ENV_VAR, raising=False)


def test_explicit_env_var_is_used_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(wiring._BUILD_REVISION_ENV_VAR, _VALID_SHA)
    assert wiring._resolve_build_revision() == _VALID_SHA


def test_malformed_explicit_env_var_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(wiring._BUILD_REVISION_ENV_VAR, "not-a-sha")
    with pytest.raises(RuntimeError, match="AIP_BUILD_REVISION"):
        wiring._resolve_build_revision()


def test_falls_back_to_git_head_when_env_var_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wiring, "_current_git_sha", lambda: _VALID_SHA)
    assert wiring._resolve_build_revision() == _VALID_SHA


def test_missing_git_binary_falls_back_to_placeholder_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates this repo's actual production container: no AIP_BUILD_REVISION, no git binary."""

    def _raise_missing_git() -> str:
        raise FileNotFoundError("git")

    monkeypatch.setattr(wiring, "_current_git_sha", _raise_missing_git)
    assert wiring._resolve_build_revision() == wiring._UNKNOWN_BUILD_REVISION


def test_no_git_directory_falls_back_to_placeholder_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates a git binary present but no .git directory (e.g. a stripped-down image copy)."""

    def _raise_not_a_repo() -> str:
        raise subprocess.CalledProcessError(128, ["git", "rev-parse", "HEAD"])

    monkeypatch.setattr(wiring, "_current_git_sha", _raise_not_a_repo)
    assert wiring._resolve_build_revision() == wiring._UNKNOWN_BUILD_REVISION
