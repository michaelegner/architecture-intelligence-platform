"""Author/inspect acquisition metadata without importing, ingesting or querying an AIP graph.

Inventory predecessor uses the existing pure source formulas and a pinned relative replay root
(`capture`). I5.2 must use that exact root for both successive snapshots; raw files are immutable.
The actual-recording checks inspect SDK telemetry and API resource bytes, not AIP answer output.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from app.sources.identity import (
    discovery_scope_id,
    kubernetes_source_instance_id,
    scope_definition_digest,
)
from app.sources.inventory import InventoryStatus, inventory_revision
from app.sources.kubernetes_envelope import validate_kubernetes_snapshot
from app.sources.model import IngestionResult

RESOURCE_TYPES = [
    "v1/Namespace",
    "v1/Pod",
    "v1/Service",
    "apps/v1/Deployment",
    "apps/v1/StatefulSet",
    "apps/v1/DaemonSet",
    "apps/v1/ReplicaSet",
    "networking.k8s.io/v1/Ingress",
]


def registration(source: str, cluster: str) -> dict:
    return {
        "id": source,
        "root": "capture",
        "envelope_relative_path": "envelope.yaml",
        "configured_scope_id": source + "-scope",
        "cluster_uid": cluster,
        "evidence_mode": "CAPTURED_RESOURCE",
        "authorized_producer": source,
        "authority_record": source + "-self-declared-authority",
    }


def predecessor(config: dict) -> str:
    scope = discovery_scope_id(
        configured_scope_id=config["configured_scope_id"],
        stable_target_identity="urn:aip:k8s-cluster:" + config["cluster_uid"],
    )
    return inventory_revision(
        discovery_scope_id=scope,
        scope_definition_digest=scope_definition_digest(
            discovery_scope_id=scope,
            normalized_roots=[config["root"]],
            filters=["aip-locality"],
            inclusion_rules=[],
        ),
        source_instance_ids=[
            kubernetes_source_instance_id(
                configured_kubernetes_source_id=config["id"], cluster_uid=config["cluster_uid"]
            )
        ],
        tombstones=[],
        status=InventoryStatus.COMPLETE,
    )


def envelope(out: Path, state: str, at: str, source: str, cluster: str) -> None:
    import hashlib

    assert state in {"c1", "c2"}
    config = registration(source, cluster)
    path = out / state / "envelope.yaml"
    data = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": source + "-" + state,
            "revision": state + "-" + at.replace(":", "-"),
            "producer": source,
            "capturedAt": at,
        },
        "source": {
            "configuredSourceId": source,
            "configuredScopeId": config["configured_scope_id"],
            "clusterUid": cluster,
            "clusterIdentityEvidenceRef": "kube-system-namespace-uid",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {"namespaces": ["aip-locality"], "resourceTypes": RESOURCE_TYPES},
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": config["authority_record"],
            "expectedPriorInventoryRevision": None if state == "c1" else predecessor(config),
        },
        "files": [
            {
                "path": "resources.yaml",
                "sha256": hashlib.sha256((out / state / "resources.yaml").read_bytes()).hexdigest(),
            }
        ],
    }
    with path.open("x") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    if state == "c1":
        with (out / "source-registration.json").open("x") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")


def resources(out: Path, state: str) -> list[dict]:
    return [
        item
        for document in yaml.safe_load_all((out / state / "resources.yaml").read_text())
        for item in document.get("items", [document])
    ]


def owner_chain(items: list[dict], uid: str, deployment_uid: str) -> list[str]:
    by_uid = {item["metadata"]["uid"]: item for item in items}
    pod = by_uid[uid]
    assert pod["kind"] == "Pod" and pod["status"]["phase"] == "Running"
    refs = [ref for ref in pod["metadata"]["ownerReferences"] if ref.get("controller")]
    assert len(refs) == 1 and refs[0]["kind"] == "ReplicaSet"
    replica = by_uid[refs[0]["uid"]]
    refs = [ref for ref in replica["metadata"]["ownerReferences"] if ref.get("controller")]
    assert len(refs) == 1 and refs[0]["kind"] == "Deployment"
    deployment = by_uid[refs[0]["uid"]]
    assert deployment["metadata"]["uid"] == deployment_uid
    return [uid, replica["metadata"]["uid"], deployment_uid]


def verify(out: Path) -> None:
    ids = dict(line.split("=", 1) for line in (out / "identities.env").read_text().splitlines())
    analysis = json.loads((out / "analysis.json").read_text())
    assert not analysis["gate1_violations"] and analysis["lines"] > 0
    counts = analysis["client_spans"]
    assert set(counts) == {"P1 -> pricing", "P2 -> legacy-pricing"}
    assert all(count > 0 for count in counts.values())
    for resource in analysis["client_resources"]:
        symbol = "P1" if resource["k8s.pod.uid"] == ids["P1_UID"] else "P2"
        assert resource["service.name"] == "orders"
        assert resource["k8s.pod.name"] == ids[symbol + "_NAME"]
        assert resource["k8s.namespace.name"] == "aip-locality"
        assert resource["k8s.deployment.name"] == ("orders" if symbol == "P1" else "orders-canary")
    assert ids["P1_WORKLOAD_UID"] != ids["P2_WORKLOAD_UID"]
    config = json.loads((out / "source-registration.json").read_text())
    envelopes = {}
    for state in ("c1", "c2"):
        validation = validate_kubernetes_snapshot(
            root=out / state, envelope_relative_path="envelope.yaml"
        )
        assert validation.result == IngestionResult.ACCEPTED, validation.diagnostics
        data = yaml.safe_load((out / state / "envelope.yaml").read_text())
        assert data["source"]["clusterUid"] == ids["CLUSTER_UID"]
        assert data["source"]["configuredSourceId"] == config["id"]
        envelopes[state] = data
    c1, c2 = resources(out, "c1"), resources(out, "c2")
    chains = {
        "c1_p1": owner_chain(c1, ids["P1_UID"], ids["P1_WORKLOAD_UID"]),
        "c1_p2": owner_chain(c1, ids["P2_UID"], ids["P2_WORKLOAD_UID"]),
        "c2_p2": owner_chain(c2, ids["P2_UID"], ids["P2_WORKLOAD_UID"]),
    }
    assert chains["c1_p2"] == chains["c2_p2"]
    assert all(item["metadata"]["uid"] != ids["P1_UID"] for item in c2)
    assert envelopes["c1"]["completeness"]["expectedPriorInventoryRevision"] is None
    assert envelopes["c2"]["completeness"]["expectedPriorInventoryRevision"] == predecessor(config)
    stamps = [ids["TRAFFIC_START"], ids["TRAFFIC_END"]]
    stamps += [envelopes[state]["metadata"]["capturedAt"] for state in ("c1", "c2")]
    assert all(stamp.startswith(ids["DAY"] + "T") for stamp in stamps)
    start, end, c1_at, c2_at = [datetime.fromisoformat(stamp) for stamp in stamps]
    assert start <= c1_at < c2_at <= end
    assert (c1_at - start).total_seconds() >= 300
    assert (c2_at - c1_at).total_seconds() >= 120
    assert start.hour >= 1 and end.hour < 22
    # The recorded file is the Collector's accepted output; retain startup and terminal logs.
    assert (out / "collector-start.log").stat().st_size > 0
    assert (out / "collector-end.log").stat().st_size > 0
    result = {
        "label": "ACTUAL_CONTROLLED_REFERENCE",
        "acquisition_checks": "PASS",
        "owner_sign_off": "PENDING_MICHAEL_EGNER",
        "aip_evaluation": "NOT_RUN",
        "chains": chains,
        "c1_inventory_revision": predecessor(config),
        "source_registration": config,
        "client_spans": counts,
        "recorded_requests": analysis["lines"],
    }
    (out / "acquisition-checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    command, output, *args = sys.argv[1:]
    if command == "envelope":
        envelope(Path(output), *args)
    elif command == "verify":
        verify(Path(output))
    else:
        raise SystemExit("expected envelope or verify")
