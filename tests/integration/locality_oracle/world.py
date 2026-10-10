"""Builds the graph state an I3 oracle case describes (`i3-expected-answer-matrix.md` §3), through
the real write paths wherever the oracle names one:

- **Declarations** go through the real importer (`import_source`), with the oracle's exact
  Operation ids: `service:orders` CALLS O1, and O1 is PROVIDED by `service:pricing`. Each relation
  carries its own declared evidence.
- **Captures** are real Kubernetes envelopes through the real discoverer and importer, one stable
  source per label. A capture is selectable only because the importer accepted and committed it.
- **v2 records and observed `PROVIDES`** go through the production per-POST persistence
  (`persist_observation_batch`, flag on). Every v2 span becomes one CLIENT_SERVER CALLS fact with
  its scoped seed, and every observed provider becomes an observed `PROVIDES` fact, mirroring
  `app.telemetry.adapter._calls_fact_core`. The record a seed produces must have the oracle's
  literal v2 id.
- **Disclosed direct writes**, the only ones:
  - the X05/X06 `graph_adjustments`, as the matrix discloses;
  - the generated captures beyond the first `REAL_GENERATED_CAPTURES` of a `generated_captures`
    template (X25: 2,000). Those are cloned as `SourceState` capture properties.
    `assert_generated_clone_matches_import` proves that the clone writer reproduces exactly the
    properties the real importer wrote for the generated captures it did import. (The owner
    decided this for I3.2c, because about 13 minutes of real imports per run was too costly.)
- **Rehearsal** cases replay the I2.6a recording into one clean state, as
  `test_locality_rehearsal_replay._replay` does (REHEARSAL - NOT I5).

`build` returns the pre-bound symbols (matrix §2 rule 2): `SOURCE:<label>`.
"""

from __future__ import annotations

import hashlib
import shutil
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from app.architecture_intelligence.repository import read_stable_snapshot_from_session
from app.canonical import ids
from app.canonical.model import ArchitectureModel, Operation, Relation, Service
from app.graph.importer import import_kubernetes_source, import_source
from app.graph.revision_fence import RevisionSingletonMissing, bump_revision
from app.graph.schema import ensure_schema
from app.provenance.model import ObservedEvidence, Provenance
from app.settings import ScopedEvidenceConfig
from app.sources.identity import discovery_scope_id, kubernetes_source_instance_id
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate, ObservedOnlyEntity
from app.telemetry.scoped_attribution import ScopedCallSeed
from tests.integration.test_architecture_intelligence_deployment_path_c import (
    _pod_resource,
    _replica_set_resource,
    _workload_resource,
)
from tests.integration.test_locality_rehearsal_replay import _kubernetes, _replay
from tests.integration.test_scoped_applicability import _bundle, _import, _inventory_revision

DATABASE = "neo4j"
REAL_GENERATED_CAPTURES = 3
DECLARED_CALLS_EVIDENCE = "evidence:declared:i3-oracle:calls"
DECLARED_PROVIDES_EVIDENCE = "evidence:declared:i3-oracle:provides"
_CAPTURE_KEYS = (
    "source_instance_id",
    "discovery_scope_id",
    "capture_revision",
    "capture_cluster_uid",
    "capture_scope_namespaces",
    "capture_evidence_mode",
    "capture_captured_at",
)


def clean(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)


def build(driver, tmp_path: Path, inputs: dict, *, reverse: bool = False) -> dict[str, str]:
    """One clean state for `inputs`. `reverse` permutes the import and span order (P07)."""
    if inputs["world"] == "rehearsal":
        capture = "c2" if "C2 capture" in inputs["replay"] else "c1"
        return replay_rehearsal(driver, capture)
    assert inputs["world"] == "K", inputs["world"]
    clean(driver)
    _declare(driver, inputs["declarations"])
    prebound = _captures(driver, tmp_path, inputs, reverse=reverse)
    _persist(driver, inputs, reverse=reverse)
    for operation, description in sorted(inputs.get("graph_adjustments", {}).items()):
        _adjust(driver, operation, description)
    return prebound


# --- Rehearsal -----------------------------------------------------------------------------------


