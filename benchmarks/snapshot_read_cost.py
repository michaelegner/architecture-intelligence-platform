"""v0.4.1 I3.1 - the committed, reproducible whole-graph snapshot/read-cost benchmark (spec
`docs/specifications/0.4.1/i3-hardening-qualification-and-release.md` §7-17).

Answers one bounded question: with the requested dependency answer held constant, how does the
cost of `canonical_snapshot_state()`/`snapshot_fingerprint()` and one end-to-end
`get_service_dependencies` MCP call change as unrelated total graph/evidence size grows? This is
evidence for a later scaling decision (ADR 0011 §18), not a performance SLO, and this module never
implements a cache, retention policy, or any other production behavior change.

Fixture model (spec §9): one fixed target subgraph - `order-service` calling `product-service`'s
`GET /products/{id}`, from the real `examples/` reference landscape, observed once - whose
dependency answer has constant semantic cardinality at every scale point, plus N unrelated
synthetic Service/Operation/CALLS facts that grow `canonical_snapshot_state()` without ever
touching the target answer. Both are seeded through real production write paths -
`app.graph.importer.import_all_sources` and `app.telemetry.aggregator.persist_observation_batch` -
not hand-rolled Cypher, and every timed read below imports and calls the real production
snapshot/service/MCP code directly (spec R1/R2) rather than reimplementing it.
"""

from __future__ import annotations

import itertools
import os
import platform
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import neo4j

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.repository import open_session
from app.graph.revision_fence import read_revision
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity
from tests.integration.independent_mcp_client import call_tool

SCHEMA_VERSION = "aip-benchmark/v1"
BENCHMARK_NAME = "snapshot_read_cost"
BENCHMARK_IMPLEMENTATION_VERSION = 1

DATABASE = "neo4j"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
ENVIRONMENT = "benchmark"
_WINDOW_START = datetime(2026, 1, 1, tzinfo=UTC)
_WINDOW_END = datetime(2026, 1, 2, tzinfo=UTC)
_BUCKET_START = datetime(2026, 1, 1, 12, tzinfo=UTC)  # inside [_WINDOW_START, _WINDOW_END)

TARGET_SERVICE_ID = ids.service_id("order-service")
TARGET_OPERATION_ID = ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}")

SMOKE_PROFILE = "smoke"
REVIEW_COMPARABLE_PROFILE = "review-comparable"
DATABASE_LIFECYCLE = "clean_rebuild_per_scale_point"
SEED_METHOD = "production_import_and_telemetry_aggregation"

# Each entry is the count of unrelated synthetic CALLS facts seeded at that scale point (spec §9's
# constant-target/growing-total-snapshot split); each fact adds exactly one Service, one Operation,
# one Evidence node and one CALLS relation (verified by `verify_structural_counts`, not assumed).
# The ~20-node fixed target subgraph (examples/ + one observed CALLS fact) plus these counts lands
# near the spec §10.2 orders of magnitude - exact dimensions are an implementation choice the spec
# explicitly leaves open ("MAY choose exact fixture dimensions that make deterministic seeding
# simpler").
SCALE_POINTS: dict[str, tuple[int, ...]] = {
    SMOKE_PROFILE: (2, 10),
    REVIEW_COMPARABLE_PROFILE: (30, 1650, 6650, 33000),
}

_BATCH_CHUNK_SIZE = 500
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
UNKNOWN_CANDIDATE_SHA = "unknown"
_REPO_ROOT = Path(__file__).resolve().parent.parent


# --- candidate identity (spec §13, mirrors evaluation.architecture_answers.candidate) -----------


class InvalidCandidateSha(ValueError):
    """An explicit candidate SHA was given but isn't a well-formed 40-hex git SHA."""


def current_git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def is_dirty_worktree() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def resolve_candidate_sha(explicit: str | None = None) -> str:
    """The candidate SHA one `run_profile` call qualifies. `explicit` if given (validated as a real
    40-hex SHA), otherwise the current git HEAD, otherwise `UNKNOWN_CANDIDATE_SHA` for local
    development only - spec §13: "a result with unknown candidate identity cannot qualify I3"."""
    if explicit is not None:
        if not _SHA_PATTERN.match(explicit):
            raise InvalidCandidateSha(f"not a well-formed 40-hex git SHA: {explicit!r}")
        return explicit
    return current_git_sha() or UNKNOWN_CANDIDATE_SHA


