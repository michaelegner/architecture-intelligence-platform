"""v0.4.2 I2 - the normative EMPTY/COMPLETE/PARTIAL_OR_INCOMPATIBLE fixture-state classifier (spec
`docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md` Part II §15).

Runs read-only, inside the already-running `architecture-intelligence` container, against the
checked-in oracle at `examples/runtime-demo/fixture-state.json`:

    "${COMPOSE[@]}" exec -T architecture-intelligence python \\
        examples/runtime-demo/check_fixture_state.py --json

It deliberately reuses this repository's own production read/business logic instead of a second,
competing implementation of "what a correct demo graph looks like":

- `app.architecture_intelligence.repository.canonical_snapshot_state`/`snapshot_fingerprint` - the
  exact functions that compute the `snapshot_id` every MCP answer already carries, so
  `expected_snapshot_id` in the manifest is the real production fingerprint, not a parallel hash;
- `app.architecture_intelligence.canonical_json.canonical_json_bytes` - the same canonicalization
  used to freeze the manifest, so a live read and the checked-in manifest normalize identically
  (UTC timestamps, sorted keys, deduplicated set-valued fields) before comparison;
- `app.architecture_intelligence.service.ArchitectureIntelligenceService.get_architecture_drift` -
  the real drift capability, so `expected_drift_claims` is checked against AIP's actual qualification
  output rather than a hand-maintained guess at what it should say (spec §52: "no new correctness
  oracle").

`classify()` itself is a pure function over plain dicts (manifest, live canonical state, live drift
claims) with no Neo4j dependency, so it is unit-testable without a database; `main()` is the only
part of this file that touches Neo4j, and it opens a single `READ_ACCESS` session and performs zero
writes (spec §15.3: "The checker MUST perform zero graph writes").
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Invoked as `python examples/runtime-demo/check_fixture_state.py`, which puts only this file's own
# directory on sys.path - unlike `uvicorn app.main:app`'s module-name invocation, which relies on
# the container's cwd (/app, per the Dockerfile's WORKDIR) already being on sys.path. Put the repo
# root back on sys.path explicitly so the `app.*` imports below resolve regardless of invocation style.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Outcome
from app.architecture_intelligence.repository import (
    canonical_snapshot_state,
    snapshot_fingerprint,
)
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    ObservationContextInput,
)
from app.graph.repository import build_driver, open_session
from app.graph.revision_fence import RevisionSingletonMissing, read_revision
from app.mcp.wiring import build_production_service
from app.settings import load_settings

_MANIFEST_PATH = Path(__file__).resolve().parent / "fixture-state.json"
_CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.yaml"))

_MAX_DETAIL_LENGTH = 500

# Stable machine-readable mismatch codes (spec §15.3).
_NODE_COUNT_MISMATCH = "NODE_COUNT_MISMATCH"
_RELATIONSHIP_COUNT_MISMATCH = "RELATIONSHIP_COUNT_MISMATCH"
_UNEXPECTED_GRAPH_DATA = "UNEXPECTED_GRAPH_DATA"
_DECLARED_RELATION_MISMATCH = "DECLARED_RELATION_MISMATCH"
_OBSERVED_RELATION_MISMATCH = "OBSERVED_RELATION_MISMATCH"
_EVIDENCE_MISMATCH = "EVIDENCE_MISMATCH"
_OBSERVATION_COUNT_MISMATCH = "OBSERVATION_COUNT_MISMATCH"
_FIRST_SEEN_MISMATCH = "FIRST_SEEN_MISMATCH"
_LAST_SEEN_MISMATCH = "LAST_SEEN_MISMATCH"
_TRACE_SAMPLE_MISMATCH = "TRACE_SAMPLE_MISMATCH"
_DRIFT_CLAIM_MISMATCH = "DRIFT_CLAIM_MISMATCH"
_SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
_UNSTABLE_DATABASE_STATE = "UNSTABLE_DATABASE_STATE"
_MISSING_REVISION_SINGLETON = "MISSING_REVISION_SINGLETON"

_MAX_CONSISTENCY_ATTEMPTS = 5

_EVIDENCE_FIELD_CODES = (
    ("observation_count", _OBSERVATION_COUNT_MISMATCH),
    ("first_seen", _FIRST_SEEN_MISMATCH),
    ("last_seen", _LAST_SEEN_MISMATCH),
    ("sample_trace_ids", _TRACE_SAMPLE_MISMATCH),
)


def _mismatch(code: str, detail: str) -> dict[str, str]:
    return {"code": code, "detail": detail[:_MAX_DETAIL_LENGTH]}


def _relation_key(relation: dict[str, Any]) -> tuple[str, str, str]:
    return (relation["type"], relation["source_id"], relation["target_id"])


def _relation_bucket(relation: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    """Whether a relation's own evidence is DECLARED, OBSERVED, both, or unresolvable - used only
    to pick a diagnostic mismatch code, never to decide EMPTY/COMPLETE/PARTIAL_OR_INCOMPATIBLE
    itself (that decision is the plain equality checks below)."""
    types = {
        evidence_by_id[eid]["evidence_type"]
        for eid in relation.get("evidence_ids", [])
        if eid in evidence_by_id
    }
    if types == {"DECLARED"}:
        return _DECLARED_RELATION_MISMATCH
    if types == {"OBSERVED"}:
        return _OBSERVED_RELATION_MISMATCH
    return _UNEXPECTED_GRAPH_DATA


def _diff_evidence(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> list[dict[str, str]]:
    expected_by_id = {e["id"]: e for e in expected}
    actual_by_id = {e["id"]: e for e in actual}
    mismatches: list[dict[str, str]] = []
    for eid in sorted(set(expected_by_id) | set(actual_by_id)):
        exp = expected_by_id.get(eid)
        act = actual_by_id.get(eid)
        if exp == act:
            continue
        if exp is None or act is None:
            mismatches.append(
                _mismatch(
                    _EVIDENCE_MISMATCH,
                    f"evidence {eid} {'unexpected' if exp is None else 'missing'}",
                )
            )
            continue
        field_mismatch_found = False
        for field, code in _EVIDENCE_FIELD_CODES:
            if exp.get(field) != act.get(field):
                field_mismatch_found = True
                mismatches.append(
                    _mismatch(code, f"evidence {eid} {field} differs from the manifest")
                )
        if not field_mismatch_found:
            mismatches.append(
                _mismatch(_EVIDENCE_MISMATCH, f"evidence {eid} differs from the manifest")
            )
    return mismatches


def classify(
    manifest: dict[str, Any],
    actual_state: dict[str, Any],
    actual_drift_claims: list[dict[str, Any]],
    *,
    whole_database_node_count: int,
    whole_database_relationship_count: int,
) -> dict[str, Any]:
    """Pure classification (no Neo4j access) - spec §15.2/§15.3's EMPTY/COMPLETE/
    PARTIAL_OR_INCOMPATIBLE oracle over one already-read canonical state.

    `whole_database_node_count`/`whole_database_relationship_count` MUST be a true `MATCH (n)`/
    `MATCH ()-[r]->()` count of the *entire* target database, not a sum over `actual_state`'s
    allowlisted node categories: `actual_state` (from `canonical_snapshot_state`) deliberately
    excludes non-architectural infrastructure nodes such as `(:AipInternalState)` (spec §19), so a
    stray node under a label `canonical_snapshot_state` doesn't project - or, before the revision
    singleton exists, its own presence - would otherwise be invisible to this check. Spec §15.2 is
    explicit that EMPTY/COMPLETE's node and relationship counts are whole-database counts, not
    canonical-model-scoped ones: "Any unrelated node or relationship therefore prevents EMPTY."
    """
    if whole_database_node_count == 0 and whole_database_relationship_count == 0:
        return {
            "classification": "EMPTY",
            "expected_snapshot_id": manifest["expected_snapshot_id"],
            "actual_snapshot_id": None,
            "mismatches": [],
        }

    actual_snapshot_id, _ = snapshot_fingerprint(actual_state)
    actual_json = json.loads(canonical_json_bytes(actual_state))
    expected_json = manifest["canonical_state"]

    mismatches: list[dict[str, str]] = []

    if whole_database_node_count != manifest["total_node_count"]:
        mismatches.append(
            _mismatch(
                _NODE_COUNT_MISMATCH,
                f"expected {manifest['total_node_count']} nodes, found {whole_database_node_count}",
            )
        )
    if whole_database_relationship_count != manifest["total_relationship_count"]:
        mismatches.append(
            _mismatch(
                _RELATIONSHIP_COUNT_MISMATCH,
                f"expected {manifest['total_relationship_count']} relationships, "
                f"found {whole_database_relationship_count}",
            )
        )

    for key in ("services", "operations", "queues", "messages", "schemas"):
        if actual_json[key] != expected_json[key]:
            mismatches.append(
                _mismatch(_UNEXPECTED_GRAPH_DATA, f"{key} set differs from the frozen manifest")
            )

    evidence_by_id = {e["id"]: e for e in expected_json["evidence"]}
    if actual_json["relations"] != expected_json["relations"]:
        expected_by_key = {_relation_key(r): r for r in expected_json["relations"]}
        actual_by_key = {_relation_key(r): r for r in actual_json["relations"]}
        for key in sorted(set(expected_by_key) | set(actual_by_key)):
            exp_rel = expected_by_key.get(key)
            act_rel = actual_by_key.get(key)
            if exp_rel == act_rel:
                continue
            reference = exp_rel if exp_rel is not None else act_rel
            code = _relation_bucket(reference, evidence_by_id)
            mismatches.append(
                _mismatch(
                    code,
                    f"relation {key} {'missing' if act_rel is None else 'unexpected or changed'}",
                )
            )

    if actual_json["evidence"] != expected_json["evidence"]:
        mismatches.extend(_diff_evidence(expected_json["evidence"], actual_json["evidence"]))

    expected_drift_claims = manifest["expected_drift_claims"]
    if actual_drift_claims != expected_drift_claims:
        mismatches.append(
            _mismatch(_DRIFT_CLAIM_MISMATCH, "expected drift claim set differs from the manifest")
        )

    if actual_snapshot_id != manifest["expected_snapshot_id"] and not mismatches:
        # Every field-level check above passed but the fingerprint still differs - defensive
        # fallback for a canonicalization-version or semantic_config difference the per-field
        # checks don't otherwise explain.
        mismatches.append(
            _mismatch(
                _SNAPSHOT_MISMATCH,
                f"expected {manifest['expected_snapshot_id']}, got {actual_snapshot_id}",
            )
        )

    classification = "COMPLETE" if not mismatches else "PARTIAL_OR_INCOMPATIBLE"
    return {
        "classification": classification,
        "expected_snapshot_id": manifest["expected_snapshot_id"],
        "actual_snapshot_id": actual_snapshot_id,
        "mismatches": mismatches,
    }


def project_drift_claims(answer) -> list[dict[str, Any]]:
    """Normalizes `ArchitectureIntelligenceService.get_architecture_drift`'s answer into the same
    plain-dict shape the manifest's `expected_drift_claims` is frozen in, sorted deterministically
    so classification never depends on incidental claim ordering."""
    if answer.outcome == Outcome.NOT_ANSWERED:
        return []
    claims = [
        {
            "subject": claim.subject.id,
            "target": claim.object.name,
            "via": claim.delivery.via.name,
            "qualification": claim.qualification.value,
            "evidence_refs": sorted(claim.evidence_refs),
        }
        for claim in answer.claims
    ]
    return sorted(claims, key=lambda c: (c["target"], c["qualification"]))


def _load_manifest() -> dict[str, Any]:
    return json.loads(_MANIFEST_PATH.read_text())


_TOTAL_NODE_COUNT_QUERY = "MATCH (n) RETURN count(n) AS count"
_TOTAL_RELATIONSHIP_COUNT_QUERY = "MATCH ()-[r]->() RETURN count(r) AS count"


def _read_actual_state(driver, *, database: str, coverage_qualification_enabled: bool) -> dict:
    with open_session(driver, database=database, read_only=True) as session:
        return canonical_snapshot_state(
            session, coverage_qualification_enabled=coverage_qualification_enabled
        )


def _read_whole_database_counts(driver, *, database: str) -> tuple[int, int]:
    """A true whole-database node/relationship count - see `classify`'s docstring for why this
    must not be derived from `canonical_snapshot_state`'s allowlisted categories."""
    with open_session(driver, database=database, read_only=True) as session:
        node_count = session.run(_TOTAL_NODE_COUNT_QUERY).single()["count"]
        relationship_count = session.run(_TOTAL_RELATIONSHIP_COUNT_QUERY).single()["count"]
    return node_count, relationship_count


