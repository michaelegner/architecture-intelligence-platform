"""AIP v0.4.1 I1.3 - the real-Neo4j differential qualification test
(docs/specifications/0.4.1/i1-qualification-consistency.md §17-§22, §29, §33).

Exercises the real production entry points on both existing qualification paths -
`app.analysis.runtime.service_runtime_profile` (the Cypher/analysis path) and
`app.architecture_intelligence.service.ArchitectureIntelligenceService.get_service_dependencies`
(the Python/MCP path) - against one shared, hand-built graph fixture covering the Q1-Q15 boundary
matrix from spec §19/§33, and proves both agree with each other *and* with hand-authored expected
values (agreement alone isn't sufficient - both paths could independently be wrong the same way).

Two deliberate fixture decisions, made explicit here rather than left implicit:

1. The fixture contains no `PROVIDES` edges at all. Path A's CALLS `target_id` is already
   provider-resolved (`coalesce(provider.id, o.id)`, app/analysis/runtime.py's
   `_CALLS_TARGET_ID_EXPR`), while path B's `delivery.via.id` is always the raw Operation id.
   Without any `PROVIDES` edge, `coalesce(provider.id, o.id)` trivially reduces to `o.id`, so the
   two paths' target identities agree by construction - no re-derivation logic needed in this test.
   Destination resolution is explicitly outside the shared kernel's scope (spec §16) and is covered
   elsewhere (tests/integration/test_architecture_intelligence_service.py).
2. Q3/Q4/Q8's coverage-driver relations are first-class fixture entries with their own expected
   qualification, not incidental scaffolding - each is itself qualified by both paths and produces
   its own comparison key. Drivers are always outgoing CALLS/SENDS on the *same* subject service as
   their case (never RECEIVES_FROM: `dependency_projection.project_service_dependencies` never
   qualifies RECEIVES_FROM as a claim, so a RECEIVES_FROM driver would appear only in path A's
   output - an artificial mismatch, not a real one).

This fixture is hand-built via direct Cypher, not `app.graph.importer.import_all_sources` (which
would introduce `PROVIDES` edges from the `examples/` reference landscape) - so it must explicitly
run `app.graph.schema.ensure_schema` itself; the normal import pipeline does this as part of its own
schema initialization, but nothing does it automatically for a from-scratch hand-built graph. Without
it, `ArchitectureIntelligenceService`'s stable-snapshot read raises `RevisionSingletonMissing`
(app/graph/revision_fence.py) - there is no `(:AipInternalState)` singleton yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.runtime import service_runtime_profile
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.request import (
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from app.qualification.declared_observed import (
    CONFIRMED,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    COVERAGE_SUFFICIENT,
    NOT_OBSERVED_IN_WINDOW,
    OBSERVED_ONLY,
)

DATABASE = "neo4j"
ENVIRONMENT = "qualification-test"
OTHER_ENVIRONMENT = "qualification-test-other"
WINDOW_START = datetime(2026, 9, 1, tzinfo=UTC)
WINDOW_END = datetime(2026, 9, 2, tzinfo=UTC)
INSIDE_WINDOW = WINDOW_START + timedelta(hours=12)

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.1", build_revision="e" * 40
)


@dataclass(frozen=True)
class _Evidence:
    id: str
    evidence_type: str  # "DECLARED" | "OBSERVED"
    environment: str | None = None
    last_seen: datetime | None = None


@dataclass(frozen=True)
class _Relation:
    """One CALLS/SENDS relation in the fixture, with its expected (qualification, coverage) per
    spec §33's Q1-Q15 table (or the coverage-driver rationale in the module docstring above).
    `expected` is `None` for the "no supported claim" cases (Q14/Q15) - both paths must omit this
    relation's comparison key entirely, not merely disagree about its qualification."""

    case: str
    subject_id: str
    subject_name: str
    relation_type: str  # "CALLS" | "SENDS"
    target_id: str
    target_name: str
    evidence: tuple[_Evidence, ...]
    expected: tuple[str, str | None] | None