def rehearsal_source(capture: str) -> str:
    config = _kubernetes(capture)
    assert config.cluster_uid is not None
    return kubernetes_source_instance_id(
        configured_kubernetes_source_id=config.id, cluster_uid=config.cluster_uid
    )


# The canonical snapshot each rehearsal replay produced, keyed by capture. A replay takes about
# 45 s (52 recorded OTLP requests through `/v1/traces`), so a case that finds the graph still in
# exactly that snapshot reuses it. Any other case cleans the graph or writes to it, which changes
# the snapshot, so a stale or mutated state is never reused.
_REPLAYED: dict[str, str] = {}


def _snapshot_id(driver) -> str | None:
    """The current canonical snapshot, or None for a graph without the revision singleton (never
    a replayed state)."""
    with driver.session(database=DATABASE) as session:
        try:
            return read_stable_snapshot_from_session(
                session, coverage_qualification_enabled=True
            ).snapshot_id
        except RevisionSingletonMissing:
            return None


def replay_rehearsal(driver, capture: str) -> dict[str, str]:
    current = _snapshot_id(driver)
    if current is None or _REPLAYED.get(capture) != current:
        _replay(driver, capture)
        _REPLAYED[capture] = _snapshot_id(driver)
    return {f"SOURCE:{capture.upper()}": rehearsal_source(capture)}


def import_rehearsal_capture(driver, tmp_path: Path, capture: str) -> None:
    """Imports one more rehearsal capture over the current state (P08: "C1, then import C2 into
    the same state"). The recorded envelopes are both first imports
    (`expectedPriorInventoryRevision: null`), so the importer would refuse C2 over C1 as a stale
    predecessor. A copy of the capture is imported instead, changing only that one field to the
    committed revision, as a capture agent re-exporting over C1 would set it. This is a
    disclosed deviation (owner decision, I3.2c). The committed fixture is never edited."""
    recorded = _kubernetes(capture)
    root = tmp_path / f"rehearsal-{capture}"
    shutil.copytree(recorded.root, root)
    envelope_path = root / recorded.envelope_relative_path
    envelope = yaml.safe_load(envelope_path.read_text(encoding="utf-8"))
    assert envelope["completeness"]["expectedPriorInventoryRevision"] is None
    envelope["completeness"]["expectedPriorInventoryRevision"] = _inventory_revision(
        driver, recorded
    )
    envelope_path.write_text(yaml.safe_dump(envelope), encoding="utf-8")
    config = recorded.model_copy(update={"root": root})
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=config)
    assert stats.committed, stats.diagnostics


# --- Declarations --------------------------------------------------------------------------------


def _operation(operation_id: str, provider: str) -> Operation:
    method, path = operation_id.removeprefix(f"operation:{provider}:").split(":", 1)
    return Operation(id=operation_id, service_id=provider, method=method, path=path)


def _declare(driver, declarations: dict) -> None:
    calls = Provenance(
        id=DECLARED_CALLS_EVIDENCE, source_type="MANIFEST", source_file="i3-oracle/calls.yaml"
    )
    provides = Provenance(
        id=DECLARED_PROVIDES_EVIDENCE,
        source_type="MANIFEST",
        source_file="i3-oracle/provides.yaml",
    )
    model = ArchitectureModel(
        services=[
            Service(id=service, name=service.removeprefix("service:"))
            for service in declarations["services"]
        ],
        operations=[
            _operation(item["id"], item["provider"]) for item in declarations["declared_operations"]
        ],
        relations=[
            *(
                Relation(
                    type="PROVIDES",
                    source_id=item["provider"],
                    target_id=item["id"],
                    evidence_ids=[provides.id],
                )
                for item in declarations["declared_operations"]
            ),
            *(
                Relation(
                    type="CALLS",
                    source_id=item["subject"],
                    target_id=item["operation"],
                    evidence_ids=[calls.id],
                )
                for item in declarations["declared_calls"]
            ),
        ],
        provenance=[calls, provides],
    )
    with driver.session(database=DATABASE) as session:
        import_source(
            session,
            source_instance_id="declared-source:i3-oracle",
            locator="i3-oracle/architecture.yaml",
            model=model,
            semantic_input_digest=hashlib.sha256(b"i3-oracle-declarations").hexdigest(),
            discovery_scope_id="declared-scope:i3-oracle",
            scope_definition_digest=hashlib.sha256(b"i3-oracle-scope").hexdigest(),
        )