# --- deterministic fixture plan (spec §9, §17.1) --------------------------------------------------


@dataclass(frozen=True)
class FixturePlan:
    profile: str
    scale_index: int
    unrelated_fact_count: int


def build_fixture_plan(profile: str, scale_index: int) -> FixturePlan:
    """Deterministic: the same `(profile, scale_index)` always produces the same plan."""
    if profile not in SCALE_POINTS:
        raise ValueError(f"unknown profile: {profile!r}")
    counts = SCALE_POINTS[profile]
    if not (0 <= scale_index < len(counts)):
        raise ValueError(f"scale_index {scale_index} out of range for profile {profile!r}")
    return FixturePlan(
        profile=profile, scale_index=scale_index, unrelated_fact_count=counts[scale_index]
    )


def _unrelated_entity_ids(index: int) -> tuple[str, str]:
    service_id = ids.service_id(f"bench-unrelated-svc-{index:06d}")
    operation_id = ids.operation_id(service_id, "GET", f"/bench/{index:06d}")
    return service_id, operation_id


def _unrelated_fact(index: int) -> tuple[list[ObservedOnlyEntity], ObservedFactCandidate]:
    subject_id, object_id = _unrelated_entity_ids(index)
    trace_id = f"{index:032x}"
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(ENVIRONMENT, _BUCKET_START, subject_id, "CALLS", object_id),
        environment=ENVIRONMENT,
        bucket_start=_BUCKET_START,
        bucket_end=_BUCKET_START,
        first_seen=_BUCKET_START,
        last_seen=_BUCKET_START,
        observation_count=1,
        sample_trace_ids=[trace_id],
        correlation_mode="CLIENT_ONLY",
    )
    entities = [
        ObservedOnlyEntity(id=subject_id, label="Service", name=f"bench-unrelated-svc-{index:06d}"),
        ObservedOnlyEntity(id=object_id, label="Operation", name=f"GET /bench/{index:06d}"),
    ]
    fact = ObservedFactCandidate(
        subject_id=subject_id,
        relation_type="CALLS",
        object_id=object_id,
        environment=ENVIRONMENT,
        timestamp=_BUCKET_START,
        trace_id=trace_id,
        evidence=evidence,
    )
    return entities, fact


# --- disposable seeding (spec §8, real production write paths) -----------------------------------


