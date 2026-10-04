"""v0.6.0 I3.4a - the read cost of the locality answer (I3 spec §14 "Safety/read cost", §16 DoD 11;
decision record D4: "I3.4 records cap and refusal frequencies and the read cost").

Records observed values only: no threshold, SLO or optimization. The owner decided (I3.4 planning)
that these are measured here, by calling each real phase on its own, not logged by production code.

Each point builds one clean graph through real production write paths:
- Kubernetes captures through `app.graph.importer.import_kubernetes_source`;
- accepted CALLS facts with their scoped seeds, plus an observed `PROVIDES` fact for each
  Operation's provider, through `app.telemetry.aggregator.persist_observation_batch` with scoped
  evidence on, in `/v1/traces`-sized units.

It then times, as medians of `REPEATS` runs:
- the end-to-end `ArchitectureIntelligenceService.get_service_dependencies_by_locality`;
- each phase on its own: the fenced inventory read (`read_locality_inventory`, which includes the
  snapshot state), the owner lookup (`read_provider_owners`), the projection
  (`project_locality_answer`), serialization (`model_dump_json`) and the evidence lookup
  (`resolve_scoped_locality_evidence` on at most 20 of the answer's refs).

It also records the first page's counts, a full cursor walk (pages, and the caps and refusals seen
per page) and the stable-read retries.

Points:
- Pod churn with a fixed Workload count (2 Deployments, N caller Pods);
- the Workload cap (60 Deployments);
- the membership cap (201 Operations);
- source fan-out (S accepted captures, so k = min(500, 2000 // S)), both with extra captures that
  never pair (page-size reduction) and with covering captures of the same Pods, where every source
  admits every candidate (k * S pairs, D4's 2,000-pair bound).

The `S > 2,000` refusal is not measured here: 2,001 real imports take about 13 minutes, and the
I3 oracle's X25 already executes it.

Dev/qualification tooling only, like the other benchmarks: never imported by `app/`, never in the
production image. Boots its own disposable Testcontainers Neo4j.

    uv run python -m benchmarks.locality_cost --profile smoke
    uv run python -m benchmarks.locality_cost --profile i3 --out <path.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import neo4j
import yaml

from app.architecture_intelligence import repository
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityEvidenceRequest,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityData,
)
from app.architecture_intelligence.locality_projection import (
    internal_request,
    project_locality_answer,
)
from app.architecture_intelligence.scoped_evidence_repository import (
    read_locality_inventory,
    read_provider_owners,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_kubernetes_source
from app.provenance.model import ObservedEvidence
from app.settings import ScopedEvidenceConfig
from app.sources.model import KubernetesSourceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity
from app.telemetry.scoped_attribution import ScopedCallSeed
from benchmarks.scoped_churn_cost import _git, _median_ms, _reset
from benchmarks.snapshot_read_cost import collect_runtime_metadata

NAME = "locality_cost"
SCHEMA_VERSION = "aip-benchmark-locality-cost/1"
DATABASE = "neo4j"
REPEATS = 5
FACTS_PER_POST = 100
STREAM_ID = "locality-cost-benchmark"

ENVIRONMENT = "production"
DAY = "2026-09-28"
CALLER = "service:orders"
PROVIDER = "service:pricing"
CLUSTER = "7f3c2a10-1b2d-4e5f-8a9b-0c1d2e3f4a5b"
OTHER_CLUSTER = "7f3c2a10-1b2d-4e5f-8a9b-0c1d2e3f4a5c"
NAMESPACE = "shop"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
_RESOURCE_TYPES = sorted(
    [
        "v1/Namespace",
        "v1/Pod",
        "v1/Service",
        "apps/v1/Deployment",
        "apps/v1/StatefulSet",
        "apps/v1/DaemonSet",
        "apps/v1/ReplicaSet",
        "networking.k8s.io/v1/Ingress",
    ]
)


@dataclass(frozen=True)
class Point:
    """One measured world. Pod i is owned by Deployment `w{i % workloads}` and calls every one of
    the `operations` Operations; `sources` counts every accepted capture, the main one included.

    The extra sources are either empty captures of another cluster (`covering=False`: they raise
    `S`, and so shrink `k`, but never pair), or full captures of the same Pods in the same cluster
    and namespace (`covering=True`: every source admits every candidate, so a page has `k * S`
    pairs - D4's actual candidate * source work, up to the 2,000-pair bound)."""

    name: str
    workloads: int
    pods: int
    operations: int = 1
    sources: int = 1
    covering: bool = False


PROFILES: dict[str, tuple[Point, ...]] = {
    "smoke": (
        Point("churn", workloads=2, pods=6),
        Point("fan-out", workloads=1, pods=4, sources=3),
    ),
    "i3": (
        Point("churn", workloads=2, pods=0),
        Point("churn", workloads=2, pods=100),
        Point("churn", workloads=2, pods=1000),
        Point("workload-cap", workloads=60, pods=60),
        Point("membership-cap", workloads=1, pods=1, operations=201),
        Point("fan-out", workloads=1, pods=500, sources=1),
        Point("fan-out", workloads=1, pods=500, sources=5),
        Point("fan-out", workloads=1, pods=500, sources=50),
        # D4's actual pair work: k * S = 2,000 admitted pairs on the page (PR #407 review).
        Point("covering-fan-out", workloads=1, pods=400, sources=5, covering=True),
        Point("covering-fan-out", workloads=1, pods=40, sources=50, covering=True),
    ),
}


def _pod_uid(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012d}"


def _operation(index: int) -> str:
    return f"operation:service:pricing:GET:/p{index:03d}"


def _capture(
    root: Path, *, source_id: str, cluster: str, namespace: str, point: Point | None
) -> KubernetesSourceConfig:
    """One COMPLETE CAPTURED_RESOURCE envelope: the point's Deployments, one ReplicaSet each and
    their Pods, or (with `point=None`) an empty capture that only raises `S`."""
    root.mkdir(parents=True, exist_ok=True)
    resources: list[dict] = []
    if point is not None:
        for w in range(point.workloads):
            name, uid = f"w{w:02d}", f"d-w{w:02d}"
            resources.append(
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "metadata": {
                        "name": name,
                        "namespace": namespace,
                        "uid": uid,
                        "resourceVersion": "1",
                    },
                }
            )
            resources.append(
                {
                    "apiVersion": "apps/v1",
                    "kind": "ReplicaSet",
                    "metadata": {
                        "name": f"{name}-rs",
                        "namespace": namespace,
                        "uid": f"rs-{uid}",
                        "resourceVersion": "1",
                        "ownerReferences": [
                            {
                                "apiVersion": "apps/v1",
                                "kind": "Deployment",
                                "name": name,
                                "uid": uid,
                                "controller": True,
                            }
                        ],
                    },
                }
            )
        for i in range(point.pods):
            w = i % point.workloads
            resources.append(
                {
                    "apiVersion": "v1",
                    "kind": "Pod",
                    "metadata": {
                        "name": f"w{w:02d}-rs-{i:05d}",
                        "namespace": namespace,
                        "uid": _pod_uid(i),
                        "resourceVersion": "1",
                        "ownerReferences": [
                            {
                                "apiVersion": "apps/v1",
                                "kind": "ReplicaSet",
                                "name": f"w{w:02d}-rs",
                                "uid": f"rs-d-w{w:02d}",
                                "controller": True,
                            }
                        ],
                    },
                }
            )
    data = yaml.safe_dump_all(resources).encode()
    (root / "resources.yaml").write_bytes(data)
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": f"{source_id}-snapshot",
            "revision": f"{source_id}-1",
            "producer": "aip-locality-cost-benchmark",
            "capturedAt": f"{DAY}T12:00:00Z",
        },
        "source": {
            "configuredSourceId": source_id,
            "configuredScopeId": f"{source_id}-scope",
            "clusterUid": cluster,
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {"namespaces": [namespace], "resourceTypes": _RESOURCE_TYPES},
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": f"{source_id}-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(data).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id=source_id,
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id=f"{source_id}-scope",
        cluster_uid=cluster,
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-locality-cost-benchmark",
        authority_record=f"{source_id}-authority",
    )


