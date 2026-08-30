"""Canonical comparison model for the AIP evaluation kernel.

See docs/specifications/0.2.0/i1-evaluation-kernel.md §6-7. Deliberately small: I1 needs only a
relation-fact record, a scenario-owned scope, an observation context, and a loaded scenario - no
larger domain hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# I1 §4.5: the only canonical relation semantics required by the three I1 scenarios.
KNOWN_RELATION_TYPES = frozenset({"CALLS", "PROVIDES", "SENDS", "RECEIVES_FROM"})

_CANONICAL_ID_PREFIXES = tuple(
    f"{kind}:" for kind in ("service", "operation", "queue", "message", "schema")
)


class ScenarioValidationError(ValueError):
    """Invalid scenario configuration (I1 §7.3) - carries scenario/file/field/reason so the loader
    can produce a clear, locatable error rather than a bare exception message."""

    def __init__(self, *, scenario: str, file: str, field: str, reason: str) -> None:
        self.scenario = scenario
        self.file = file
        self.field = field
        self.reason = reason
        super().__init__(f"scenario={scenario} file={file} field={field}: {reason}")


def is_canonical_id(value: object) -> bool:
    return isinstance(value, str) and value.startswith(_CANONICAL_ID_PREFIXES)


@dataclass(frozen=True, order=True)
class RelationFact:
    """One canonical architecture relation fact, as compared by the evaluator (I1 §6.1). Both an
    expected fact (parsed from expected.yaml) and an actual fact (projected from the graph) use
    this same record so the comparator can compare them directly."""

    type: str
    source: str
    target: str
    status: str | None = None
    declared_evidence: bool | None = None
    observed_evidence: bool | None = None


@dataclass(frozen=True)
class ScenarioScope:
    """Scenario-owned comparison scope (I1 §8). A relation is in scope when its source or target is
    a scoped entity, and - if relation_types is given - its type is one of them."""

    entities: tuple[str, ...]
    relation_types: tuple[str, ...] | None = None

    def contains(self, fact: RelationFact) -> bool:
        if self.relation_types is not None and fact.type not in self.relation_types:
            return False
        return fact.source in self.entities or fact.target in self.entities


@dataclass(frozen=True)
class Observation:
    """Runtime observation context (I1 §7.1/§10). environment/window are None for a declaration-only
    scenario that has no runtime telemetry fixture."""

    environment: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    scope: ScenarioScope
    observation: Observation
    expected_relations: tuple[RelationFact, ...]
    path: Path