# --- Captures ------------------------------------------------------------------------------------


def _expand(template: dict) -> list[int]:
    first, last = template["n"].split("..")
    count = template["count"]
    start = int(first)
    end = count - 1 if last == "count-1" else count
    return list(range(start, end + 1))


def _fmt(value: Any, n: int) -> Any:
    if isinstance(value, str):
        return value.format(n=n)
    if isinstance(value, dict):
        return {key: _fmt(item, n) for key, item in value.items()}
    if isinstance(value, list):
        return [_fmt(item, n) for item in value]
    return value


def generated_pods(inputs: dict) -> list[dict]:
    template = inputs.get("generated_pods")
    if template is None:
        return []
    return [
        {key: _fmt(template[key], n) for key in ("uid", "name", "namespace", "owner")}
        | {"capture": template["capture"]}
        for n in _expand(template)
    ]


def _resources(pods: list[dict]) -> list[dict]:
    """One Deployment and one ReplicaSet per owner, then its Pods (a captured owner chain)."""
    by_owner: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for pod in pods:
        owner = pod["owner"]
        by_owner[(owner["kind"], owner["name"], owner["uid"])].append(pod)
    resources = []
    for (kind, name, uid), owned in sorted(by_owner.items()):
        assert kind == "Deployment", kind
        namespace = owned[0]["namespace"]
        replica_set, replica_set_uid = f"{name}-rs", f"rs-{uid}"
        resources.append(_workload_resource(kind, name, uid=uid, namespace=namespace))
        resources.append(
            _replica_set_resource(
                replica_set,
                uid=replica_set_uid,
                namespace=namespace,
                owner_name=name,
                owner_uid=uid,
            )
        )
        resources.extend(
            _pod_resource(
                pod["name"],
                uid=pod["uid"],
                namespace=pod["namespace"],
                owner_kind="ReplicaSet",
                owner_name=replica_set,
                owner_uid=replica_set_uid,
            )
            for pod in owned
        )
    return resources


def _source_id(label: str) -> str:
    return f"i3-oracle-{label.lower()}"


def _spec(capture: dict, pods: list[dict]) -> dict:
    return {
        "source_id": _source_id(capture["label"]),
        "cluster_uid": capture["cluster_uid"],
        "namespaces": capture["namespaces"],
        "resources": _resources(pods),
        "captured_at": capture["captured_at"],
        "revision": capture["revision"],
        "completeness": capture["completeness"],
    }


def _captures(driver, tmp_path: Path, inputs: dict, *, reverse: bool) -> dict[str, str]:
    extra = defaultdict(list)
    for pod in generated_pods(inputs):
        extra[pod["capture"]].append(pod)
    captures = list(inputs.get("captures", ()))
    prebound = {}
    for capture in reversed(captures) if reverse else captures:
        assert capture["evidence_mode"] == "CAPTURED_RESOURCE", capture
        selector = _import(
            driver, tmp_path, **_spec(capture, capture["pods"] + extra[capture["label"]])
        )
        prebound[f"SOURCE:{capture['label']}"] = selector.source_instance_id
    template = inputs.get("generated_captures")
    if template is not None:
        generated = [_fmt(template, n) for n in _expand(template)]
        for capture in generated[:REAL_GENERATED_CAPTURES]:
            selector = _import(driver, tmp_path, **_spec(capture, []))
            prebound[f"SOURCE:{capture['label']}"] = selector.source_instance_id
        assert_generated_clone_matches_import(driver, tmp_path, generated[:REAL_GENERATED_CAPTURES])
        _clone_captures(driver, tmp_path, generated[REAL_GENERATED_CAPTURES:])
    return prebound


def build_capture(driver, tmp_path: Path, capture: dict) -> str:
    """Imports one more K capture into the current state (P04's graph change)."""
    return _import(driver, tmp_path, **_spec(capture, capture["pods"])).source_instance_id