def _evidence(subject: str, relation: str, obj: str, at: datetime, trace: str):
    day = at.replace(hour=0, minute=0, second=0, microsecond=0)
    return ObservedEvidence(
        id=ids.observed_evidence_id(ENVIRONMENT, day, subject, relation, obj),
        environment=ENVIRONMENT,
        bucket_start=day,
        bucket_end=day + timedelta(days=1),
        first_seen=at,
        last_seen=at,
        observation_count=1,
        sample_trace_ids=[trace],
        correlation_mode="CLIENT_SERVER",
    )


def _facts(point: Point) -> list[ObservedFactCandidate]:
    """One accepted paired CALLS per (Pod, Operation), each with its scoped seed, and one observed
    `PROVIDES` per Operation so every positive Operation has a unique evidenced owner."""
    day = datetime.fromisoformat(DAY).replace(tzinfo=UTC)
    facts = []
    for op in range(point.operations):
        operation = _operation(op)
        at = day + timedelta(hours=9)
        trace = f"{op:032x}"
        facts.append(
            ObservedFactCandidate(
                subject_id=PROVIDER,
                relation_type="PROVIDES",
                object_id=operation,
                environment=ENVIRONMENT,
                timestamp=at,
                trace_id=trace,
                evidence=_evidence(PROVIDER, "PROVIDES", operation, at, trace),
            )
        )
        for i in range(point.pods):
            at = day + timedelta(hours=10, seconds=i)
            trace = f"{op:016x}{i:016x}"
            w = i % point.workloads
            facts.append(
                ObservedFactCandidate(
                    subject_id=CALLER,
                    relation_type="CALLS",
                    object_id=operation,
                    environment=ENVIRONMENT,
                    timestamp=at,
                    trace_id=trace,
                    evidence=_evidence(CALLER, "CALLS", operation, at, trace),
                    scoped_seed=ScopedCallSeed(
                        environment=ENVIRONMENT,
                        bucket_utc_day=DAY,
                        subject_id=CALLER,
                        object_id=operation,
                        caller_cluster_uid=CLUSTER,
                        caller_pod_uid=_pod_uid(i),
                        fact_timestamp=at,
                        trace_id=trace,
                        correlation_mode="CLIENT_SERVER",
                        k8s_namespace_name=NAMESPACE,
                        k8s_pod_name=f"w{w:02d}-rs-{i:05d}",
                        k8s_deployment_name=f"w{w:02d}",
                    ),
                )
            )
    return facts