def wipe_database(driver: neo4j.Driver) -> None:
    with open_session(driver, database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def seed_target_subgraph(driver: neo4j.Driver) -> None:
    """The fixed target subgraph (spec §9): `order-service` -[:CALLS]-> `product-service`'s
    `GET /products/{id}`, declared via the real `examples/` fixture landscape
    (`app.graph.importer.import_all_sources`) and then observed once via the real telemetry
    aggregation path (`app.telemetry.aggregator.persist_observation_batch`) - the same production
    pipeline `tests/integration/test_mcp_independent_client_golden_path.py` already proves yields a
    CONFIRMED SYNC_HTTP claim, so the target answer's qualification is known and stable."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    trace_id = "b" * 32
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(
            ENVIRONMENT, _BUCKET_START, TARGET_SERVICE_ID, "CALLS", TARGET_OPERATION_ID
        ),
        environment=ENVIRONMENT,
        bucket_start=_BUCKET_START,
        bucket_end=_BUCKET_START,
        first_seen=_BUCKET_START,
        last_seen=_BUCKET_START,
        observation_count=1,
        sample_trace_ids=[trace_id],
        correlation_mode="CLIENT_SERVER",
    )
    batch = ObservationBatch(
        facts=[
            ObservedFactCandidate(
                subject_id=TARGET_SERVICE_ID,
                relation_type="CALLS",
                object_id=TARGET_OPERATION_ID,
                environment=ENVIRONMENT,
                timestamp=_BUCKET_START,
                trace_id=trace_id,
                evidence=evidence,
            )
        ]
    )
    persist_observation_batch(driver, DATABASE, batch)


def seed_unrelated_scale_data(driver: neo4j.Driver, *, count: int) -> None:
    """Grows `canonical_snapshot_state()` without touching the target answer (spec §9): `count`
    synthetic Service/Operation pairs with one CALLS fact each, seeded through the same production
    `persist_observation_batch` write path the target subgraph's own observation uses, in
    fixed-size chunks rather than one single all-in-one-transaction call."""
    for start in range(0, count, _BATCH_CHUNK_SIZE):
        chunk = range(start, min(start + _BATCH_CHUNK_SIZE, count))
        entities: list[ObservedOnlyEntity] = []
        facts: list[ObservedFactCandidate] = []
        for index in chunk:
            chunk_entities, fact = _unrelated_fact(index)
            entities.extend(chunk_entities)
            facts.append(fact)
        persist_observation_batch(
            driver, DATABASE, ObservationBatch(entities=entities, facts=facts)
        )


# --- structural counts and validation (spec §12) --------------------------------------------------


@dataclass(frozen=True)
class ActualCounts:
    service_count: int
    operation_count: int
    queue_count: int
    message_count: int
    schema_count: int
    evidence_count: int
    relation_count: int


def measure_structural_counts(session: neo4j.Session) -> ActualCounts:
    def count(label: str) -> int:
        return session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]

    relation_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    return ActualCounts(
        service_count=count("Service"),
        operation_count=count("Operation"),
        queue_count=count("Queue"),
        message_count=count("Message"),
        schema_count=count("Schema"),
        evidence_count=count("Evidence"),
        relation_count=relation_count,
    )


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    detail: str


def verify_structural_counts(
    counts_after_target: ActualCounts, counts_after_unrelated: ActualCounts, plan: FixturePlan
) -> ValidationResult:
    """A mismatch is a benchmark failure, not a timing anomaly (spec §12). Compares the *delta*
    against the plan rather than a hardcoded absolute count, so this never depends on `examples/`'s
    own exact fixture shape - only on each unrelated fact adding exactly one Service, one
    Operation, one Evidence node and one CALLS relation."""
    n = plan.unrelated_fact_count
    expected = ActualCounts(
        service_count=counts_after_target.service_count + n,
        operation_count=counts_after_target.operation_count + n,
        queue_count=counts_after_target.queue_count,
        message_count=counts_after_target.message_count,
        schema_count=counts_after_target.schema_count,
        evidence_count=counts_after_target.evidence_count + n,
        relation_count=counts_after_target.relation_count + n,
    )
    if counts_after_unrelated != expected:
        return ValidationResult(
            passed=False,
            detail=f"expected {expected} after seeding {n} unrelated facts, measured "
            f"{counts_after_unrelated}",
        )
    return ValidationResult(passed=True, detail="structural counts match the deterministic plan")


def seed_scale_point(driver: neo4j.Driver, plan: FixturePlan) -> tuple[ActualCounts, ActualCounts]:
    """Wipes the database, seeds the fixed target subgraph, records its structural counts, then
    seeds `plan.unrelated_fact_count` unrelated synthetic facts and records the counts again."""
    wipe_database(driver)
    seed_target_subgraph(driver)
    with open_session(driver, database=DATABASE, read_only=True) as session:
        counts_after_target = measure_structural_counts(session)
    seed_unrelated_scale_data(driver, count=plan.unrelated_fact_count)
    with open_session(driver, database=DATABASE, read_only=True) as session:
        counts_after_unrelated = measure_structural_counts(session)
    return counts_after_target, counts_after_unrelated


# --- timing (spec §11) ------------------------------------------------------------------------


class RevisionFenceMoved(RuntimeError):
    """The internal revision fence moved during a timed sample loop, with no concurrent writer
    (spec §11: "explicit failure if the revision fence moves during a sample beyond production's
    permitted retry behavior")."""


@dataclass(frozen=True)
class SnapshotTimingSamples:
    durations_seconds: list[float]
    snapshot_ids: list[str]
    model_revisions: list[str]


def measure_snapshot_and_fingerprint(
    session: neo4j.Session, *, coverage_qualification_enabled: bool, warmup: int, samples: int
) -> SnapshotTimingSamples:
    for _ in range(warmup):
        canonical_snapshot_state(
            session, coverage_qualification_enabled=coverage_qualification_enabled
        )
    durations: list[float] = []
    snapshot_ids: list[str] = []
    model_revisions: list[str] = []
    for _ in range(samples):
        start = time.perf_counter()
        state = canonical_snapshot_state(
            session, coverage_qualification_enabled=coverage_qualification_enabled
        )
        snapshot_id, model_revision = snapshot_fingerprint(state)
        durations.append(time.perf_counter() - start)
        snapshot_ids.append(snapshot_id)
        model_revisions.append(model_revision)
    return SnapshotTimingSamples(durations, snapshot_ids, model_revisions)


@dataclass(frozen=True)
class DependencyTimingSamples:
    durations_seconds: list[float]
    snapshot_ids: list[str]
    model_revisions: list[str]
    last_structured_content: dict[str, Any]


def measure_dependency_call(
    client: httpx.Client,
    *,
    service_id: str,
    observation_context: dict[str, str],
    warmup: int,
    samples: int,
) -> DependencyTimingSamples:
    def call() -> dict[str, Any]:
        result = call_tool(
            client,
            name="get_service_dependencies",
            arguments={
                "request": {"service_id": service_id, "observation_context": observation_context}
            },
        )
        return result["structuredContent"]

    for _ in range(warmup):
        call()
    durations: list[float] = []
    snapshot_ids: list[str] = []
    model_revisions: list[str] = []
    last_structured_content: dict[str, Any] = {}
    for _ in range(samples):
        start = time.perf_counter()
        structured_content = call()
        durations.append(time.perf_counter() - start)
        snapshot_ids.append(structured_content["snapshot"]["snapshot_id"])
        model_revisions.append(structured_content["snapshot"]["model_revision"])
        last_structured_content = structured_content
    return DependencyTimingSamples(
        durations, snapshot_ids, model_revisions, last_structured_content
    )


def _timing_summary(durations: list[float]) -> dict[str, Any]:
    return {
        "raw_seconds": durations,
        "minimum_seconds": min(durations),
        "median_seconds": statistics.median(durations),
    }


def _all_equal(values: list[str]) -> bool:
    return len(set(values)) == 1


# --- target-answer semantic invariance (spec §12) --------------------------------------------


def canonicalize_target_answer(structured_content: dict[str, Any]) -> dict[str, Any]:
    """Strips snapshot identity/build metadata that legitimately reflects a larger graph, keeping
    only what spec §12 requires to remain equal: requested service, observation context, outcome,
    claim identities/qualifications/delivery semantics, limitations."""
    claims = [
        {
            "claim_id": claim["claim_id"],
            "subject": claim["subject"],
            "object": claim["object"],
            "predicate": claim["predicate"],
            "destination_resolution": claim["destination_resolution"],
            "delivery": claim["delivery"],
            "qualification": claim["qualification"],
            "coverage": claim.get("coverage"),
            "evidence_refs": sorted(claim["evidence_refs"]),
            "resolution_evidence_refs": sorted(claim["resolution_evidence_refs"]),
        }
        for claim in structured_content["claims"]
    ]
    return {
        "tool": structured_content["tool"],
        "outcome": structured_content["outcome"],
        "observation_context": structured_content["observation_context"],
        "data": structured_content["data"],
        "claims": claims,
        "limitations": structured_content["limitations"],
    }


def verify_target_answer_invariance(canonical_answers: list[dict[str, Any]]) -> ValidationResult:
    if not canonical_answers:
        return ValidationResult(passed=False, detail="no answers to compare")
    first = canonical_answers[0]
    for index, answer in enumerate(canonical_answers[1:], start=1):
        if answer != first:
            return ValidationResult(
                passed=False,
                detail=f"scale point {index}'s target answer diverged from scale point 0's",
            )
    return ValidationResult(passed=True, detail="target answer identical at every scale point")


# --- runtime metadata (spec §14) ----------------------------------------------------------------


def _memory_total_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def collect_runtime_metadata(*, neo4j_version: str | None) -> dict[str, Any]:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "cpu_model": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "memory_total_bytes": _memory_total_bytes(),
        "python_version": sys.version.split()[0],
        "neo4j_version": neo4j_version,
    }


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# --- orchestration (spec §13) -------------------------------------------------------------------


def run_profile(
    profile: str,
    *,
    driver: neo4j.Driver,
    client: httpx.Client,
    candidate_sha: str,
    dirty_worktree: bool,
    neo4j_version: str | None = None,
    warmup: int = 1,
    samples: int = 3,
) -> dict[str, Any]:
    if samples < 3:
        raise ValueError("spec §11: at least three measured samples per operation/scale point")

    started_at = datetime.now(UTC)
    scale_counts = SCALE_POINTS[profile]
    observation_context = {
        "environment": ENVIRONMENT,
        "window_start": _iso(_WINDOW_START),
        "window_end": _iso(_WINDOW_END),
    }

    scale_point_results: list[dict[str, Any]] = []
    canonical_answers: list[dict[str, Any]] = []
    for scale_index in range(len(scale_counts)):
        plan = build_fixture_plan(profile, scale_index)
        counts_after_target, counts_after_unrelated = seed_scale_point(driver, plan)
        structural_result = verify_structural_counts(
            counts_after_target, counts_after_unrelated, plan
        )

        with open_session(driver, database=DATABASE, read_only=True) as session:
            revision_before = read_revision(session)
            snapshot_samples = measure_snapshot_and_fingerprint(
                session, coverage_qualification_enabled=True, warmup=warmup, samples=samples
            )
            revision_after = read_revision(session)
        if revision_before != revision_after:
            raise RevisionFenceMoved(
                f"revision fence moved from {revision_before} to {revision_after} during a "
                f"snapshot timing loop at scale point {scale_index} - no concurrent writer exists "
                "during a benchmark run"
            )

        dependency_samples = measure_dependency_call(
            client,
            service_id=TARGET_SERVICE_ID,
            observation_context=observation_context,
            warmup=warmup,
            samples=samples,
        )
        structured_content = dependency_samples.last_structured_content
        canonical_answers.append(canonicalize_target_answer(structured_content))

        claims = structured_content.get("claims", [])
        target_evidence_ref_count = len(
            {
                ref
                for claim in claims
                for ref in (*claim["evidence_refs"], *claim["resolution_evidence_refs"])
            }
        )

        scale_point_results.append(
            {
                "scale_index": scale_index,
                "planned_unrelated_fact_count": plan.unrelated_fact_count,
                "actual_node_counts": {
                    "service": counts_after_unrelated.service_count,
                    "operation": counts_after_unrelated.operation_count,
                    "queue": counts_after_unrelated.queue_count,
                    "message": counts_after_unrelated.message_count,
                    "schema": counts_after_unrelated.schema_count,
                    "evidence": counts_after_unrelated.evidence_count,
                },
                "actual_relation_count": counts_after_unrelated.relation_count,
                "target_claim_count": len(claims),
                "target_evidence_reference_count": target_evidence_ref_count,
                "revision_fence_value": revision_after,
                "snapshot_fingerprint_seconds": _timing_summary(snapshot_samples.durations_seconds),
                "dependency_call_seconds": _timing_summary(dependency_samples.durations_seconds),
                "snapshot_id_consistent": _all_equal(snapshot_samples.snapshot_ids)
                and _all_equal(dependency_samples.snapshot_ids)
                and snapshot_samples.snapshot_ids[0] == dependency_samples.snapshot_ids[0],
                "model_revision_consistent": _all_equal(snapshot_samples.model_revisions)
                and _all_equal(dependency_samples.model_revisions)
                and snapshot_samples.model_revisions[0] == dependency_samples.model_revisions[0],
                "structural_validation": "PASS" if structural_result.passed else "FAIL",
                "structural_validation_detail": structural_result.detail,
            }
        )

    invariance = verify_target_answer_invariance(canonical_answers)
    for entry in scale_point_results:
        entry["semantic_validation"] = "PASS" if invariance.passed else "FAIL"

    completed_at = datetime.now(UTC)

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_implementation_version": BENCHMARK_IMPLEMENTATION_VERSION,
        "candidate_sha": candidate_sha,
        "dirty_worktree": dirty_worktree,
        "started_at": _iso(started_at),
        "completed_at": _iso(completed_at),
        "profile": profile,
        "database_lifecycle": DATABASE_LIFECYCLE,
        "seed_method": SEED_METHOD,
        "warmup_count": warmup,
        "sample_count": samples,
        "request": {
            "tool": "get_service_dependencies",
            "service_id": TARGET_SERVICE_ID,
            "observation_context": observation_context,
        },
        "runtime_metadata": collect_runtime_metadata(neo4j_version=neo4j_version),
        "semantic_validation_detail": invariance.detail,
        "scale_points": scale_point_results,
    }