def _clone_properties(tmp_path: Path, capture: dict) -> dict:
    """The `SourceState` capture properties the importer writes for an accepted zero-Pod capture
    (only those the I2/I3 capture read uses, plus the source identity)."""
    config = _bundle(tmp_path / "clones" / capture["label"], **_spec(capture, []))
    assert config.cluster_uid is not None
    return {
        "source_instance_id": kubernetes_source_instance_id(
            configured_kubernetes_source_id=config.id, cluster_uid=config.cluster_uid
        ),
        "discovery_scope_id": discovery_scope_id(
            configured_scope_id=config.resolved_scope_id,
            stable_target_identity=config.resolved_stable_target_identity,
        ),
        "capture_revision": capture["revision"],
        "capture_cluster_uid": capture["cluster_uid"],
        "capture_scope_namespaces": sorted(capture["namespaces"]),
        "capture_evidence_mode": capture["evidence_mode"],
        "capture_captured_at": capture["captured_at"],
    }


def assert_generated_clone_matches_import(driver, tmp_path: Path, imported: list[dict]) -> None:
    """The disclosure check: for every generated capture the real importer imported, the clone
    writer produces exactly the properties the importer wrote."""
    assert imported, "at least one generated capture must go through the real importer"
    with driver.session(database=DATABASE) as session:
        for capture in imported:
            expected = _clone_properties(tmp_path, capture)
            record = session.run(
                "MATCH (s:SourceState {source_instance_id: $id}) RETURN properties(s) AS p",
                id=expected["source_instance_id"],
            ).single()
            assert record is not None, capture["label"]
            actual = {key: record["p"].get(key) for key in _CAPTURE_KEYS}
            assert actual == expected, (capture["label"], actual, expected)


def _clone_captures(driver, tmp_path: Path, captures: list[dict]) -> None:
    rows = [_clone_properties(tmp_path, capture) for capture in captures]
    if not rows:
        return
    with driver.session(database=DATABASE) as session:
        session.execute_write(
            lambda tx: (
                tx.run(
                    "UNWIND $rows AS row CREATE (s:SourceState) SET s = row", rows=rows
                ).consume(),
                bump_revision(tx),
            )
        )


# --- v2 records and observed PROVIDES ------------------------------------------------------------


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _calls_fact(seed: ScopedCallSeed) -> ObservedFactCandidate:
    day = datetime.fromisoformat(seed.bucket_utc_day).replace(tzinfo=UTC)
    return ObservedFactCandidate(
        subject_id=seed.subject_id,
        relation_type="CALLS",
        object_id=seed.object_id,
        environment=seed.environment,
        timestamp=seed.fact_timestamp,
        trace_id=seed.trace_id,
        evidence=ObservedEvidence(
            id=ids.observed_evidence_id(
                seed.environment, day, seed.subject_id, "CALLS", seed.object_id
            ),
            environment=seed.environment,
            bucket_start=day,
            bucket_end=day + timedelta(days=1),
            first_seen=seed.fact_timestamp,
            last_seen=seed.fact_timestamp,
            observation_count=1,
            sample_trace_ids=[seed.trace_id],
            correlation_mode=seed.correlation_mode,
        ),
        scoped_seed=seed,
    )


def _provides_fact(provider: str, operation: str, *, environment: str, day: str):
    start = datetime.fromisoformat(day).replace(tzinfo=UTC)
    seen = start + timedelta(hours=9)
    trace = hashlib.sha256(f"provides|{provider}|{operation}".encode()).hexdigest()[:32]
    return ObservedFactCandidate(
        subject_id=provider,
        relation_type="PROVIDES",
        object_id=operation,
        environment=environment,
        timestamp=seen,
        trace_id=trace,
        evidence=ObservedEvidence(
            id=ids.observed_evidence_id(environment, start, provider, "PROVIDES", operation),
            environment=environment,
            bucket_start=start,
            bucket_end=start + timedelta(days=1),
            first_seen=seen,
            last_seen=seen,
            observation_count=1,
            sample_trace_ids=[trace],
            correlation_mode="CLIENT_SERVER",
        ),
    )


