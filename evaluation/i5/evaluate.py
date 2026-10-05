"""Read one actual-capture state through production service, real REST and negotiated MCP.

Runs in the candidate AIP image. Outputs canonical semantic bytes and untouched transport
responses; no expectation is derived from those outputs. C1-bound requests are saved for C2.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from checks import (
    canonical_bytes,
    check_comparison,
    check_evidence,
    check_not_found,
    check_query,
    check_stale,
    facts_from_dossier,
)
from negotiated_mcp_client import (
    negotiated_call_body,
    negotiated_headers,
    negotiated_initialize_body,
)

from app.architecture_intelligence.bootstrap import (
    build_production_service,
    production_service_kwargs,
)
from app.architecture_intelligence.locality_contracts import (
    LOCALITY_SCHEMA_VERSION,
    LOCALITY_TOOL_NAME,
    LocalityAnswer,
    LocalityCursor,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityRequest,
    encode_cursor,
)
from app.architecture_intelligence.locality_projection import query_digest
from app.architecture_intelligence.repository import (
    canonical_snapshot_state,
    read_stable_snapshot_from_session,
)
from app.graph.repository import build_driver, open_session
from app.settings import config_path_from_env, load_config


async def main(state: str, output_path: str, dossier_path: str) -> None:
    output = Path(output_path)
    output.mkdir(parents=True, exist_ok=True)
    facts = facts_from_dossier(Path(dossier_path))
    config = load_config(config_path_from_env())
    driver = build_driver(
        os.environ["NEO4J_URI"], os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]
    )
    service = build_production_service(driver, **production_service_kwargs(config))
    origin = "http://localhost:8000"
    with open_session(driver, database=config.graph.database, read_only=True) as session:
        snapshot = read_stable_snapshot_from_session(
            session,
            coverage_qualification_enabled=config.telemetry.coverage.qualification_enabled,
            read_extra=lambda s: canonical_snapshot_state(s, coverage_qualification_enabled=True),
        )
        revision = session.run(
            "MATCH (s:AipInternalState {id:'architecture'}) RETURN s.revision AS r"
        ).single()["r"]
        v1 = session.run(
            "MATCH (:Service {id:'service:orders'})-[r:CALLS]->(o:Operation) "
            "UNWIND r.evidence_ids AS eid MATCH (e:Evidence {id:eid}) "
            "WHERE e.evidence_type = 'OBSERVED' "
            "RETURN o.id AS operation, e.id AS id, e.observation_count AS count ORDER BY operation, id"
        ).data()
    assert "scoped_observed_calls_v2" in snapshot.extra
    assert "scoped_capture_scopes_v2" in snapshot.extra
    expected_counts = {c["operation_id"]: c["count"] for c in facts["candidates"].values()}
    assert len(v1) == 2 and {r["operation"]: r["count"] for r in v1} == expected_counts
    (output / "snapshot-state.json").write_bytes(canonical_bytes(snapshot.extra))
    (output / "accounting.json").write_bytes(
        canonical_bytes({"v1": v1, "graph_revision": revision})
    )
    passed = []
    async with httpx.AsyncClient(base_url=origin, timeout=60) as client:
        headers = negotiated_headers(origin=origin)
        init = await client.post("/mcp", headers=headers, json=negotiated_initialize_body())
        (output / "mcp-initialize.transport.json").write_bytes(init.content)
        assert init.status_code == 200 and "result" in init.json()

        async def ask(case: str, request: dict) -> dict:
            (output / f"{case}.request.json").write_bytes(canonical_bytes(request))
            parsed = ServiceDependenciesByLocalityRequest.model_validate(request).root
            result = (
                service.get_service_dependencies_by_locality(parsed)
                if isinstance(parsed, LocalityQueryRequest)
                else service.resolve_scoped_locality_evidence(parsed)
            )
            direct = json.loads(result.model_dump_json())
            (output / f"{case}.service.json").write_bytes(canonical_bytes(direct))
            body = {k: v for k, v in request.items() if k not in ("mode", "subject_service_id")}
            route = "/api/services/" + request["subject_service_id"] + "/dependencies/by-locality"
            if request["mode"] == "evidence":
                route += "/evidence"
            rest = await client.post(route, json=body)
            (output / f"{case}.rest.transport.json").write_bytes(rest.content)
            assert rest.status_code == 200, (case, rest.status_code, rest.text)
            rpc = await client.post(
                "/mcp",
                headers=headers,
                json=negotiated_call_body(LOCALITY_TOOL_NAME, {"request": request}),
            )
            (output / f"{case}.mcp.transport.json").write_bytes(rpc.content)
            assert rpc.status_code == 200 and "result" in rpc.json(), (case, rpc.text)
            envelope = rpc.json()["result"]
            assert envelope["isError"] is False
            for surface, payload in (("rest", rest.json()), ("mcp", envelope["structuredContent"])):
                (output / f"{case}.{surface}.json").write_bytes(canonical_bytes(payload))
                LocalityAnswer.model_validate(payload)
                assert canonical_bytes(payload) == canonical_bytes(direct), (case, surface)
            assert direct["producer"]["build_revision"] == os.environ["AIP_BUILD_REVISION"]
            assert direct["snapshot"]["snapshot_id"] == snapshot.snapshot_id
            passed.append(case)
            return direct

        query = {
            "mode": "query",
            "subject_service_id": "service:orders",
            "environment": "locality-capture",
            "first_day": facts["day"],
            "last_day": facts["day"],
        }
        answer = await ask("inventory", query)
        check_query(answer, facts, state)
        identities = [
            {
                "cluster_uid": facts["cluster_uid"],
                "namespace": "aip-locality",
                "kind": "Deployment",
                "uid": facts["candidates"][p]["workload_uid"],
            }
            for p in ("P1", "P2")
        ]
        comparison = await ask("comparison", query | {"compare": identities})
        if state == "c1":
            check_comparison(comparison, facts)
        else:
            assert comparison["data"]["comparison"]["completeness"] == "NOT_ESTABLISHED"
            assert [s["evaluation"] for s in comparison["data"]["comparison"]["scopes"]] == [
                "UNKNOWN",
                "POSITIVE",
            ]
        refs = sorted(
            {c["v2_id"] for c in facts["candidates"].values()}
            | {r for chain in facts["chains"][state].values() for r in chain["capture_refs"]}
        )
        evidence_request = {
            "mode": "evidence",
            "subject_service_id": "service:orders",
            "snapshot_id": snapshot.snapshot_id,
            "refs": refs,
        }
        evidence = await ask("evidence", evidence_request)
        check_evidence(evidence, facts, state)
        check_not_found(
            await ask("wrong-caller", evidence_request | {"subject_service_id": "service:pricing"})
        )
        check_not_found(
            await ask("unauthorized-ref", evidence_request | {"refs": ["evidence:unauthorized:i5"]})
        )
        p1_refs = sorted(
            [
                facts["candidates"]["P1"]["v2_id"],
                *facts["chains"][state].get("P1", {}).get("capture_refs", []),
            ]
        )
        check_not_found(
            await ask(
                "wrong-operation",
                evidence_request
                | {
                    "refs": p1_refs,
                    "object_operation_id": facts["candidates"]["P2"]["operation_id"],
                },
            )
        )
        no_locality = await ask("wrong-environment", query | {"environment": "other-environment"})
        assert no_locality["data"]["localities"] == []
        assert len(no_locality["data"]["candidates"]) == 2
        assert all(c["disposition"] == "INAPPLICABLE" for c in no_locality["data"]["candidates"])
        if state == "c1":
            cursor = encode_cursor(
                LocalityCursor(
                    v=1,
                    after_id=min(c["v2_id"] for c in facts["candidates"].values()),
                    query_digest=query_digest(LocalityQueryRequest.model_validate(query)),
                    snapshot_id=snapshot.snapshot_id,
                    schema_version=LOCALITY_SCHEMA_VERSION,
                )
            )
            # Protocol-generated negative-control cursor; this small capture emits no next_cursor.
            saved = {
                "evidence": evidence_request,
                "query": query | {"snapshot_id": snapshot.snapshot_id},
                "cursor": query | {"cursor": cursor},
            }
            (output.parent / "c1-bound-requests.json").write_bytes(canonical_bytes(saved))
        else:
            saved = json.loads((output.parent / "c1-bound-requests.json").read_bytes())
            assert saved["evidence"]["snapshot_id"] != snapshot.snapshot_id
            for kind, request in saved.items():
                check_stale(await ask("stale-" + kind, request))
    driver.close()
    (output / "result.json").write_bytes(
        canonical_bytes(
            {
                "status": "CORRECT",
                "cases": passed,
                "snapshot_id": snapshot.snapshot_id,
                "pid": os.getpid(),
                "candidate_sha": os.environ["AIP_BUILD_REVISION"],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
