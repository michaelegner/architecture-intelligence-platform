"""Orchestrates the architecture-answers evaluation suite: two full clean-state passes over every
scenario against a live AIP instance (I1.4 review finding #4 - "two identical runs" means two
complete reset -> ingest -> observe -> reconcile -> call-service passes of the whole suite, not two
calls against one already-prepared graph).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    Producer,
    ServiceDependenciesData,
)
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from evaluation import fixture_setup
from evaluation.architecture_answers.candidate import current_git_sha
from evaluation.architecture_answers.comparator import ScenarioReport, compare
from evaluation.architecture_answers.model import Scenario

# Real production build-provenance wiring is finalized in I4 (spec §10); until then this evaluator
# injects the actual candidate git SHA rather than a placeholder literal (spec §27/§28 - a missing
# or placeholder build revision must never qualify a release artifact). producer.name/version are
# still frozen literals - the application identity/version target, not the per-commit revision.
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.0", build_revision=current_git_sha()
)

_DATABASE = "neo4j"
_BROKEN_EVIDENCE_QUERY = "MATCH (e:Evidence {id: $id}) RETURN count(e) AS c"


def _build_request(scenario: Scenario) -> ServiceDependenciesRequest:
    request = scenario.request
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
    return ServiceDependenciesRequest.model_validate(
        {
            "service_id": request.service_id,
            "observation_context": observation_context,
            "snapshot_id": request.snapshot_id,
        }
    )


def _run_pass(
    driver: neo4j.Driver, *, scenario: Scenario
) -> ArchitectureAnswer[ServiceDependenciesData]:
    fixture_setup.prepare_scenario(driver, database=_DATABASE, scenario_path=scenario.path)
    # `import_all_sources` (inside prepare_scenario) also calls this, idempotently, whenever a
    # scenario has declarations - but a scenario with none at all (e.g. a request-level refusal
    # against an otherwise-empty graph) would otherwise leave no revision singleton behind for
    # ArchitectureIntelligenceService to read. Deliberately not folded into evaluation.fixture_setup
    # .reset_graph itself - that would change its observable node-count contract, which the
    # existing relation-facts suite's own tests assert on.
    with driver.session(database=_DATABASE) as session:
        ensure_schema(session)
    service = ArchitectureIntelligenceService(driver, database=_DATABASE, producer=PRODUCER)
    return service.get_service_dependencies(_build_request(scenario))


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


def _suite_hash(answers: list[ArchitectureAnswer[ServiceDependenciesData]]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(answers)).hexdigest()


@dataclass(frozen=True)
class SuiteResult:
    reports: tuple[ScenarioReport, ...]
    run_count: int
    run_output_sha256: tuple[str, str]
    semantic_outputs_identical: bool


def run_suite(driver: neo4j.Driver, scenarios: list[Scenario]) -> SuiteResult:
    sorted_scenarios = sorted(scenarios, key=lambda s: s.id)

    first_pass = [_run_pass(driver, scenario=scenario) for scenario in sorted_scenarios]

    second_pass: list[ArchitectureAnswer[ServiceDependenciesData]] = []
    reports: list[ScenarioReport] = []
    for scenario in sorted_scenarios:
        answer = _run_pass(driver, scenario=scenario)
        second_pass.append(answer)
        # Must happen immediately, before the next scenario's reset_graph wipes this state.
        broken_refs = _broken_evidence_refs(driver, evidence_refs=tuple(answer.evidence_refs))
        reports.append(compare(scenario, answer, broken_evidence_refs=broken_refs))

    first_hash = _suite_hash(first_pass)
    second_hash = _suite_hash(second_pass)

    return SuiteResult(
        reports=tuple(reports),
        run_count=2,
        run_output_sha256=(first_hash, second_hash),
        semantic_outputs_identical=first_hash == second_hash,
    )