# --- determinism canonicalization (spec §15) ----------------------------------------------------

_VARIABLE_TOP_LEVEL_FIELDS = frozenset({"started_at", "completed_at", "runtime_metadata"})
_VARIABLE_SCALE_POINT_FIELDS = frozenset(
    {"snapshot_fingerprint_seconds", "dependency_call_seconds"}
)


def qualifies_for_release(result: dict[str, Any]) -> ValidationResult:
    """Spec §13: "a result with unknown candidate identity cannot qualify I3"; "dirty_worktree =
    true is release-blocking". A pure check over an already-produced result dict, used during
    candidate qualification (I3.2) - a local/dev run with `unknown`/dirty state is still allowed to
    run and be inspected; it just cannot be cited as release evidence."""
    if result["candidate_sha"] == UNKNOWN_CANDIDATE_SHA:
        return ValidationResult(
            passed=False, detail="candidate_sha is unknown - not release-qualifying"
        )
    if not _SHA_PATTERN.match(result["candidate_sha"]):
        return ValidationResult(
            passed=False,
            detail=f"candidate_sha {result['candidate_sha']!r} is not a well-formed 40-hex SHA",
        )
    if result["dirty_worktree"]:
        return ValidationResult(
            passed=False, detail="dirty_worktree is true - not release-qualifying"
        )
    return ValidationResult(passed=True, detail="candidate identity is release-qualifying")


