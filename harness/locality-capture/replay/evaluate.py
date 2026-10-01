"""Evaluate one clean replay state (v0.6.0 I2.6a; I1 capture runbook §§7, 9).

Runs inside the replay stack's AIP container (`/app`), builds the service exactly as the app does
(`load_config` + `build_production_service`), and prints one JSON document:

- `assessment`: `assess_local_calls` for caller `service:orders`, environment `locality-capture`, the
  whole run day (E1-E5);
- `v2_records` and `v1_calls` (E6), `snapshot_id` (E7), the accepted `operations`;
- `inventories`: each accepted capture's Pods for P1/P2 with their owner chain (gate 3).

Usage (inside the container): python /app/rehearsal-tools/evaluate.py DAY P1_UID P2_UID
"""

import json
import os
import sys

from app.architecture_intelligence.bootstrap import (
    build_production_service,
    production_service_kwargs,
)
from app.architecture_intelligence.repository import read_stable_snapshot_from_session
from app.architecture_intelligence.scoped_applicability import LocalityRequest
from app.architecture_intelligence.scoped_evidence_repository import (
    read_scoped_observed_calls,
    read_source_inventories,
)
from app.graph.repository import build_driver, open_session
from app.settings import config_path_from_env, load_config

CALLER = "service:orders"
ENVIRONMENT = "locality-capture"


def _all_v2(session) -> list[dict]:
    records, after = [], None
    while True:
        page = read_scoped_observed_calls(session, subject_id=CALLER, after_id=after)
        records.extend(record.model_dump(mode="json") for record in page.records)
        if not page.truncated:
            return records
        after = page.records[-1].id


def main(day: str, p1_uid: str, p2_uid: str) -> None:
    config = load_config(config_path_from_env())
    driver = build_driver(
        os.environ["NEO4J_URI"], os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]
    )
    service = build_production_service(driver, **production_service_kwargs(config))
    result = service.assess_local_calls(
        LocalityRequest(
            subject_service_id=CALLER, environment=ENVIRONMENT, first_day=day, last_day=day
        )
    )
    with open_session(driver, database=config.graph.database, read_only=True) as session:
        snapshot = read_stable_snapshot_from_session(
            session,
            coverage_qualification_enabled=config.telemetry.coverage.qualification_enabled,
        )
        inventories = read_source_inventories(session, pod_uids=[p1_uid, p2_uid])
        v1_calls = session.run(
            "MATCH (:Service {id: $caller})-[r:CALLS]->(o:Operation) "
            "UNWIND r.evidence_ids AS eid MATCH (e:Evidence {id: eid}) "
            "RETURN o.id AS operation, e.id AS id, e.evidence_type AS type, "
            "e.observation_count AS count ORDER BY operation, id",
            caller=CALLER,
        ).data()
        operations = [r["id"] for r in session.run("MATCH (o:Operation) RETURN o.id AS id")]
        total_nodes = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        v2 = _all_v2(session)
    driver.close()
    print(
        json.dumps(
            {
                "snapshot_id": snapshot.snapshot_id,
                "result_snapshot_id": result.snapshot_id,
                "assessment": {
                    "disposition": result.disposition,
                    "reasons": list(result.reasons),
                    "assertions": [
                        {
                            "assertion_id": a.assertion_id,
                            "operation": a.object_operation_id,
                            "workload": {
                                "kind": a.caller_workload.kind,
                                "namespace": a.caller_workload.namespace,
                                "name": a.caller_workload.name,
                                "uid": a.caller_workload.uid,
                                "cluster_uid": a.caller_workload.cluster_uid,
                            },
                            "qualification": a.qualification,
                            "declared_evidence_ids": list(a.declared_evidence_ids),
                            "v2_evidence_ids": list(a.observation.evidence_ids),
                            "captures": [c.revision for c in a.selected_captures],
                            "target_runtime_scope": a.target_runtime_scope,
                        }
                        for a in result.assertions
                    ],
                    "candidate_limitations": [
                        {
                            "v2_evidence_id": c.v2_evidence_id,
                            "disposition": c.disposition,
                            "reasons": list(c.reasons),
                        }
                        for c in result.candidate_limitations
                    ],
                },
                "v2_records": v2,
                "v1_calls": v1_calls,
                "operations": sorted(operations),
                "inventories": [
                    {
                        "revision": inventory.capture.revision,
                        "cluster_uid": inventory.capture.cluster_uid,
                        "pods": [
                            {
                                "uid": pod.captured_uid,
                                "name": pod.name,
                                "owners": [
                                    {
                                        "kind": o.workload.kind if o.workload else None,
                                        "name": o.workload.name if o.workload else None,
                                        "uid": o.workload.uid if o.workload else None,
                                    }
                                    for o in pod.owners
                                ],
                            }
                            for pod in inventory.pods
                        ],
                    }
                    for inventory in inventories
                ],
                "total_nodes": total_nodes,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main(*sys.argv[1:4])
