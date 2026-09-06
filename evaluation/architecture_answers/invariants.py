"""Live cross-tool invariants (I3 spec §33.1-§33.3), checked for every `get_architecture_drift`
scenario's real actual answer - never the frozen expected answers ("a live cross-tool consistency
assertion, not the source of expected ground truth", spec §33.1).

Both checks in `check_drift_invariants` MUST run immediately after the drift answer is produced,
before the next scenario's `reset_graph` wipes that graph state - same reasoning
`runner._broken_evidence_refs` already documents for its own per-scenario integrity check. This
also means the invariant does NOT depend on two different scenario directories coincidentally
producing the same snapshot fingerprint (they never do: `Evidence.source_file` embeds each
scenario's own directory path verbatim, so byte-identical `input/` content under two differently
named scenario directories still yields two different snapshots - confirmed by running the suite).
Instead, `check_dependency_to_drift` builds its own `get_service_dependencies` request for the
drift answer's own `service_id`, pinned to the drift answer's own `snapshot_id` and reconstructed
`observation_context`, and calls it against that same still-live graph - no paired scenario
directory needed at all.

Deliberately does not reimplement the drift filter: `check_dependency_to_drift` imports the same
`DRIFT_QUALIFICATIONS` constant `app.architecture_intelligence.drift_projection` filters by, rather
than hand-copying the two-value set (spec §30: "The comparator MUST NOT derive expected
qualifications").

§33.4 (Service-to-MCP) is deliberately NOT checked here - spec §30's evaluator diagram has no MCP
layer, and folding MCP transport/session-manager plumbing into this independent evaluator would
blur the boundary it exists to keep. It is instead proven by
`tests/integration/test_mcp_drift_scenario_parity.py` against every drift scenario in this same
bundled suite; `reporter.py` records that file, plus a live-computed scenario count, as the
qualifying evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.architecture_intelligence.drift_projection import DRIFT_QUALIFICATIONS
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from evaluation.architecture_answers.model import TOOL_ARCHITECTURE_DRIFT, ExpectedAnswer


@dataclass(frozen=True)
class CrossToolInvariantFailure:
    invariant: str
    detail: str


def _check_drift_to_evidence(
    answer: ExpectedAnswer, *, service: ArchitectureIntelligenceService
) -> list[CrossToolInvariantFailure]:
    """Spec §33.3: every evidence ref a drift answer returns must resolve through `get_evidence` at
    that same drift answer's own snapshot."""
    if not answer.evidence_refs:
        return []
    evidence_answer = service.get_evidence(
        EvidenceRequest.model_validate(
            {
                "evidence_refs": sorted(answer.evidence_refs),
                "snapshot_id": answer.snapshot.snapshot_id,
            }
        )
    )
    # get_evidence legitimately refuses with data=None (SNAPSHOT_NOT_AVAILABLE - the drift answer's
    # own snapshot stopped being current between producing it and this immediately-following call,
    # or the stable-read retry itself could not settle) - that refusal is itself a real invariant
    # failure (the evidence a drift answer just returned no longer resolves at all), not something
    # to crash the whole suite run over by blindly reading `.data.missing_evidence_refs`.
    if evidence_answer.data is None:
        return [
            CrossToolInvariantFailure(
                invariant="drift_to_evidence",
                detail=(
                    f"snapshot={answer.snapshot.snapshot_id}: get_evidence refused "
                    f"({[lim.code.value for lim in evidence_answer.limitations]})"
                ),
            )
        ]
    if not evidence_answer.data.missing_evidence_refs:
        return []
    return [
        CrossToolInvariantFailure(
            invariant="drift_to_evidence",
            detail=(
                f"snapshot={answer.snapshot.snapshot_id}: missing evidence refs "
                f"{evidence_answer.data.missing_evidence_refs}"
            ),
        )
    ]


def _check_dependency_to_drift(
    answer: ExpectedAnswer, *, service: ArchitectureIntelligenceService
) -> list[CrossToolInvariantFailure]:
    """Spec §33.1/§33.2: `drift.claims` must equal a live `get_service_dependencies` call for the
    same service, pinned to the drift answer's own snapshot and observation context, filtered to
    the two discrepancy qualifications - by real object equality (`claim_id`, payload and evidence
    linkage together, since `DependencyClaim.__eq__` compares every field). Only meaningful for a
    successful drift answer naming a real service; a refusal (`data is None`) has nothing to
    compare against."""
    if answer.data is None:
        return []
    context = answer.observation_context
    dependency_answer = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": answer.data.service.id,
                "observation_context": {
                    "environment": context.environment,
                    "window_start": context.window_start,
                    "window_end": context.window_end,
                },
                "snapshot_id": answer.snapshot.snapshot_id,
            }
        )
    )
    expected_drift_claims = [
        claim for claim in dependency_answer.claims if claim.qualification in DRIFT_QUALIFICATIONS
    ]
    if list(answer.claims) == expected_drift_claims:
        return []
    return [
        CrossToolInvariantFailure(
            invariant="dependency_to_drift",
            detail=(
                f"service={answer.data.service.id} snapshot={answer.snapshot.snapshot_id}: "
                "drift.claims != live dependency.claims filtered to "
                f"{sorted(q.value for q in DRIFT_QUALIFICATIONS)}"
            ),
        )
    ]


def check_drift_invariants(
    answer: ExpectedAnswer, *, service: ArchitectureIntelligenceService
) -> list[CrossToolInvariantFailure]:
    """Both live cross-tool checks for one drift answer. Caller MUST invoke this immediately after
    producing `answer`, before the next scenario's `reset_graph` - see module docstring. A no-op for
    any non-drift answer (no invariant to check)."""
    if answer.tool != TOOL_ARCHITECTURE_DRIFT:
        return []
    return _check_dependency_to_drift(answer, service=service) + _check_drift_to_evidence(
        answer, service=service
    )