def build(driver: neo4j.Driver, point: Point, work_dir: Path) -> None:
    """One clean graph for `point`, through the real importer and per-POST persistence."""
    _reset(driver)
    configs = [
        _capture(
            work_dir / "main", source_id="main", cluster=CLUSTER, namespace=NAMESPACE, point=point
        )
    ] + [
        # Covering: the same Pods, cluster and namespace, so every source pairs with every
        # candidate. Otherwise: another cluster, its own namespace and no Pods, so it is accepted
        # and counted in S but never pairs (D4).
        _capture(
            work_dir / f"g{n}",
            source_id=f"g{n:04d}",
            cluster=CLUSTER if point.covering else OTHER_CLUSTER,
            namespace=NAMESPACE if point.covering else f"gen-{n:04d}",
            point=point if point.covering else None,
        )
        for n in range(1, point.sources)
    ]
    for config in configs:
        if not import_kubernetes_source(driver, database=DATABASE, source_config=config).committed:
            raise RuntimeError(f"the benchmark capture {config.id} was not accepted")
    facts = _facts(point)
    entities = [
        ObservedOnlyEntity(id=CALLER, label="Service", name="orders"),
        ObservedOnlyEntity(id=PROVIDER, label="Service", name="pricing"),
        *(
            ObservedOnlyEntity(id=_operation(op), label="Operation", name=f"GET /p{op:03d}")
            for op in range(point.operations)
        ),
    ]
    scoped = ScopedEvidenceConfig(enabled=True, **{"stream-id": STREAM_ID})
    for start in range(0, len(facts), FACTS_PER_POST):
        persist_observation_batch(
            driver,
            DATABASE,
            ObservationBatch(entities=entities, facts=facts[start : start + FACTS_PER_POST]),
            scoped=scoped,
        )


def _query(cursor: str | None = None) -> LocalityQueryRequest:
    return LocalityQueryRequest(
        mode="query",
        subject_service_id=CALLER,
        environment=ENVIRONMENT,
        first_day=DAY,
        last_day=DAY,
        cursor=cursor,
    )


def _data(answer: LocalityAnswer) -> ServiceDependenciesByLocalityData:
    assert isinstance(answer.data, ServiceDependenciesByLocalityData)
    return answer.data


def _counts(data: ServiceDependenciesByLocalityData) -> dict[str, Any]:
    inventory = data.inventory
    return {
        "evaluated_v2_candidates": inventory.evaluated_v2_candidate_count,
        "admitted_pairs": inventory.admitted_pair_count,
        "localities": len(data.localities),
        "provider_groups": sum(len(item.provider_groups) for item in data.localities),
        "memberships": sum(len(item.assessments) for item in data.localities),
        "considered_capture_sources": inventory.considered_capture_source_count,
        "candidate_page_size": inventory.bounds.candidate_page_size,
        "i2_truncated": inventory.i2_truncated,
        "cap_reached": [cap.value for cap in inventory.cap_reached],
        "completeness": inventory.completeness.value,
    }