def _read_actual_drift_claims(
    driver, *, database: str, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    service = build_production_service(driver, database=database)
    answer = service.get_architecture_drift(
        ArchitectureDriftRequest(
            service_id=manifest["service_id"],
            observation_context=ObservationContextInput(
                environment=manifest["environment"],
                window_start=manifest["window_start"],
                window_end=manifest["window_end"],
            ),
        )
    )
    return project_drift_claims(answer)


class FixtureStateUnstable(RuntimeError):
    """Raised when the composite read below (whole-database counts, canonical state, and drift
    claims) couldn't observe one consistent committed database revision after
    `_MAX_CONSISTENCY_ATTEMPTS` tries. Mirrors `app.architecture_intelligence.repository.
    SnapshotUnstable`'s bounded discard-and-retry idiom (spec §19.1's stable-read algorithm),
    extended to also cover this checker's own extra whole-database count queries and its separate
    `get_architecture_drift` call - not just `canonical_snapshot_state` alone."""


def _read_revision_or_none(session) -> int | None:
    """`None` means "no `(:AipInternalState)` singleton yet" - a legitimate state for a virgin/
    EMPTY database (spec §15.2), not a fencing failure."""
    try:
        return read_revision(session)
    except RevisionSingletonMissing:
        return None


def _read_consistent_fixture_data(
    driver, *, database: str, coverage_qualification_enabled: bool, manifest: dict[str, Any]
) -> tuple[int, int, dict, list[dict[str, Any]]]:
    """Reads whole-database counts, canonical state, and (when non-empty) drift claims as one
    logically consistent snapshot, fenced by `(:AipInternalState).revision`: a write landing
    anywhere between the first and last revision read below discards the whole bundle and retries,
    rather than letting the checker silently combine pre- and post-write data into one
    classification (spec §15's checker is a normative oracle - it must never observe a state that
    never actually existed as one committed revision)."""
    for _ in range(_MAX_CONSISTENCY_ATTEMPTS):
        with open_session(driver, database=database, read_only=True) as session:
            revision_before = _read_revision_or_none(session)
            node_count = session.run(_TOTAL_NODE_COUNT_QUERY).single()["count"]
            relationship_count = session.run(_TOTAL_RELATIONSHIP_COUNT_QUERY).single()["count"]
            state = canonical_snapshot_state(
                session, coverage_qualification_enabled=coverage_qualification_enabled
            )
            revision_after_state = _read_revision_or_none(session)

        if revision_before != revision_after_state:
            continue  # mutated mid-read - discard everything and retry

        if node_count == 0 and relationship_count == 0:
            return node_count, relationship_count, state, []

        if revision_before is None:
            # Non-empty graph with no trustworthy (:AipInternalState) revision (missing entirely,
            # or an invalid value read_revision() itself rejects) - e.g. a lone unrelated node in
            # an otherwise-untouched database, which I2 §45 requires to classify as
            # PARTIAL_OR_INCOMPATIBLE. get_architecture_drift's own stable-read requires the
            # singleton and would raise RevisionSingletonMissing uncaught, so never call it here.
            raise RevisionSingletonMissing(
                "database contains graph data but no valid (:AipInternalState) revision singleton"
            )

        # get_architecture_drift performs its own separate stable read internally, so the only
        # remaining race is a write landing between the bracket above and this call - re-check the
        # fence once more after it returns.
        drift_claims = _read_actual_drift_claims(driver, database=database, manifest=manifest)

        with open_session(driver, database=database, read_only=True) as session:
            revision_final = _read_revision_or_none(session)

        if revision_final != revision_before:
            continue  # mutated between the state/count read and the drift-claims read - retry

        return node_count, relationship_count, state, drift_claims

    raise FixtureStateUnstable(
        f"no consistent database revision observed after {_MAX_CONSISTENCY_ATTEMPTS} attempts"
    )


def classify_fixture(
    manifest: dict[str, Any],
    driver,
    *,
    database: str,
    coverage_qualification_enabled: bool,
) -> dict[str, Any]:
    """The Neo4j-backed half of this tool, factored out from `run()` so integration tests can drive
    it directly against a real (e.g. testcontainers) driver without going through `load_settings`'s
    environment-variable contract. Opens no write transaction (spec §15.3)."""
    try:
        node_count, relationship_count, actual_state, actual_drift_claims = (
            _read_consistent_fixture_data(
                driver,
                database=database,
                coverage_qualification_enabled=coverage_qualification_enabled,
                manifest=manifest,
            )
        )
    except FixtureStateUnstable as exc:
        return {
            "fixture_id": manifest["fixture_id"],
            "classification": "PARTIAL_OR_INCOMPATIBLE",
            "expected_snapshot_id": manifest.get("expected_snapshot_id"),
            "actual_snapshot_id": None,
            "mismatches": [_mismatch(_UNSTABLE_DATABASE_STATE, str(exc))],
        }
    except RevisionSingletonMissing as exc:
        return {
            "fixture_id": manifest["fixture_id"],
            "classification": "PARTIAL_OR_INCOMPATIBLE",
            "expected_snapshot_id": manifest.get("expected_snapshot_id"),
            "actual_snapshot_id": None,
            "mismatches": [_mismatch(_MISSING_REVISION_SINGLETON, str(exc))],
        }

    result = classify(
        manifest,
        actual_state,
        actual_drift_claims,
        whole_database_node_count=node_count,
        whole_database_relationship_count=relationship_count,
    )
    return {"fixture_id": manifest["fixture_id"], **result}


def run(manifest: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings(_CONFIG_PATH)
    driver = build_driver(
        settings.config.graph.uri, settings.secrets.neo4j_user, settings.secrets.neo4j_password
    )
    try:
        return classify_fixture(
            manifest,
            driver,
            database=settings.config.graph.database,
            coverage_qualification_enabled=(
                settings.config.telemetry.coverage.qualification_enabled
            ),
        )
    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        required=True,
        help="Emit the classification as JSON to stdout (currently the only supported output mode).",
    )
    parser.parse_args(argv)

    manifest = _load_manifest()
    result = run(manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