_RELATIONS: tuple[_Relation, ...] = (
    # Q1 - CALLS declared + observed -> CONFIRMED.
    _Relation(
        "Q1",
        "service:q1",
        "q1",
        "CALLS",
        "operation:q1",
        "q1",
        (
            _Evidence("evidence:q1-declared", "DECLARED"),
            _Evidence("evidence:q1-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),
        ),
        (CONFIRMED, None),
    ),
    # Q2 - CALLS observed only -> OBSERVED_ONLY.
    _Relation(
        "Q2",
        "service:q2",
        "q2",
        "CALLS",
        "operation:q2",
        "q2",
        (_Evidence("evidence:q2-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),),
        (OBSERVED_ONLY, None),
    ),
    # Q3 - CALLS declared-only, with an HTTP coverage driver on the same subject -> SUFFICIENT.
    _Relation(
        "Q3",
        "service:q3",
        "q3",
        "CALLS",
        "operation:q3-target",
        "q3-target",
        (_Evidence("evidence:q3-declared", "DECLARED"),),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_SUFFICIENT),
    ),
    _Relation(
        "Q3-driver",
        "service:q3",
        "q3",
        "CALLS",
        "operation:q3-driver",
        "q3-driver",
        (_Evidence("evidence:q3-driver-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),),
        (OBSERVED_ONLY, None),
    ),
    # Q4 - CALLS declared-only, with only a messaging (SENDS) driver on the same subject ->
    # PARTIAL (relevant CALLS signal is http_observed, which stays False here).
    _Relation(
        "Q4",
        "service:q4",
        "q4",
        "CALLS",
        "operation:q4-target",
        "q4-target",
        (_Evidence("evidence:q4-declared", "DECLARED"),),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_PARTIAL),
    ),
    _Relation(
        "Q4-driver",
        "service:q4",
        "q4",
        "SENDS",
        "queue:q4-driver",
        "q4-driver",
        (_Evidence("evidence:q4-driver-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),),
        (OBSERVED_ONLY, None),
    ),
    # Q5 - CALLS declared-only, no other telemetry for the subject at all -> NONE.
    _Relation(
        "Q5",
        "service:q5",
        "q5",
        "CALLS",
        "operation:q5",
        "q5",
        (_Evidence("evidence:q5-declared", "DECLARED"),),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_NONE),
    ),
    # Q6 - SENDS declared + observed -> CONFIRMED.
    _Relation(
        "Q6",
        "service:q6",
        "q6",
        "SENDS",
        "queue:q6",
        "q6",
        (
            _Evidence("evidence:q6-declared", "DECLARED"),
            _Evidence("evidence:q6-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),
        ),
        (CONFIRMED, None),
    ),
    # Q7 - SENDS observed only -> OBSERVED_ONLY.
    _Relation(
        "Q7",
        "service:q7",
        "q7",
        "SENDS",
        "queue:q7",
        "q7",
        (_Evidence("evidence:q7-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),),
        (OBSERVED_ONLY, None),
    ),
    # Q8 - SENDS declared-only, with a messaging coverage driver on the same subject -> SUFFICIENT.
    _Relation(
        "Q8",
        "service:q8",
        "q8",
        "SENDS",
        "queue:q8-target",
        "q8-target",
        (_Evidence("evidence:q8-declared", "DECLARED"),),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_SUFFICIENT),
    ),
    _Relation(
        "Q8-driver",
        "service:q8",
        "q8",
        "SENDS",
        "queue:q8-driver",
        "q8-driver",
        (_Evidence("evidence:q8-driver-observed", "OBSERVED", ENVIRONMENT, INSIDE_WINDOW),),
        (OBSERVED_ONLY, None),
    ),
    # Q9 - declared + observed, but the observed evidence is in a different environment -> NONE
    # (no coverage driver on this subject; coverage is judged from the *selected* environment).
    _Relation(
        "Q9",
        "service:q9",
        "q9",
        "CALLS",
        "operation:q9",
        "q9",
        (
            _Evidence("evidence:q9-declared", "DECLARED"),
            _Evidence("evidence:q9-wrong-env", "OBSERVED", OTHER_ENVIRONMENT, INSIDE_WINDOW),
        ),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_NONE),
    ),
    # Q10 - observed evidence exists but its last_seen is before window_start -> excluded -> NONE.
    _Relation(
        "Q10",
        "service:q10",
        "q10",
        "CALLS",
        "operation:q10",
        "q10",
        (
            _Evidence("evidence:q10-declared", "DECLARED"),
            _Evidence(
                "evidence:q10-early", "OBSERVED", ENVIRONMENT, WINDOW_START - timedelta(seconds=1)
            ),
        ),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_NONE),
    ),
    # Q11 - observed evidence's last_seen is exactly window_start (inclusive lower bound) -> CONFIRMED.
    _Relation(
        "Q11",
        "service:q11",
        "q11",
        "CALLS",
        "operation:q11",
        "q11",
        (
            _Evidence("evidence:q11-declared", "DECLARED"),
            _Evidence("evidence:q11-exact-start", "OBSERVED", ENVIRONMENT, WINDOW_START),
        ),
        (CONFIRMED, None),
    ),
    # Q12 - observed evidence's last_seen is exactly window_end (inclusive upper bound) -> CONFIRMED.
    _Relation(
        "Q12",
        "service:q12",
        "q12",
        "CALLS",
        "operation:q12",
        "q12",
        (
            _Evidence("evidence:q12-declared", "DECLARED"),
            _Evidence("evidence:q12-exact-end", "OBSERVED", ENVIRONMENT, WINDOW_END),
        ),
        (CONFIRMED, None),
    ),
    # Q13 - observed evidence's last_seen is after window_end -> excluded -> NONE.
    _Relation(
        "Q13",
        "service:q13",
        "q13",
        "CALLS",
        "operation:q13",
        "q13",
        (
            _Evidence("evidence:q13-declared", "DECLARED"),
            _Evidence(
                "evidence:q13-late", "OBSERVED", ENVIRONMENT, WINDOW_END + timedelta(seconds=1)
            ),
        ),
        (NOT_OBSERVED_IN_WINDOW, COVERAGE_NONE),
    ),
    # Q14 - the relation's evidence_ids references an id with no Evidence node at all (dangling) ->
    # no supported claim. The dangling id is deliberately never created as a node - see _seed().
    _Relation("Q14", "service:q14", "q14", "CALLS", "operation:q14", "q14", (), None),
    # Q15 - the relation has no evidence references at all -> no supported claim.
    _Relation("Q15", "service:q15", "q15", "SENDS", "queue:q15", "q15", (), None),
)

_Q14_DANGLING_EVIDENCE_ID = "evidence:q14-dangling"

_CREATE_SERVICE = "CREATE (:Service {id: $id, name: $name})"
_CREATE_OPERATION = "CREATE (:Operation {id: $id, name: $name, method: 'GET', path: $path})"
_CREATE_QUEUE = "CREATE (:Queue {id: $id, name: $name})"
_CREATE_DECLARED_EVIDENCE = "CREATE (:Evidence {id: $id, evidence_type: 'DECLARED'})"
_CREATE_OBSERVED_EVIDENCE = (
    "CREATE (:Evidence {id: $id, evidence_type: 'OBSERVED', "
    "environment: $environment, last_seen: $last_seen})"
)
_CREATE_CALLS = (
    "MATCH (a:Service {id: $subject_id}), (o:Operation {id: $target_id}) "
    "CREATE (a)-[:CALLS {evidence_ids: $evidence_ids}]->(o)"
)
_CREATE_SENDS = (
    "MATCH (a:Service {id: $subject_id}), (q:Queue {id: $target_id}) "
    "CREATE (a)-[:SENDS {evidence_ids: $evidence_ids}]->(q)"
)


def _seed(session) -> None:
    ensure_schema(session)

    seen_subjects: set[str] = set()
    seen_operations: set[str] = set()
    seen_queues: set[str] = set()

    for relation in _RELATIONS:
        if relation.subject_id not in seen_subjects:
            session.run(_CREATE_SERVICE, id=relation.subject_id, name=relation.subject_name)
            seen_subjects.add(relation.subject_id)

        if relation.relation_type == "CALLS" and relation.target_id not in seen_operations:
            session.run(
                _CREATE_OPERATION,
                id=relation.target_id,
                name=relation.target_name,
                path=f"/{relation.target_name}",
            )
            seen_operations.add(relation.target_id)
        elif relation.relation_type == "SENDS" and relation.target_id not in seen_queues:
            session.run(_CREATE_QUEUE, id=relation.target_id, name=relation.target_name)
            seen_queues.add(relation.target_id)

        for evidence in relation.evidence:
            query = (
                _CREATE_DECLARED_EVIDENCE
                if evidence.evidence_type == "DECLARED"
                else _CREATE_OBSERVED_EVIDENCE
            )
            session.run(
                query,
                id=evidence.id,
                environment=evidence.environment,
                last_seen=evidence.last_seen,
            )

        evidence_ids = [evidence.id for evidence in relation.evidence]
        if relation.case == "Q14":
            evidence_ids = [_Q14_DANGLING_EVIDENCE_ID]  # never created as an Evidence node

        query = _CREATE_CALLS if relation.relation_type == "CALLS" else _CREATE_SENDS
        session.run(
            query,
            subject_id=relation.subject_id,
            target_id=relation.target_id,
            evidence_ids=evidence_ids,
        )


def _expected_map() -> dict[tuple[str, str, str], tuple[str, str | None]]:
    return {
        (r.subject_id, r.relation_type, r.target_id): r.expected
        for r in _RELATIONS
        if r.expected is not None
    }


def _excluded_keys() -> set[tuple[str, str, str]]:
    return {(r.subject_id, r.relation_type, r.target_id) for r in _RELATIONS if r.expected is None}


def _collect_path_a(
    session, subject_ids: list[str]
) -> dict[tuple[str, str, str], tuple[str, str | None]]:
    result: dict[tuple[str, str, str], tuple[str, str | None]] = {}
    for subject_id in subject_ids:
        profile = service_runtime_profile(
            session,
            service_id=subject_id,
            environment=ENVIRONMENT,
            since=WINDOW_START,
            until=WINDOW_END,
            qualification_enabled=True,
        )
        assert profile is not None, f"expected {subject_id} to exist in the fixture"
        for relation in profile.relations:
            key = (subject_id, relation.relation_type, relation.target_id)
            result[key] = (relation.status, relation.coverage)
    return result


def _collect_path_b(
    driver, subject_ids: list[str]
) -> dict[tuple[str, str, str], tuple[str, str | None]]:
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    result: dict[tuple[str, str, str], tuple[str, str | None]] = {}
    for subject_id in subject_ids:
        request = ServiceDependenciesRequest(
            service_id=subject_id,
            observation_context=ObservationContextInput(
                environment=ENVIRONMENT, window_start=WINDOW_START, window_end=WINDOW_END
            ),
        )
        answer = service.get_service_dependencies(request)
        for claim in answer.claims:
            key = (claim.subject.id, claim.delivery.relation_type.value, claim.delivery.via.id)
            result[key] = (
                claim.qualification.value,
                claim.coverage.value if claim.coverage is not None else None,
            )
    return result


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def test_qualification_consistency_across_analysis_and_architecture_intelligence_paths(driver):
    """Spec §17-§22/§33/§38: for every relation in the Q1-Q15 fixture, the analysis/Cypher path and
    the Architecture Intelligence/MCP path SHALL agree on qualification and coverage, and both
    SHALL match the hand-authored expected value. Reports every mismatch at once rather than
    failing on the first, per spec §38's required completion statement (qualification mismatches =
    N, coverage mismatches = N)."""
    with driver.session(database=DATABASE) as session:
        _seed(session)

    subject_ids = sorted({r.subject_id for r in _RELATIONS})

    with driver.session(database=DATABASE) as session:
        path_a = _collect_path_a(session, subject_ids)
    path_b = _collect_path_b(driver, subject_ids)

    expected = _expected_map()
    excluded = _excluded_keys()

    leaked_a = sorted(k for k in path_a if k in excluded)
    leaked_b = sorted(k for k in path_b if k in excluded)
    assert not leaked_a, f"path A (analysis) reported an excluded relation: {leaked_a}"
    assert not leaked_b, (
        f"path B (Architecture Intelligence) reported an excluded relation: {leaked_b}"
    )

    only_in_a = sorted(set(path_a) - set(path_b))
    only_in_b = sorted(set(path_b) - set(path_a))
    assert not only_in_a, f"relations only reported by path A (analysis): {only_in_a}"
    assert not only_in_b, (
        f"relations only reported by path B (Architecture Intelligence): {only_in_b}"
    )

    qualification_mismatches = []
    coverage_mismatches = []
    for key in sorted(set(path_a) & set(path_b)):
        a_qualification, a_coverage = path_a[key]
        b_qualification, b_coverage = path_b[key]
        exp_qualification, exp_coverage = expected[key]
        if not (a_qualification == b_qualification == exp_qualification):
            qualification_mismatches.append(
                {
                    "key": key,
                    "expected": exp_qualification,
                    "path_a": a_qualification,
                    "path_b": b_qualification,
                }
            )
        if not (a_coverage == b_coverage == exp_coverage):
            coverage_mismatches.append(
                {
                    "key": key,
                    "expected": exp_coverage,
                    "path_a": a_coverage,
                    "path_b": b_coverage,
                }
            )

    assert not qualification_mismatches, (
        f"qualification mismatches = {len(qualification_mismatches)}: {qualification_mismatches}"
    )
    assert not coverage_mismatches, (
        f"coverage mismatches = {len(coverage_mismatches)}: {coverage_mismatches}"
    )
