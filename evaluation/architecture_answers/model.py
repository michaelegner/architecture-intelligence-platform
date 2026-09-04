"""Scenario model for the architecture-answers evaluation suite (spec I1.4 §25).

Deliberately small: unlike `evaluation.model.RelationFact` (a bespoke comparison record), the
expected side here reuses the real, already-frozen public contract type directly -
`app.architecture_intelligence.contracts.ArchitectureAnswer[ServiceDependenciesData]` - so nothing
about the public envelope can be silently omitted from a scenario's ground truth (I1.4 review
finding #3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.architecture_intelligence.contracts import ArchitectureAnswer, ServiceDependenciesData


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
    service_id: str
    environment: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    snapshot_id: str | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    request: Request
    expected: ArchitectureAnswer[ServiceDependenciesData]
    path: Path
