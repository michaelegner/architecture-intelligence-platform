"""Orchestrates the architecture-answers evaluation suite: two full clean-state passes over every
scenario against a live AIP instance (I1.4 review finding #4 - "two identical runs" means two
complete reset -> ingest -> observe -> reconcile -> call-service passes of the whole suite, not two
calls against one already-prepared graph).

I3.3 (spec §31) generalizes dispatch to all three tools via `_DISPATCH`, a fixed
tool -> (request type, service method name) table - "dispatch, not architecture semantics" (spec
§31): no generic tool-workflow DSL, just one small lookup.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from app.version import package_version
from evaluation import fixture_setup
from evaluation.architecture_answers.candidate import resolve_candidate_sha
from evaluation.architecture_answers.comparator import ScenarioReport, compare
from evaluation.architecture_answers.invariants import (
    CrossToolInvariantFailure,
    check_drift_invariants,
)
from evaluation.architecture_answers.model import (
    TOOL_ARCHITECTURE_DRIFT,
    TOOL_EVIDENCE,
    TOOL_SERVICE_DEPENDENCIES,
    ExpectedAnswer,
    Request,
    Scenario,
)

_DATABASE = "neo4j"
_BROKEN_EVIDENCE_QUERY = "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c"

# tool -> (request type, ArchitectureIntelligenceService method name). Spec §31's dispatch table.
_DISPATCH: dict[str, tuple[type, str]] = {
    TOOL_SERVICE_DEPENDENCIES: (ServiceDependenciesRequest, "get_service_dependencies"),
    TOOL_ARCHITECTURE_DRIFT: (ArchitectureDriftRequest, "get_architecture_drift"),
    TOOL_EVIDENCE: (EvidenceRequest, "get_evidence"),
}


def _build_producer(candidate_sha: str) -> Producer:
    # Real production build-provenance wiring is finalized in I4 (spec §10); until then this
    # evaluator injects the resolved candidate SHA rather than a placeholder literal (spec §27/§28
    # - a missing or placeholder build revision must never qualify a release artifact).
    # `version` is read from `app.version.package_version()` (PR #120 review finding: a frozen
    # literal here independently drifted from the real production version, and every scenario's
    # own `expected_answer.json` had frozen the same wrong literal alongside it, so the mismatch
    # never surfaced) - `name` stays a frozen literal, the fixed application identity.
    return Producer(
        name="architecture-intelligence-platform",
        version=package_version(),
        build_revision=candidate_sha,
    )


def build_request_payload(request: Request) -> dict:
    """The tool-shaped request payload a scenario's `Request` maps to - public because
    `tests/integration/test_mcp_drift_scenario_parity.py` (I3 spec §33.4) needs the exact same
    construction the live evaluator run uses, not a second copy of it that could silently drift
    apart from this one."""
    if request.tool == TOOL_EVIDENCE:
        return {"evidence_refs": list(request.evidence_refs), "snapshot_id": request.snapshot_id}

    observation_context = None
    has_any_context_field = (
        request.environment is not None
        or request.window_start is not None
        or request.window_end is not None
    )
    if has_any_context_field:
        observation_context = {
            "environment": request.environment,
            "window_start": request.window_start,
            "window_end": request.window_end,
        }
    return {
        "service_id": request.service_id,
        "observation_context": observation_context,
        "snapshot_id": request.snapshot_id,
    }


def _run_pass(driver: neo4j.Driver, *, scenario: Scenario, producer: Producer) -> ExpectedAnswer:
    fixture_setup.prepare_scenario(driver, database=_DATABASE, scenario_path=scenario.path)
    # `import_all_sources` (inside prepare_scenario) also calls this, idempotently, whenever a
    # scenario has declarations - but a scenario with none at all (e.g. a request-level refusal
    # against an otherwise-empty graph) would otherwise leave no revision singleton behind for
    # ArchitectureIntelligenceService to read. Deliberately not folded into evaluation.fixture_setup
    # .reset_graph itself - that would change its observable node-count contract, which the
    # existing relation-facts suite's own tests assert on.
    with driver.session(database=_DATABASE) as session:
        ensure_schema(session)
    service = ArchitectureIntelligenceService(driver, database=_DATABASE, producer=producer)
    request_type, method_name = _DISPATCH[scenario.request.tool]
    request = request_type.model_validate(build_request_payload(scenario.request))
    return getattr(service, method_name)(request)


def _broken_evidence_refs(
    driver: neo4j.Driver, *, evidence_refs: tuple[str, ...]
) -> tuple[str, ...]:
    """Independent real-Neo4j integrity check, additive to the comparator's exact-list comparison -
    every id in the actual answer's evidence_refs must resolve to a real Evidence node."""
    if not evidence_refs:
        return ()
    broken = []
    with driver.session(database=_DATABASE) as session:
        for evidence_id in evidence_refs:
            count = session.run(_BROKEN_EVIDENCE_QUERY, id=evidence_id).single()["c"]
            if count == 0:
                broken.append(evidence_id)
    return tuple(sorted(broken))