def walk(service: ArchitectureIntelligenceService) -> dict[str, Any]:
    """Every page of the query, by cursor, on one snapshot: the cap and refusal frequency."""
    pages, cursor, seen = [], None, []
    while True:
        answer = service.get_service_dependencies_by_locality(_query(cursor))
        if answer.data is None:
            pages.append({"refusal": answer.limitations[0].code.value})
            break
        data = _data(answer)
        seen += [candidate.v2_evidence_id for candidate in data.candidates]
        pages.append(
            {
                "candidates": len(data.candidates),
                "cap_reached": [cap.value for cap in data.inventory.cap_reached],
                "i2_truncated": data.inventory.i2_truncated,
                "outcome": answer.outcome.value,
            }
        )
        cursor = data.inventory.next_cursor
        if cursor is None:
            break
    return {
        "pages": len(pages),
        "candidates_seen": len(seen),
        "distinct_candidates_seen": len(set(seen)),
        "pages_with_a_cap": sum(1 for page in pages if page.get("cap_reached")),
        "pages_i2_truncated": sum(1 for page in pages if page.get("i2_truncated")),
        "refusals": sum(1 for page in pages if "refusal" in page),
        "per_page": pages,
    }


def _stable_read_retries(operation: Callable[[], object]) -> int:
    """Attempts minus one: each stable-read attempt reads the revision twice (spec §19.1)."""
    calls = []
    original = repository.read_revision

    def counting(session):
        calls.append(1)
        return original(session)

    repository.read_revision = counting
    try:
        operation()
    finally:
        repository.read_revision = original
    return max(len(calls) // 2 - 1, 0)


def measure_point(driver: neo4j.Driver, point: Point, work_dir: Path) -> dict[str, Any]:
    build(driver, point, work_dir)
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    query = _query()
    locality = internal_request(query)
    first = service.get_service_dependencies_by_locality(query)
    data = _data(first)
    refs = sorted(
        {
            ref
            for item in data.localities
            for assessment in item.assessments
            for ref in (*assessment.observation.evidence_ids, *assessment.capture_evidence_refs)
        }
    )[:20]
    assert first.snapshot is not None
    evidence = LocalityEvidenceRequest(
        mode="evidence",
        subject_service_id=CALLER,
        snapshot_id=first.snapshot.snapshot_id,
        refs=refs or ["evidence:none"],
    )

    with driver.session(database=DATABASE) as session:

        def fenced_read():
            return read_locality_inventory(
                session,
                locality,
                coverage_qualification_enabled=True,
                service_workload_mapping_document=None,
                after_id=None,
                read_candidates=True,
            )

        read = fenced_read()
        operations = (
            [candidate.record.object_id for candidate in read.page.result.candidates]
            if read.page is not None and read.page.result is not None
            else []
        )
        considered = read.page.considered_source_count if read.page is not None else 0
        timings = {
            "end_to_end_ms_median": _median_ms(
                lambda: service.get_service_dependencies_by_locality(query)
            ),
            "fenced_read_ms_median": _median_ms(fenced_read),
            "owner_lookup_ms_median": _median_ms(
                lambda: read_provider_owners(session, operation_ids=operations)
            ),
            "projection_ms_median": _median_ms(
                lambda: project_locality_answer(
                    query,
                    read.applicability(),
                    read.owners,
                    considered_sources=considered,
                    producer=PRODUCER,
                )
            ),
            "serialization_ms_median": _median_ms(first.model_dump_json),
            "evidence_lookup_ms_median": _median_ms(
                lambda: service.resolve_scoped_locality_evidence(evidence)
            ),
        }
    return {
        "point": point.name,
        "workloads": point.workloads,
        "pods": point.pods,
        "operations": point.operations,
        "sources": point.sources,
        "first_page": _counts(data),
        "outcome": first.outcome.value,
        "evidence_refs_looked_up": len(refs),
        "timings": timings,
        "walk": walk(service),
        "stable_read_retries": _stable_read_retries(
            lambda: service.get_service_dependencies_by_locality(query)
        ),
    }


def run(profile: str, driver: neo4j.Driver) -> dict[str, Any]:
    with driver.session(database=DATABASE) as session:
        neo4j_version = session.run(
            "CALL dbms.components() YIELD versions RETURN versions[0] AS v"
        ).single()["v"]
    with tempfile.TemporaryDirectory(prefix="aip-locality-cost-") as work:
        points = [
            measure_point(driver, point, Path(work) / f"{index:02d}")
            for index, point in enumerate(PROFILES[profile])
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": NAME,
        "profile": profile,
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _git("rev-parse", "HEAD"),
        "dirty_worktree": bool(_git("status", "--porcelain")),
        "repeats": REPEATS,
        "facts_per_post": FACTS_PER_POST,
        "runtime": collect_runtime_metadata(neo4j_version=neo4j_version),
        "points": points,
    }


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    parser = argparse.ArgumentParser(prog="python -m benchmarks.locality_cost")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="smoke")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    with Neo4jContainer(
        "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
    ) as container:
        driver = container.get_driver()
        try:
            result = run(args.profile, driver)
        finally:
            driver.close()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
