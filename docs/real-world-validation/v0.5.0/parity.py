"""I5 Slice 5 implementation of the frozen `docs/real-world-validation/v0.5.0/public-surfaces.md` (the
parity checker the Slice 5 runs used, committed as run evidence). The as-run file had sha256
cb370ccd394b07a5a734864f3e142b754563b3e914660f722a0f4eb4d4245ac4. The committed copy differs only
in lint and formatting, with no behavior change:
- this docstring header;
- two `noqa: FURB162` comments, and one removed unused `noqa: E402`;
- one set comprehension joined onto a single line by `ruff format`.


    PYTHONPATH=$AIP_CHECKOUT uv run --project $AIP_CHECKOUT python parity.py \
        --config <target AIP config> --environment <env> --window-start <ts> --window-end <ts> \
        --service <service id> [--service ...] --out <dir>

For each service it takes the dependencies and drift answers, and evidence for every evidence ref
in them (batches of at most 20). Each answer is read from three surfaces:
1. **Service.** `ArchitectureIntelligenceService`, built via `production_service_kwargs`; the
   answer is `model_dump(mode="json")`.
2. **REST.** `GET /api/services/{id}/dependencies|drift` and `POST /api/evidence/resolve`; the
   answer is the JSON body.
3. **Negotiated MCP.** `tests/integration/independent_mcp_client.py`; the answer is the tool
   result's `structuredContent`.

The pass condition is that all three JSON values are equal. `tools/list` must also return exactly
the three frozen tool names. The Q-GRAPH zero-writes digest is taken around this script by the
caller.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import neo4j

from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.mcp.wiring import build_production_service, production_service_kwargs
from app.settings import load_config

sys.path.insert(0, str(Path(os.environ["AIP_CHECKOUT"]) / "tests" / "integration"))
import independent_mcp_client as mcp

EXPECTED_TOOLS = ["get_architecture_drift", "get_evidence", "get_service_dependencies"]
BASE_URL = "http://localhost:8000"


def _refs(value: object) -> set[str]:
    """Every string in any list under a key that ends in `evidence_refs`, anywhere in the answer."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("evidence_refs") and isinstance(item, list):
                found.update(r for r in item if isinstance(r, str))
            else:
                found |= _refs(item)
    elif isinstance(value, list):
        for item in value:
            found |= _refs(item)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--window-start", required=True)
    parser.add_argument("--window-end", required=True)
    parser.add_argument("--service", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    start = datetime.fromisoformat(args.window_start.replace("Z", "+00:00"))  # noqa: FURB162
    end = datetime.fromisoformat(args.window_end.replace("Z", "+00:00"))  # noqa: FURB162
    context = ObservationContextInput(
        environment=args.environment, window_start=start, window_end=end
    )
    context_json = context.model_dump(mode="json")

    config = load_config(args.config)
    driver = neo4j.GraphDatabase.driver(
        "bolt://localhost:7687", auth=("neo4j", os.environ["NEO4J_PASSWORD"])
    )
    service = build_production_service(driver, **production_service_kwargs(config))
    results: list[dict] = []
    ok = True
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        tools = [t["name"] for t in mcp.tools_list(client)["tools"]]
        tools_ok = tools == EXPECTED_TOOLS
        ok &= tools_ok
        results.append({"read": "tools/list", "tools": tools, "equal": tools_ok})

        def record(read: str, svc: dict, rest: dict, via_mcp: dict) -> None:
            nonlocal ok
            equal = svc == rest == via_mcp
            ok &= equal
            safe = read.replace(":", "_").replace("/", "_").replace(" ", "_")
            for surface, body in (("service", svc), ("rest", rest), ("mcp", via_mcp)):
                (args.out / f"{safe}.{surface}.json").write_text(
                    json.dumps(body, indent=2, sort_keys=True) + "\n"
                )
            snapshots = {(b.get("snapshot") or {}).get("snapshot_id") for b in (svc, rest, via_mcp)}
            results.append(
                {"read": read, "equal": equal, "snapshot_ids": sorted(map(str, snapshots))}
            )

        params = {"environment": args.environment, "from": args.window_start, "to": args.window_end}
        for service_id in args.service:
            dependencies = service.get_service_dependencies(
                ServiceDependenciesRequest(service_id=service_id, observation_context=context)
            ).model_dump(mode="json")
            record(
                f"dependencies {service_id}",
                dependencies,
                client.get(f"/api/services/{service_id}/dependencies", params=params).json(),
                mcp.call_tool(
                    client,
                    name="get_service_dependencies",
                    arguments={
                        "request": {"service_id": service_id, "observation_context": context_json}
                    },
                )["structuredContent"],
            )
            drift = service.get_architecture_drift(
                ArchitectureDriftRequest(service_id=service_id, observation_context=context)
            ).model_dump(mode="json")
            record(
                f"drift {service_id}",
                drift,
                client.get(f"/api/services/{service_id}/drift", params=params).json(),
                mcp.call_tool(
                    client,
                    name="get_architecture_drift",
                    arguments={
                        "request": {"service_id": service_id, "observation_context": context_json}
                    },
                )["structuredContent"],
            )
            refs = sorted(_refs(dependencies) | _refs(drift))
            snapshot_id = (dependencies.get("snapshot") or {}).get("snapshot_id")
            for index in range(0, len(refs), 20):
                batch = refs[index : index + 20]
                request = {"evidence_refs": batch, "snapshot_id": snapshot_id}
                record(
                    f"evidence {service_id} batch {index // 20}",
                    service.get_evidence(EvidenceRequest(**request)).model_dump(mode="json"),
                    client.post("/api/evidence/resolve", json=request).json(),
                    mcp.call_tool(client, name="get_evidence", arguments={"request": request})[
                        "structuredContent"
                    ],
                )
    driver.close()
    (args.out / "parity-summary.json").write_text(
        json.dumps({"all_equal": ok, "reads": results}, indent=2) + "\n"
    )
    print(json.dumps({"all_equal": ok, "reads": len(results)}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