def _suite_hash(answers: list[ExpectedAnswer]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(answers)).hexdigest()


@dataclass(frozen=True)
class SuiteResult:
    candidate_sha: str
    reports: tuple[ScenarioReport, ...]
    run_count: int
    run_output_sha256: tuple[str, str]
    semantic_outputs_identical: bool
    cross_tool_invariant_failures: tuple[CrossToolInvariantFailure, ...] = ()


def run_suite(
    driver: neo4j.Driver, scenarios: list[Scenario], *, candidate_sha: str | None = None
) -> SuiteResult:
    """`candidate_sha` is the one immutable run identity shared by the producer injected into every
    live service call, the comparator's independent `producer.build_revision` check, and the
    recorded result artifact (I1.4 review) - resolved exactly once here, not re-derived separately
    by each component. Pass it explicitly (`python -m evaluation answers --candidate-sha <40hex>`)
    for a real release-qualification run; omit it only for ad-hoc/local runs against the current
    checkout."""
    resolved_sha = resolve_candidate_sha(candidate_sha)
    producer = _build_producer(resolved_sha)
    sorted_scenarios = sorted(scenarios, key=lambda s: s.id)

    first_pass = [
        _run_pass(driver, scenario=scenario, producer=producer) for scenario in sorted_scenarios
    ]

    second_pass: list[ExpectedAnswer] = []
    reports: list[ScenarioReport] = []
    invariant_failures: list[CrossToolInvariantFailure] = []
    for scenario in sorted_scenarios:
        answer = _run_pass(driver, scenario=scenario, producer=producer)
        second_pass.append(answer)
        # Everything below must happen immediately, before the next scenario's reset_graph wipes
        # this state - the broken-evidence-ref integrity check and both §33.1/§33.3 cross-tool
        # invariants all need a live read against the exact graph this specific answer was
        # produced from.
        broken_refs = _broken_evidence_refs(driver, evidence_refs=tuple(answer.evidence_refs))
        if answer.tool == TOOL_ARCHITECTURE_DRIFT:
            service = ArchitectureIntelligenceService(driver, database=_DATABASE, producer=producer)
            invariant_failures.extend(check_drift_invariants(answer, service=service))
        reports.append(
            compare(scenario, answer, candidate_sha=resolved_sha, broken_evidence_refs=broken_refs)
        )

    first_hash = _suite_hash(first_pass)
    second_hash = _suite_hash(second_pass)

    return SuiteResult(
        candidate_sha=resolved_sha,
        reports=tuple(reports),
        run_count=2,
        run_output_sha256=(first_hash, second_hash),
        semantic_outputs_identical=first_hash == second_hash,
        cross_tool_invariant_failures=tuple(invariant_failures),
    )
