"""Loads and strictly validates the two real-world validation inputs (I1 §17/§31):

- `expected.yaml`     - a system's frozen, independently authored ground truth.
- an actual-facts capture - a plain list of AIP canonical relation facts (I1 §31 "AIP Result
  Capture"), produced separately (e.g. from a live Neo4j query or an exported graph snapshot) and
  handed to this loader as data. This module never queries Neo4j itself (I1 §19: "The comparator
  SHALL NOT consume upstream source directly during comparison").

A malformed document is a configuration error (ExpectedValidationError), never a finding.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from real_world_validation.model import (
    KNOWN_RELATION_TYPES,
    ExpectedDocument,
    ExpectedRelation,
    ExpectedValidationError,
    InsufficientEvidenceItem,
    RelationFact,
    ScopeDeclaration,
    UnresolvedIdentityItem,
    UnsupportedItem,
    is_canonical_id,
)

_TOP_LEVEL_ALLOWED_KEYS = {
    "system",
    "upstream_revision",
    "scope",
    "expected",
    "unsupported",
    "unresolved_identity",
    "insufficient_evidence",
}
_SCOPE_ALLOWED_KEYS = {"entities", "relation_types"}
_EXPECTED_ALLOWED_KEYS = {"relations"}
_RELATION_ALLOWED_KEYS = {"id", "type", "source", "target", "status", "evidence"}
_EVIDENCE_ALLOWED_KEYS = {"declared", "observed"}
_UNSUPPORTED_ALLOWED_KEYS = {"id", "mechanism", "description"}
_ID_DESCRIPTION_ALLOWED_KEYS = {"id", "description"}
_KNOWN_STATUSES = {"CONFIRMED", "OBSERVED_ONLY", "NOT_OBSERVED_IN_WINDOW"}

_ACTUAL_TOP_LEVEL_ALLOWED_KEYS = {"relations"}
_ACTUAL_RELATION_ALLOWED_KEYS = {"type", "source", "target", "status", "evidence"}


def _error(system: str, file: Path, field: str, reason: str) -> ExpectedValidationError:
    return ExpectedValidationError(system=system, file=str(file), field=field, reason=reason)


def _reject_unknown_keys(
    data: dict, allowed: set[str], *, system: str, file: Path, field: str
) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise _error(system, file, field, f"unknown field(s): {', '.join(sorted(unknown))}")


def _require(data: dict, key: str, *, system: str, file: Path, prefix: str = "") -> Any:
    if not isinstance(data, dict) or key not in data or data[key] is None:
        raise _error(system, file, f"{prefix}{key}", "missing required field")
    return data[key]


def _require_mapping(value: Any, *, system: str, file: Path, field: str) -> dict:
    if not isinstance(value, dict):
        raise _error(system, file, field, f"expected a mapping, got {value!r}")
    return value


def _require_list(value: Any, *, system: str, file: Path, field: str) -> list:
    if not isinstance(value, list):
        raise _error(system, file, field, f"expected a list, got {value!r}")
    return value


def _optional_mapping(value: Any, *, system: str, file: Path, field: str) -> dict:
    if value is None:
        return {}
    return _require_mapping(value, system=system, file=file, field=field)


def _validate_entity_id(value: Any, *, system: str, file: Path, field: str) -> str:
    if not is_canonical_id(value):
        raise _error(system, file, field, f"malformed canonical identifier: {value!r}")
    return value


def _validate_relation_type(value: Any, *, system: str, file: Path, field: str) -> str:
    if not isinstance(value, str) or value not in KNOWN_RELATION_TYPES:
        raise _error(system, file, field, f"unknown relation type: {value!r}")
    return value


def _validate_status(value: Any, *, system: str, file: Path, field: str) -> str | None:
    if value is not None and (not isinstance(value, str) or value not in _KNOWN_STATUSES):
        raise _error(system, file, field, f"unknown status: {value!r}")
    return value


def _validate_evidence(evidence: dict, *, system: str, file: Path, field: str) -> dict:
    _reject_unknown_keys(evidence, _EVIDENCE_ALLOWED_KEYS, system=system, file=file, field=field)
    for key, value in evidence.items():
        if not isinstance(value, bool):
            raise _error(system, file, f"{field}.{key}", f"must be a boolean: {value!r}")
    return evidence


def _validate_id(value: Any, *, system: str, file: Path, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(system, file, field, f"must be a non-empty string: {value!r}")
    return value


def _parse_relation_fact(
    raw: Any, *, system: str, file: Path, field: str, allowed_keys: set[str]
) -> RelationFact:
    if not isinstance(raw, dict):
        raise _error(system, file, field, f"expected a mapping, got {raw!r}")
    _reject_unknown_keys(raw, allowed_keys, system=system, file=file, field=field)
    relation_type = _validate_relation_type(
        _require(raw, "type", system=system, file=file, prefix=f"{field}."),
        system=system,
        file=file,
        field=f"{field}.type",
    )
    source = _validate_entity_id(
        _require(raw, "source", system=system, file=file, prefix=f"{field}."),
        system=system,
        file=file,
        field=f"{field}.source",
    )
    target = _validate_entity_id(
        _require(raw, "target", system=system, file=file, prefix=f"{field}."),
        system=system,
        file=file,
        field=f"{field}.target",
    )
    evidence = _validate_evidence(
        _optional_mapping(raw.get("evidence"), system=system, file=file, field=f"{field}.evidence"),
        system=system,
        file=file,
        field=f"{field}.evidence",
    )
    status = _validate_status(raw.get("status"), system=system, file=file, field=f"{field}.status")
    return RelationFact(
        type=relation_type,
        source=source,
        target=target,
        status=status,
        declared_evidence=evidence.get("declared"),
        observed_evidence=evidence.get("observed"),
    )


def _parse_expected_relation(raw: Any, *, system: str, file: Path, field: str) -> ExpectedRelation:
    if not isinstance(raw, dict):
        raise _error(system, file, field, f"expected a mapping, got {raw!r}")
    finding_id = _validate_id(
        _require(raw, "id", system=system, file=file, prefix=f"{field}."),
        system=system,
        file=file,
        field=f"{field}.id",
    )
    fact = _parse_relation_fact(
        raw, system=system, file=file, field=field, allowed_keys=_RELATION_ALLOWED_KEYS
    )
    return ExpectedRelation(id=finding_id, fact=fact)


def _parse_unsupported_item(raw: Any, *, system: str, file: Path, field: str) -> UnsupportedItem:
    raw = _require_mapping(raw, system=system, file=file, field=field)
    _reject_unknown_keys(raw, _UNSUPPORTED_ALLOWED_KEYS, system=system, file=file, field=field)
    return UnsupportedItem(
        id=_validate_id(
            _require(raw, "id", system=system, file=file, prefix=f"{field}."),
            system=system,
            file=file,
            field=f"{field}.id",
        ),
        mechanism=_require(raw, "mechanism", system=system, file=file, prefix=f"{field}."),
        description=_require(raw, "description", system=system, file=file, prefix=f"{field}."),
    )


def _parse_id_description_item(raw: Any, cls: type, *, system: str, file: Path, field: str) -> Any:
    raw = _require_mapping(raw, system=system, file=file, field=field)
    _reject_unknown_keys(raw, _ID_DESCRIPTION_ALLOWED_KEYS, system=system, file=file, field=field)
    return cls(
        id=_validate_id(
            _require(raw, "id", system=system, file=file, prefix=f"{field}."),
            system=system,
            file=file,
            field=f"{field}.id",
        ),
        description=_require(raw, "description", system=system, file=file, prefix=f"{field}."),
    )


def load_expected(path: Path) -> ExpectedDocument:
    """Loads and validates one system's frozen expected.yaml (I1 §17)."""
    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _error("<unknown>", path, "<root>", f"expected a mapping, got {raw!r}")

    system = raw.get("system")
    if not system or not isinstance(system, str):
        raise _error("<unknown>", path, "system", "missing required field")

    _reject_unknown_keys(raw, _TOP_LEVEL_ALLOWED_KEYS, system=system, file=path, field="<root>")

    upstream_revision = _require(raw, "upstream_revision", system=system, file=path)
    if not isinstance(upstream_revision, str) or not upstream_revision:
        raise _error(system, path, "upstream_revision", "must be a non-empty string")

    scope_raw = _require_mapping(
        _require(raw, "scope", system=system, file=path), system=system, file=path, field="scope"
    )
    _reject_unknown_keys(scope_raw, _SCOPE_ALLOWED_KEYS, system=system, file=path, field="scope")
    entities_raw = _require_list(
        _require(scope_raw, "entities", system=system, file=path, prefix="scope."),
        system=system,
        file=path,
        field="scope.entities",
    )
    if not entities_raw:
        raise _error(system, path, "scope.entities", "must not be empty")
    entities = tuple(
        _validate_entity_id(e, system=system, file=path, field="scope.entities")
        for e in entities_raw
    )
    if len(set(entities)) != len(entities):
        raise _error(system, path, "scope.entities", "duplicate entities")

    relation_types_raw = scope_raw.get("relation_types")
    if relation_types_raw is not None:
        relation_types_raw = _require_list(
            relation_types_raw, system=system, file=path, field="scope.relation_types"
        )
        if not relation_types_raw:
            raise _error(system, path, "scope.relation_types", "must not be empty when present")
        relation_types = tuple(
            _validate_relation_type(rt, system=system, file=path, field="scope.relation_types")
            for rt in relation_types_raw
        )
        if len(set(relation_types)) != len(relation_types):
            raise _error(system, path, "scope.relation_types", "duplicate relation types")
    else:
        relation_types = None
    scope = ScopeDeclaration(entities=entities, relation_types=relation_types)

    expected_raw = _optional_mapping(
        raw.get("expected"), system=system, file=path, field="expected"
    )
    _reject_unknown_keys(
        expected_raw, _EXPECTED_ALLOWED_KEYS, system=system, file=path, field="expected"
    )
    relations_raw = _require_list(
        expected_raw.get("relations", []), system=system, file=path, field="expected.relations"
    )
    expected_relations = tuple(
        _parse_expected_relation(r, system=system, file=path, field="expected.relations")
        for r in relations_raw
    )

    unsupported_raw = raw.get("unsupported")
    unsupported = ()
    if unsupported_raw is not None:
        unsupported_raw = _require_list(
            unsupported_raw, system=system, file=path, field="unsupported"
        )
        unsupported = tuple(
            _parse_unsupported_item(u, system=system, file=path, field="unsupported")
            for u in unsupported_raw
        )

    unresolved_raw = raw.get("unresolved_identity")
    unresolved_identity = ()
    if unresolved_raw is not None:
        unresolved_raw = _require_list(
            unresolved_raw, system=system, file=path, field="unresolved_identity"
        )
        unresolved_identity = tuple(
            _parse_id_description_item(
                u,
                UnresolvedIdentityItem,
                system=system,
                file=path,
                field="unresolved_identity",
            )
            for u in unresolved_raw
        )

    insufficient_raw = raw.get("insufficient_evidence")
    insufficient_evidence = ()
    if insufficient_raw is not None:
        insufficient_raw = _require_list(
            insufficient_raw, system=system, file=path, field="insufficient_evidence"
        )
        insufficient_evidence = tuple(
            _parse_id_description_item(
                u,
                InsufficientEvidenceItem,
                system=system,
                file=path,
                field="insufficient_evidence",
            )
            for u in insufficient_raw
        )

    # I1 §18: finding ids must be unique across the whole dossier, not just within one section.
    all_ids = (
        [r.id for r in expected_relations]
        + [u.id for u in unsupported]
        + [u.id for u in unresolved_identity]
        + [u.id for u in insufficient_evidence]
    )
    seen: set[str] = set()
    for finding_id in all_ids:
        if finding_id in seen:
            raise _error(system, path, "<id>", f"duplicate finding id: {finding_id!r}")
        seen.add(finding_id)

    return ExpectedDocument(
        system=system,
        upstream_revision=upstream_revision,
        scope=scope,
        expected_relations=expected_relations,
        unsupported=unsupported,
        unresolved_identity=unresolved_identity,
        insufficient_evidence=insufficient_evidence,
    )


def load_actual(path: Path) -> list[RelationFact]:
    """Loads an AIP result capture (I1 §31): a plain list of canonical relation facts already
    produced elsewhere (e.g. exported from a live comparison run). No `id` field - actual graph
    facts have no dossier-authored finding id."""
    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raw = {}
    system = "<actual>"
    if not isinstance(raw, dict):
        raise _error(system, path, "<root>", f"expected a mapping, got {raw!r}")
    _reject_unknown_keys(
        raw, _ACTUAL_TOP_LEVEL_ALLOWED_KEYS, system=system, file=path, field="<root>"
    )
    relations_raw = _require_list(
        raw.get("relations", []), system=system, file=path, field="relations"
    )
    return [
        _parse_relation_fact(
            r,
            system=system,
            file=path,
            field="relations",
            allowed_keys=_ACTUAL_RELATION_ALLOWED_KEYS,
        )
        for r in relations_raw
    ]
