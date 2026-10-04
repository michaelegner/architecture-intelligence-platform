"""v0.6.0 I2.6c - the Pod-churn cost of caller-Pod-scoped v2 evidence (I2 spec §14; I1 L28; I1 v2
contract §9; decision record D15.5).

Answers one bounded question: with one Workload, one Operation and one UTC day held constant, what
does it cost as the number of distinct caller Pods N grows (each Pod replacement mints a distinct v2
record, I1 §7.1), measured against the same traffic with scoped evidence off? It records observed
values only: no threshold, no SLO, no optimization (I2 §14: "this draft invents no performance
thresholds or successful measurements").

Per scale point N, two clean graphs (scoped evidence off, then on) are built through real
production write paths - one accepted Kubernetes capture of Deployment `orders` with all N Pods
(`app.graph.importer.import_kubernetes_source`) and N CALLS facts, one per Pod, persisted in
`/v1/traces`-sized units (`app.telemetry.aggregator.persist_observation_batch`) - and every timed
read calls the real production code: `canonical_snapshot_state` + `snapshot_fingerprint`,
`ArchitectureIntelligenceService.assess_local_calls` and `read_transition_report`.

Dev/qualification tooling only, like `benchmarks/snapshot_read_cost.py`: never imported by `app/`,
never in the production image. Boots its own disposable Testcontainers Neo4j.

    uv run python -m benchmarks.scoped_churn_cost --profile smoke --candidate-sha <full-sha>
    uv run python -m benchmarks.scoped_churn_cost --profile i2 --out <path.json> --candidate-sha <full-sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import neo4j
import yaml

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.scoped_applicability import LocalityRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_kubernetes_source
from app.graph.schema import ensure_schema
from app.provenance.model import ObservedEvidence
from app.settings import ScopedEvidenceConfig
from app.sources.model import KubernetesSourceConfig
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity
from app.telemetry.scoped_attribution import ScopedCallSeed
from app.telemetry.scoped_ledger import read_transition_report
from benchmarks.i4_metadata import input_pins, metadata, producer
from benchmarks.snapshot_read_cost import collect_runtime_metadata

NAME = "scoped_churn_cost"
SCHEMA_VERSION = "aip-benchmark-scoped-churn/1"
DATABASE = "neo4j"
SCALE_POINTS = {"smoke": (0, 3), "i2": (0, 100, 1000)}
REPEATS = 5
FACTS_PER_POST = 100
STREAM_ID = "churn-benchmark"

ENVIRONMENT = "production"
DAY = "2026-09-28"
CALLER = "service:orders"
OPERATION = "operation:pricing:GET:/prices"
CLUSTER = "7f3c2a10-1b2d-4e5f-8a9b-0c1d2e3f4a5b"
NAMESPACE = "shop"
SOURCE_ID = "churn-benchmark-capture"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)


def _pod_uid(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012d}"


def _capture(root: Path, pods: int) -> KubernetesSourceConfig:
    """Deployment `orders` -> one ReplicaSet -> N Pods, as one COMPLETE CAPTURED_RESOURCE envelope."""
    root.mkdir(parents=True, exist_ok=True)
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "orders",
            "namespace": NAMESPACE,
            "uid": "d-orders",
            "resourceVersion": "1",
        },
    }
    replica_set = {
        "apiVersion": "apps/v1",
        "kind": "ReplicaSet",
        "metadata": {
            "name": "orders-rs",
            "namespace": NAMESPACE,
            "uid": "rs-orders",
            "resourceVersion": "1",
            "ownerReferences": [
                {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "orders",
                    "uid": "d-orders",
                    "controller": True,
                }
            ],
        },
    }
    pod_resources = [
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": f"orders-rs-{i:05d}",
                "namespace": NAMESPACE,
                "uid": _pod_uid(i),
                "resourceVersion": "1",
                "ownerReferences": [
                    {
                        "apiVersion": "apps/v1",
                        "kind": "ReplicaSet",
                        "name": "orders-rs",
                        "uid": "rs-orders",
                        "controller": True,
                    }
                ],
            },
        }
        for i in range(1, pods + 1)
    ]
    resources = yaml.safe_dump_all([deployment, replica_set, *pod_resources]).encode()
    (root / "resources.yaml").write_bytes(resources)
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": f"{SOURCE_ID}-snapshot",
            "revision": f"{SOURCE_ID}-{pods}",
            "producer": "aip-churn-benchmark",
            "capturedAt": f"{DAY}T12:00:00Z",
        },
        "source": {
            "configuredSourceId": SOURCE_ID,
            "configuredScopeId": f"{SOURCE_ID}-scope",
            "clusterUid": CLUSTER,
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": [NAMESPACE],
            "resourceTypes": sorted(
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
            ),
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": f"{SOURCE_ID}-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resources).hexdigest()}],
    }
    (root / "envelope.yaml").write_bytes(yaml.safe_dump(envelope).encode())
    return KubernetesSourceConfig(
        id=SOURCE_ID,
        root=root,
        envelope_relative_path="envelope.yaml",
        configured_scope_id=f"{SOURCE_ID}-scope",
        cluster_uid=CLUSTER,
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-churn-benchmark",
        authority_record=f"{SOURCE_ID}-authority",
    )


def _facts(pods: int) -> list[ObservedFactCandidate]:
    """One accepted paired CALLS per Pod: one v1 bucket for all of them, one v2 record each."""
    day = datetime.fromisoformat(DAY).replace(tzinfo=UTC)
    evidence_id = ids.observed_evidence_id(ENVIRONMENT, day, CALLER, "CALLS", OPERATION)
    facts = []
    for i in range(1, pods + 1):
        at = day + timedelta(hours=10, seconds=i)
        trace = f"{i:032x}"
        facts.append(
            ObservedFactCandidate(
                subject_id=CALLER,
                relation_type="CALLS",
                object_id=OPERATION,
                environment=ENVIRONMENT,
                timestamp=at,
                trace_id=trace,
                evidence=ObservedEvidence(
                    id=evidence_id,
                    environment=ENVIRONMENT,
                    bucket_start=day,
                    bucket_end=day + timedelta(days=1),
                    first_seen=at,
                    last_seen=at,
                    observation_count=1,
                    sample_trace_ids=[trace],
                    correlation_mode="CLIENT_SERVER",
                ),
                scoped_seed=ScopedCallSeed(
                    environment=ENVIRONMENT,
                    bucket_utc_day=DAY,
                    subject_id=CALLER,
                    object_id=OPERATION,
                    caller_cluster_uid=CLUSTER,
                    caller_pod_uid=_pod_uid(i),
                    fact_timestamp=at,
                    trace_id=trace,
                    correlation_mode="CLIENT_SERVER",
                    k8s_namespace_name=NAMESPACE,
                    k8s_pod_name=f"orders-rs-{i:05d}",
                    k8s_deployment_name="orders",
                ),
            )
        )
    return facts


def _median_ms(operation: Callable[[], object], repeats: int = REPEATS) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 3)


def _reset(driver: neo4j.Driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)


def _counts(session: neo4j.Session) -> dict[str, int]:
    def one(query: str) -> int:
        return session.run(query).single()["n"]

    return {
        "v2_records": one("MATCH (v:ScopedObservedCallV2) RETURN count(v) AS n"),
        "v1_evidence": one(
            "MATCH (e:Evidence) WHERE e.source_type = 'OPENTELEMETRY' RETURN count(e) AS n"
        ),
        "scoped_operational_nodes": one(
            "MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH 'ScopedEvidence') RETURN count(n) AS n"
        ),
        "scoped_nodes": one(
            "MATCH (n) WHERE any(l IN labels(n) WHERE l = 'ScopedObservedCallV2' OR l STARTS WITH 'ScopedEvidence') RETURN count(n) AS n"
        ),
        "scoped_relationships": one(
            "MATCH (a)-[r]->(b) WHERE any(n IN [a,b] WHERE any(l IN labels(n) WHERE l = 'ScopedObservedCallV2' OR l STARTS WITH 'ScopedEvidence')) RETURN count(r) AS n"
        ),
        "total_nodes": one("MATCH (n) RETURN count(n) AS n"),
        "total_relationships": one("MATCH ()-[r]->() RETURN count(r) AS n"),
    }


def measure_point(driver: neo4j.Driver, pods: int, work_dir: Path) -> dict[str, Any]:
    """Two clean graphs for one N: scoped evidence off, then on."""
    point: dict[str, Any] = {"pods": pods}
    facts = _facts(pods)
    units = [facts[i : i + FACTS_PER_POST] for i in range(0, len(facts), FACTS_PER_POST)]
    entities = [
        ObservedOnlyEntity(id=CALLER, label="Service", name="orders"),
        ObservedOnlyEntity(id=OPERATION, label="Operation", name="GET /prices"),
    ]
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    request = LocalityRequest(
        subject_service_id=CALLER, environment=ENVIRONMENT, first_day=DAY, last_day=DAY
    )
    for enabled in (False, True):
        _reset(driver)
        source_config = _capture(work_dir / f"{pods}-{enabled}", pods)
        capture_started = time.perf_counter()
        stats = import_kubernetes_source(driver, database=DATABASE, source_config=source_config)
        if not stats.committed:
            raise RuntimeError(f"the benchmark capture for N={pods} was not accepted")
        capture_ms = (time.perf_counter() - capture_started) * 1000
        scoped = ScopedEvidenceConfig(enabled=enabled, **{"stream-id": STREAM_ID})
        per_post = []
        for unit in units:
            started = time.perf_counter()
            persist_observation_batch(
                driver, DATABASE, ObservationBatch(entities=entities, facts=unit), scoped=scoped
            )
            per_post.append((time.perf_counter() - started) * 1000)
        with driver.session(database=DATABASE) as session:
            label = "on" if enabled else "off"
            point[label] = {
                **_counts(session),
                "accepted_facts": len(facts),
                "capture_import_ms": capture_ms,
                "source_configuration": source_config.model_dump(mode="json"),
                "persist_ms_per_post": per_post,
                "generated_inputs": input_pins(work_dir / f"{pods}-{enabled}"),
                "scoped_configuration": scoped.model_dump(mode="json"),
                "posts": len(units),
                "persist_ms_per_post_median": round(statistics.median(per_post), 3)
                if per_post
                else None,
                "snapshot_fingerprint_ms_median": _median_ms(
                    lambda: snapshot_fingerprint(
                        canonical_snapshot_state(session, coverage_qualification_enabled=True)
                    )
                ),
            }
            if enabled:
                result = service.assess_local_calls(request)
                point[label]["assess_local_calls_ms_median"] = _median_ms(
                    lambda: service.assess_local_calls(request)
                )
                point[label]["assessment"] = {
                    "assertions": len(result.assertions),
                    "candidates_on_page": sum(
                        len(a.observation.evidence_ids) for a in result.assertions
                    )
                    + len(result.candidate_limitations),
                    "truncated": result.truncated,
                }
                from app.architecture_intelligence.locality_contracts import LocalityQueryRequest
                from benchmarks.locality_cost import measure_reads

                point[label]["locality"] = measure_reads(
                    driver,
                    service,
                    LocalityQueryRequest(
                        mode="query",
                        subject_service_id=CALLER,
                        environment=ENVIRONMENT,
                        first_day=DAY,
                        last_day=DAY,
                    ),
                    PRODUCER,
                )
                point[label]["transition_report_ms_median"] = _median_ms(
                    lambda: read_transition_report(session, STREAM_ID)
                )
    return point


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def run(profile: str, driver: neo4j.Driver) -> dict[str, Any]:
    with driver.session(database=DATABASE) as session:
        neo4j_version = session.run(
            "CALL dbms.components() YIELD versions RETURN versions[0] AS v"
        ).single()["v"]
    with tempfile.TemporaryDirectory(prefix="aip-churn-") as work:
        points = [measure_point(driver, n, Path(work)) for n in SCALE_POINTS[profile]]
        from benchmarks.i4_replacement import measure_replacements

        replacements = (
            measure_replacements(driver, Path(work) / "replacement", PRODUCER)
            if profile == "i2"
            else []
        )
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
        "replacements": replacements,
    }


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    parser = argparse.ArgumentParser(prog="python -m benchmarks.scoped_churn_cost")
    parser.add_argument("--profile", choices=sorted(SCALE_POINTS), default="smoke")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    global PRODUCER
    PRODUCER = producer(args.candidate_sha)
    with Neo4jContainer(
        "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
    ) as container:
        driver = container.get_driver()
        try:
            result = run(args.profile, driver)
            assert result["commit"] == args.candidate_sha and not result["dirty_worktree"]
            result.update(
                metadata(
                    args.candidate_sha,
                    PRODUCER,
                    container,
                    {
                        "profile": args.profile,
                        "scoped_evidence": [False, True],
                        "facts_per_post": FACTS_PER_POST,
                    },
                )
            )
        finally:
            driver.close()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