def render_human_summary(result: dict[str, Any]) -> str:
    """Spec §16: every scale point and both timed operations, at least the ratio between adjacent
    graph sizes and adjacent minimum durations, and a conclusion using only the three bounded
    phrases the spec allows - never a claimed linear law, and never an SLO/pass-fail threshold."""
    lines = [
        (
            f"snapshot_read_cost benchmark - profile={result['profile']} "
            f"candidate={result['candidate_sha']}"
        ),
        "",
    ]
    points = result["scale_points"]
    for point in points:
        total_nodes = sum(point["actual_node_counts"].values())
        lines.append(
            f"  scale_index={point['scale_index']} total_nodes={total_nodes} "
            f"relations={point['actual_relation_count']} "
            f"snapshot_min={point['snapshot_fingerprint_seconds']['minimum_seconds']:.4f}s "
            f"dependency_min={point['dependency_call_seconds']['minimum_seconds']:.4f}s "
            f"structural={point['structural_validation']} semantic={point['semantic_validation']}"
        )

    ratios = []
    for previous, current in itertools.pairwise(points):
        previous_nodes = sum(previous["actual_node_counts"].values())
        current_nodes = sum(current["actual_node_counts"].values())
        node_ratio = current_nodes / previous_nodes if previous_nodes else float("nan")
        previous_min = previous["snapshot_fingerprint_seconds"]["minimum_seconds"]
        current_min = current["snapshot_fingerprint_seconds"]["minimum_seconds"]
        duration_ratio = current_min / previous_min if previous_min else float("nan")
        ratios.append((node_ratio, duration_ratio))
        lines.append(
            f"  {previous['scale_index']} -> {current['scale_index']}: "
            f"node_size_ratio={node_ratio:.2f} snapshot_min_duration_ratio={duration_ratio:.2f}"
        )

    if len(ratios) < 1:
        conclusion = "run was insufficient to determine the expected shape"
    elif all(duration_ratio >= 1.0 for _, duration_ratio in ratios):
        conclusion = "observed cost increased with total graph size in this environment"
    else:
        conclusion = "observed cost did not increase monotonically in this run"
    lines.append("")
    lines.append(f"conclusion: {conclusion}")
    lines.append(
        "no performance SLO or maximum-duration threshold is claimed; this benchmark reports "
        "measurements only (spec §16)."
    )
    return "\n".join(lines)


def canonicalize_for_determinism(result: dict[str, Any]) -> dict[str, Any]:
    """Strips exactly the spec §15 variable fields (timestamps, timing samples/summaries, and
    execution-specific host/runtime metadata) so two clean smoke runs from the same source state
    can be compared for identical deterministic structure. `snapshot_id`/`model_revision` are
    never part of the result at all (only their cross-sample *consistency* is recorded), so there
    is nothing to strip for that field - the preferred, expected outcome the spec names."""
    canonical = {k: v for k, v in result.items() if k not in _VARIABLE_TOP_LEVEL_FIELDS}
    canonical["scale_points"] = [
        {k: v for k, v in point.items() if k not in _VARIABLE_SCALE_POINT_FIELDS}
        for point in result["scale_points"]
    ]
    return canonical
