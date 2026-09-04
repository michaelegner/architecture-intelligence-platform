"""v0.4.0 I2.2 - lazily gives the `get_service_dependencies` MCP tool body access to a real
`ArchitectureIntelligenceService` (spec `docs/specifications/0.4.0/
i2-mcp-vertical-slice-and-evidence-drill-down.md` §8, §10).

Tool registration (`app.mcp.tools.register_tools`) happens at import time, inside `app.mcp.server`'s
module-level `mcp_server` construction - before FastAPI's lifespan (`app.main.lifespan`) builds
`app.state.driver`. Tool *dispatch* only ever happens per-request, strictly after lifespan startup,
so this module gives the tool body a level of indirection it can resolve lazily: `configure()` runs
once during lifespan startup, `get_service()` runs on every `get_service_dependencies` call.

Named `wiring.py`, not `runtime.py`, to avoid colliding with this codebase's existing "runtime"
vocabulary (`app.settings.RuntimeAnalysisConfig`, `app.api.runtime`), which means *observed* runtime
telemetry - an unrelated domain concept from MCP process wiring.

This module intentionally holds a `neo4j.Driver` reference and constructs
`ArchitectureIntelligenceService` - it does not, itself, open a session, run Cypher, or import
`app.graph.repository`. Spec §8 forbids the *adapter* from doing those things; the session lifecycle
for every real read stays entirely inside `ArchitectureIntelligenceService`, which is already
designed for exactly this indirection ("opens its own `READ_ACCESS` session for every call - no
caller ... is ever handed a session", `app.architecture_intelligence.service`'s own docstring).
Passing a driver reference through to that constructor is not the same as the adapter accessing
Neo4j directly.

`build_production_service`'s `Producer.build_revision` resolution (`_resolve_build_revision`) was
corrected during review: the first version unconditionally ran `git rev-parse HEAD` at lifespan
startup. This repo's production `Dockerfile` is `python:3.13-slim` - no `git` binary, no `.git`
directory copied in - so every real container crashed on startup before serving any endpoint, MCP or
otherwise. `_resolve_build_revision` now prefers an explicit `AIP_BUILD_REVISION` env var (a real
deployment's build/CI step sets this to the exact SHA it built - see `.github/workflows/docker.yml`
and `Dockerfile`'s `ARG`/`ENV`), validated as a real 40-hex SHA if present (a malformed *explicit*
value is a deploy misconfiguration and fails loudly, same as
`evaluation.architecture_answers.candidate.resolve_candidate_sha`'s own `InvalidCandidateSha`).
Only when the env var is absent does it fall back to `git rev-parse HEAD` for local/dev ergonomics
(where `.git` and `git` are normally both present) - and that fallback itself never raises: a missing
git binary or `.git` directory (any container without the env var set) logs a warning and returns the
literal `"unknown"` rather than crashing startup. Real production build-provenance wiring (spec §10)
remains a named I4 concern; this only has to not crash and not silently fabricate a plausible-looking
fake SHA - `"unknown"` is honestly what it is.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path

import neo4j

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService

logger = logging.getLogger("architecture_intelligence.mcp")

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_REVISION_ENV_VAR = "AIP_BUILD_REVISION"
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_UNKNOWN_BUILD_REVISION = "unknown"

_service: ArchitectureIntelligenceService | None = None


def configure(service: ArchitectureIntelligenceService) -> None:
    global _service
    _service = service


def get_service() -> ArchitectureIntelligenceService:
    if _service is None:
        raise RuntimeError(
            "MCP runtime is not configured - call app.mcp.wiring.configure() during application "
            "startup before any tool dispatches"
        )
    return _service


def _current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, cwd=_REPO_ROOT
    )
    return result.stdout.strip()


def _resolve_build_revision() -> str:
    explicit = os.environ.get(_BUILD_REVISION_ENV_VAR)
    if explicit:
        if not _SHA_PATTERN.match(explicit):
            raise RuntimeError(
                f"{_BUILD_REVISION_ENV_VAR} must be a 40-hex git SHA, got {explicit!r}"
            )
        return explicit
    try:
        return _current_git_sha()
    except (OSError, subprocess.CalledProcessError):
        # No AIP_BUILD_REVISION and no git available (e.g. this repo's production container, which
        # has neither the git binary nor a .git directory) - never crash startup over this.
        logger.warning(
            "%s is not set and `git rev-parse HEAD` is unavailable; falling back to a placeholder "
            "build_revision. Set %s in any real deployment.",
            _BUILD_REVISION_ENV_VAR,
            _BUILD_REVISION_ENV_VAR,
        )
        return _UNKNOWN_BUILD_REVISION


def build_production_service(
    driver: neo4j.Driver, *, database: str
) -> ArchitectureIntelligenceService:
    producer = Producer(
        name="architecture-intelligence-platform",
        version="0.4.0",
        build_revision=_resolve_build_revision(),
    )
    return ArchitectureIntelligenceService(driver, database=database, producer=producer)
