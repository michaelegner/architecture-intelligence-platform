"""Scenario model for the architecture-answers evaluation suite (spec I1.4 §25, generalized to all
three tools by I3.3 spec §29/§31).

Deliberately small: unlike `evaluation.model.RelationFact` (a bespoke comparison record), the
expected side here reuses the real, already-frozen public contract types directly -
`ArchitectureAnswer[ServiceDependenciesData | ArchitectureDriftData | EvidenceData]` - so nothing
about the public envelope can be silently omitted from a scenario's ground truth (I1.4 review
finding #3).

`Request.tool` defaults to `get_service_dependencies` so every one of I1's 8 existing
`request.yaml` files keeps parsing, and keeps meaning, unchanged (I3 spec §29/§51). `Request` is one
dataclass carrying the union of fields both request shapes need (`service_id`/`environment`/
`window_start`/`window_end` for the two dependency-shaped tools, `evidence_refs` for
`get_evidence`) rather than three separate dataclasses - spec §31's dispatch table is deliberately
"dispatch, not architecture semantics", and one shape keeps `loader.py`/`runner.py` from needing a
parallel Scenario/Request class hierarchy for what is still one small, uniform scenario format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    EvidenceData,
    ServiceDependenciesData,
)

TOOL_SERVICE_DEPENDENCIES = "get_service_dependencies"
TOOL_ARCHITECTURE_DRIFT = "get_architecture_drift"
TOOL_EVIDENCE = "get_evidence"

TOOL_NAMES = (TOOL_SERVICE_DEPENDENCIES, TOOL_ARCHITECTURE_DRIFT, TOOL_EVIDENCE)

ExpectedAnswer = (
    ArchitectureAnswer[ServiceDependenciesData]
    | ArchitectureAnswer[ArchitectureDriftData]
    | ArchitectureAnswer[EvidenceData]
)


class ScenarioValidationError(ValueError):
    """Invalid scenario configuration - carries scenario/file/field/reason for a clear, locatable
    error, matching evaluation.model.ScenarioValidationError's shape."""

    def __init__(self, *, scenario: str, file: str, field: str, reason: str) -> None:
        self.scenario = scenario
        self.file = file
        self.field = field
        self.reason = reason
        super().__init__(f"scenario={scenario} file={file} field={field}: {reason}")


@dataclass(frozen=True)
class Request:
    tool: str = TOOL_SERVICE_DEPENDENCIES
    # get_service_dependencies / get_architecture_drift shape:
    service_id: str | None = None
    environment: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    # get_evidence shape:
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    # shared by all three tools:
    snapshot_id: str | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    request: Request
    expected: ExpectedAnswer
    path: Path
