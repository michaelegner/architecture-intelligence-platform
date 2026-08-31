"""Canonical model for the AIP real-world validation contract.

See docs/specifications/0.3.0/i1-real-world-validation-contract.md. I1 freezes the methodology that
I2 (Quarkus Super Heroes) and I3 (Apache Airflow) must use later - the finding vocabulary (I1 §13),
severity (I1 §14), the expected.yaml shape (I1 §17), and the comparator's output record (I1 §20).
This module deliberately does not import from `evaluation/` (the v0.2 synthetic evaluation kernel):
the two are separate, unrelated methodology kernels, and the few primitives they happen to share
(a canonical-id prefix check, a small relation-type set) are small enough to duplicate rather than
couple the two packages together.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# I1 §13: the six finding classifications are frozen - no 7th "unexpected" bucket exists here,
# unlike evaluation.comparator.UNEXPECTED. An unexpected in-scope actual fact is reported as
# INCORRECT_SUPPORTED instead (see comparator.py).
CLASSIFICATIONS = frozenset(
    {
        "CORRECT",
        "MISSING_SUPPORTED",
        "INCORRECT_SUPPORTED",
        "UNSUPPORTED",
        "UNRESOLVED_IDENTITY",
        "INSUFFICIENT_EVIDENCE",
    }
)

# I1 §14: severity stays a distinct concept from classification.
SEVERITIES = frozenset({"CRITICAL", "MAJOR", "MINOR", "INFO"})

# I1 §21's sort key: "classification, severity, relation type, source, target, finding id" -
# ranks give that ordering a concrete, documented, tested total order. Most-severe-in-scope-of-
# error classifications sort first so a report's worst findings are read first.
CLASSIFICATION_RANK: dict[str, int] = {
    "INCORRECT_SUPPORTED": 0,
    "MISSING_SUPPORTED": 1,
    "UNRESOLVED_IDENTITY": 2,
    "INSUFFICIENT_EVIDENCE": 3,
    "UNSUPPORTED": 4,
    "CORRECT": 5,
}
SEVERITY_RANK: dict[str, int] = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}

# I1 has no real findings yet to calibrate case-by-case severity from, so each classification gets
# one fixed default severity (I1 §14 guidance). This is a default, not a hardcoded rule - I2/I3 MAY
# override severity per finding once real evidence exists.
DEFAULT_SEVERITY: dict[str, str] = {
    "CORRECT": "INFO",
    "MISSING_SUPPORTED": "MAJOR",
    "INCORRECT_SUPPORTED": "CRITICAL",
    "UNSUPPORTED": "INFO",
    "UNRESOLVED_IDENTITY": "MINOR",
    "INSUFFICIENT_EVIDENCE": "MINOR",
}

# The four relation types AIP's Canonical Model currently supports (CLAUDE.md's graph model table).
KNOWN_RELATION_TYPES = frozenset({"PROVIDES", "CALLS", "SENDS", "RECEIVES_FROM"})

_CANONICAL_ID_PREFIXES = tuple(
    f"{kind}:" for kind in ("service", "operation", "queue", "message", "schema")
)


def is_canonical_id(value: object) -> bool:
    return isinstance(value, str) and value.startswith(_CANONICAL_ID_PREFIXES)


class ExpectedValidationError(ValueError):
    """Invalid expected.yaml / actual-facts-capture configuration (I1 §43) - carries
    system/file/field/reason so the loader can produce a clear, locatable error rather than a bare
    exception message."""

    def __init__(self, *, system: str, file: str, field: str, reason: str) -> None:
        self.system = system
        self.file = file
        self.field = field
        self.reason = reason
        super().__init__(f"system={system} file={file} field={field}: {reason}")


@dataclass(frozen=True, order=True)
class RelationFact:
    """One canonical architecture relation fact (I1 §6.1/§17), used for both an expected fact
    (parsed from expected.yaml) and an actual fact (parsed from an AIP result capture)."""

    type: str
    source: str
    target: str
    status: str | None = None
    declared_evidence: bool | None = None
    observed_evidence: bool | None = None


@dataclass(frozen=True)
class ScopeDeclaration:
    """The dossier's declared supported comparison scope (I1 §11/§17 `scope:`). A fact is in scope
    when its source or target is a scoped entity, and - if relation_types is given - its type is
    one of them."""

    entities: tuple[str, ...]
    relation_types: tuple[str, ...] | None = None

    def contains(self, fact: RelationFact) -> bool:
        if self.relation_types is not None and fact.type not in self.relation_types:
            return False
        return fact.source in self.entities or fact.target in self.entities


@dataclass(frozen=True)
class ExpectedRelation:
    id: str
    fact: RelationFact


@dataclass(frozen=True)
class UnsupportedItem:
    """I1 §12.4/§17 `unsupported:` entry - a mechanism outside AIP's current supported scope."""

    id: str
    mechanism: str
    description: str


@dataclass(frozen=True)
class UnresolvedIdentityItem:
    """I1 §12.5 - independent evidence suggests a relationship, but AIP cannot resolve identity
    safely without guessing. Authored directly in expected.yaml, not derived by the comparator."""

    id: str
    description: str


@dataclass(frozen=True)
class InsufficientEvidenceItem:
    """I1 §12.6 - the dossier itself cannot establish the fact strongly enough to use as ground
    truth. Authored directly in expected.yaml, not derived by the comparator."""

    id: str
    description: str


@dataclass(frozen=True)
class ExpectedDocument:
    """One system's frozen expected.yaml (I1 §17)."""

    system: str
    upstream_revision: str
    scope: ScopeDeclaration
    expected_relations: tuple[ExpectedRelation, ...]
    unsupported: tuple[UnsupportedItem, ...] = field(default=())
    unresolved_identity: tuple[UnresolvedIdentityItem, ...] = field(default=())
    insufficient_evidence: tuple[InsufficientEvidenceItem, ...] = field(default=())


@dataclass(frozen=True)
class Finding:
    """One comparator output record (I1 §20)."""

    id: str
    classification: str
    severity: str
    expected: RelationFact | None
    actual: RelationFact | None
