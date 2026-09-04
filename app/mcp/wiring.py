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

`build_production_service`'s `Producer.build_revision` uses the same "current git HEAD" fallback
`evaluation.architecture_answers.candidate.resolve_candidate_sha` uses for non-qualification runs,
duplicated here as a ~5-line helper rather than imported from `evaluation/` - that package is a
consumer of `app/`, not the reverse, and I2.2 does not qualify a release candidate (I2 does not
reopen release-candidate qualification at all; see spec §7). Real production build-provenance wiring
is a named I4 concern (spec §10) - this is a placeholder until then, exactly like the evaluator's own
fallback is for ad-hoc/local runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import neo4j

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

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


def build_production_service(
    driver: neo4j.Driver, *, database: str
) -> ArchitectureIntelligenceService:
    producer = Producer(
        name="architecture-intelligence-platform",
        version="0.4.0",
        build_revision=_current_git_sha(),
    )
    return ArchitectureIntelligenceService(driver, database=database, producer=producer)