def _seeds(v2: dict) -> list[ScopedCallSeed]:
    resource = v2["client_resource"]
    return [
        ScopedCallSeed(
            environment=v2["environment"],
            bucket_utc_day=v2["bucket_utc_day"],
            subject_id=v2["subject_id"],
            object_id=v2["object_id"],
            caller_cluster_uid=v2["caller_cluster_uid"],
            caller_pod_uid=v2["caller_pod_uid"],
            fact_timestamp=_time(span["timestamp"]),
            trace_id=span["trace_id"],
            correlation_mode=v2["correlation_mode"],
            k8s_namespace_name=resource.get("k8s.namespace.name"),
            k8s_pod_name=resource.get("k8s.pod.name"),
            k8s_deployment_name=resource.get("k8s.deployment.name"),
        )
        for span in v2["spans"]
    ]


def generated_v2(inputs: dict) -> list[dict]:
    """One v2 input per generated Pod n (the `generated_v2` template). Its trace id is
    `sha256("gen" + n)[:32]`, a stand-in that no property case checks."""
    template = inputs.get("generated_v2")
    if template is None:
        return []
    pods = generated_pods(inputs)
    assert len(pods) == template["count"]
    records = []
    for n, pod in zip(_expand(template), pods, strict=True):
        records.append(
            {
                key: template[key]
                for key in (
                    "subject_id",
                    "object_id",
                    "environment",
                    "bucket_utc_day",
                    "caller_cluster_uid",
                    "correlation_mode",
                )
            }
            | {
                "caller_pod_uid": pod["uid"],
                "client_resource": {
                    "k8s.namespace.name": pod["namespace"],
                    "k8s.pod.name": pod["name"],
                    "k8s.deployment.name": pod["owner"]["name"],
                },
                "spans": [
                    {
                        "timestamp": span["timestamp"],
                        "trace_id": hashlib.sha256(f"gen{n}".encode()).hexdigest()[:32],
                    }
                    for span in template["spans"]
                ],
            }
        )
    return records


def v2_id(v2: dict) -> str:
    return ids.scoped_observed_call_v2_id(
        environment=v2["environment"],
        bucket_utc_day=v2["bucket_utc_day"],
        subject_id=v2["subject_id"],
        object_id=v2["object_id"],
        caller_cluster_uid=v2["caller_cluster_uid"],
        caller_pod_uid=v2["caller_pod_uid"],
    )


def _persist(driver, inputs: dict, *, reverse: bool) -> None:
    v2s = [*inputs.get("v2", ()), *generated_v2(inputs)]
    for v2 in inputs.get("v2", ()):
        assert v2_id(v2) == v2["id"], "the oracle's literal v2 id must follow from its key"
    facts = [_calls_fact(seed) for v2 in v2s for seed in _seeds(v2)]
    environment, day = "production", "2026-09-28"
    for operation, description in sorted(inputs.get("observed_providers", {}).items()):
        provider = description.split(" ", 1)[0]
        facts.append(_provides_fact(provider, operation, environment=environment, day=day))
    if reverse:
        facts.reverse()
    entities: dict[str, ObservedOnlyEntity] = {}
    for fact in facts:
        subject_label = "Service"
        entities.setdefault(
            fact.subject_id,
            ObservedOnlyEntity(id=fact.subject_id, label=subject_label, name=fact.subject_id),
        )
        entities.setdefault(
            fact.object_id,
            ObservedOnlyEntity(id=fact.object_id, label="Operation", name=fact.object_id),
        )
    if not facts:
        return
    persist_observation_batch(
        driver,
        DATABASE,
        ObservationBatch(entities=list(entities.values()), facts=facts),
        scoped=ScopedEvidenceConfig(enabled=True),
    )


# --- Disclosed graph adjustments (X05, X06) ------------------------------------------------------

_DANGLING = "PROVIDES edge whose evidence does not resolve (no accepted owner)"
_AMBIGUOUS_PREFIX = "two evidenced PROVIDES: "


