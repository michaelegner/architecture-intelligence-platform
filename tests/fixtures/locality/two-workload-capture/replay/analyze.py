"""Stdlib-only analysis of a recorded `otlp.jsonl` (v0.6.0 I2.6a; I1 capture runbook §9 gates 1, 4).

Reads the recording exactly as written by the recording Collector and reports, without any AIP
code:

- gate 1: every CLIENT span's Resource carries a non-empty `k8s.pod.uid` equal to P1 or P2, a
  `k8s.cluster.uid` byte-equal to CLUSTER_UID and `deployment.environment.name=locality-capture`;
- the CLIENT/SERVER arrival order of every trace across recorded lines (in-batch, CLIENT-first,
  SERVER-first, CLIENT-only, SERVER-only), the input for gate 4;
- per (Pod UID, peer.service) CLIENT span counts, to compare with the persisted v2/v1 counts.

Usage: python analyze.py OTLP_JSONL IDENTITIES_ENV
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SERVER, CLIENT = 2, 3
_KIND = {"SPAN_KIND_SERVER": SERVER, "SPAN_KIND_CLIENT": CLIENT}


def _attributes(items) -> dict[str, str]:
    out = {}
    for item in items or []:
        value = item.get("value", {})
        out[item["key"]] = value.get("stringValue", json.dumps(value, sort_keys=True))
    return out


def main(path: str, identities_path: str) -> None:
    ids = dict(
        line.strip().split("=", 1)
        for line in Path(identities_path).read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    pods = {ids["P1_UID"]: "P1", ids["P2_UID"]: "P2"}
    positions: dict[str, dict[int, list[int]]] = defaultdict(lambda: defaultdict(list))
    client_counts: Counter = Counter()
    resources: set[str] = set()
    violations: list[str] = []
    lines = 0
    for index, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not raw.strip():
            continue
        lines += 1
        for resource_spans in json.loads(raw).get("resourceSpans", []):
            resource = _attributes(resource_spans.get("resource", {}).get("attributes"))
            for scope_spans in resource_spans.get("scopeSpans", []):
                for span in scope_spans.get("spans", []):
                    kind = span.get("kind")
                    kind = _KIND.get(kind, kind)
                    positions[span["traceId"]][kind].append(index)
                    if kind != CLIENT:
                        continue
                    resources.add(json.dumps(resource, sort_keys=True))
                    pod = resource.get("k8s.pod.uid", "")
                    if pod not in pods:
                        violations.append(f"line {index + 1}: CLIENT k8s.pod.uid {pod!r}")
                    if resource.get("k8s.cluster.uid") != ids["CLUSTER_UID"]:
                        violations.append(f"line {index + 1}: CLIENT k8s.cluster.uid differs")
                    if resource.get("deployment.environment.name") != "locality-capture":
                        violations.append(f"line {index + 1}: CLIENT environment differs")
                    peer = _attributes(span.get("attributes")).get("peer.service")
                    client_counts[f"{pods.get(pod, pod)} -> {peer}"] += 1
    orders: Counter = Counter()
    for kinds in positions.values():
        client, server = kinds.get(CLIENT), kinds.get(SERVER)
        if client and server:
            if client[0] == server[0]:
                orders["in_batch"] += 1
            elif client[0] < server[0]:
                orders["client_first"] += 1
            else:
                orders["server_first"] += 1
        elif client:
            orders["client_only"] += 1
        elif server:
            orders["server_only"] += 1
    print(
        json.dumps(
            {
                "lines": lines,
                "traces": len(positions),
                "arrival_orders": dict(sorted(orders.items())),
                "client_spans": dict(sorted(client_counts.items())),
                "client_resources": [json.loads(r) for r in sorted(resources)],
                "gate1_violations": violations,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