def _adjust(driver, operation: str, description: str) -> None:
    """The matrix §3 direct writes: real ingestion may not produce these owner states."""
    if description == _DANGLING:
        provider = "service:" + operation.split(":")[2]
        rows = [{"provider": provider, "evidence": f"evidence:i3-oracle:dangling:{operation}"}]
        evidence = []
    elif description.startswith(_AMBIGUOUS_PREFIX):
        providers = description.removeprefix(_AMBIGUOUS_PREFIX).split(" and ")
        rows = [
            {"provider": provider, "evidence": f"evidence:i3-oracle:owner:{provider}:{operation}"}
            for provider in providers
        ]
        evidence = [row["evidence"] for row in rows]
    else:
        raise AssertionError(f"unknown graph adjustment: {description!r}")
    with driver.session(database=DATABASE) as session:
        session.execute_write(
            lambda tx: (
                tx.run(
                    "UNWIND $evidence AS id CREATE (:Evidence {id: id, source_type: 'MANIFEST', "
                    "source_file: 'i3-oracle/adjustment.yaml', evidence_type: 'DECLARED'})",
                    evidence=evidence,
                ).consume(),
                tx.run(
                    "MATCH (o:Operation {id: $operation}) UNWIND $rows AS row "
                    "MERGE (s:Service {id: row.provider}) "
                    "MERGE (s)-[r:PROVIDES]->(o) SET r.evidence_ids = [row.evidence]",
                    operation=operation,
                    rows=rows,
                ).consume(),
                bump_revision(tx),
            )
        )


# --- Pre-bound refs (matrix §2 rule 2: `REF:<what>` names the fixture's own evidence id) --------

# The oracle's Operation tags (author_expected_answers.py `OP_TAG`, matrix §3 world K).
OPERATIONS = {
    "O1": "operation:service:pricing:GET:/prices",
    "O2": "operation:service:legacy-pricing:GET:/prices",
    "O3": "operation:service:pricing:GET:/prices/{id}",
    "O4": "operation:service:catalog:GET:/items",
    "O5": "operation:service:catalog:GET:/stock",
}


def _existing_evidence(driver, evidence_id: str) -> str:
    with driver.session(database=DATABASE) as session:
        found = session.run("MATCH (e:Evidence {id: $id}) RETURN e.id AS id", id=evidence_id)
        assert found.single() is not None, f"the fixture has no Evidence {evidence_id}"
    return evidence_id


def _pod_capture_ref(driver, inputs: dict, prebound: dict[str, str], what: str) -> str:
    """`K8S_POD:<capture>/<pod>`: the Pod contribution evidence ref of that Pod in that capture.
    The pod label is matched by the K world's name suffix (`billing-6b8f5d-p9` is P9)."""
    label, pod_label = what.split("/")
    [capture] = [c for c in inputs["captures"] if c["label"] == label]
    [pod] = [p for p in capture["pods"] if p["name"].endswith(f"-{pod_label.lower()}")]
    with driver.session(database=DATABASE) as session:
        record = session.run(
            "MATCH (c:InfrastructureContribution {source_instance_id: $source, "
            "captured_resource_uid: $uid}) RETURN c.evidence_refs AS refs",
            source=prebound[f"SOURCE:{label}"],
            uid=pod["uid"],
        ).single()
    assert record is not None and len(record["refs"]) == 1, (what, record)
    return _existing_evidence(driver, record["refs"][0])


def bind_refs(driver, inputs: dict, prebound: dict[str, str], names: list[str]) -> dict[str, str]:
    """Resolves each `REF:<kind>:<what>` the request names to the built fixture's own id."""
    bound = {}
    for name in names:
        _, kind, what = name.split(":", 2)
        if kind == "DECLARED":
            assert what == "orders->pricing", what
            bound[name] = _existing_evidence(driver, DECLARED_CALLS_EVIDENCE)
        elif kind == "V1":
            subject, tag = what.split("->")
            day = datetime.fromisoformat("2026-09-28").replace(tzinfo=UTC)
            bound[name] = _existing_evidence(
                driver,
                ids.observed_evidence_id(
                    "production", day, f"service:{subject}", "CALLS", OPERATIONS[tag]
                ),
            )
        elif kind == "K8S_POD":
            bound[name] = _pod_capture_ref(driver, inputs, prebound, what)
        else:
            raise AssertionError(f"unknown REF kind: {name}")
    return bound
