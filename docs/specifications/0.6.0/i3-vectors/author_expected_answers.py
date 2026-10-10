"""Author the I3 independent expected answers (v0.6.0 I3.1c; I3 spec §14, decision record D15).

Standalone and stdlib-only: it imports nothing from `app`, so the oracle cannot be derived from
the I3 implementation it qualifies (I3 §14). Literal IDs come from the frozen rules alone:

- v2 IDs: I1 v2 contract §2 (sorted-key compact UTF-8 JSON of the ten key fields, full SHA-256);
- assertion IDs: I2 D9/D14.1 and `i2-vectors/local-assessment-id.json` (same canonical JSON).

Values that only a run can know are `{{SYMBOL}}` placeholders, matched by the procedure in
`../i3-expected-answer-matrix.md` §2. Usage, from the repository root:

    python docs/specifications/0.6.0/i3-vectors/author_expected_answers.py

writes `expected-answers.json` next to this file. Re-running must reproduce it byte for byte.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parent / "expected-answers.json"

# --- Frozen identity rules ----------------------------------------------------------------------


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def v2_id(*, subject: str, operation: str, environment: str, day: str, cluster: str, pod: str):
    return "evidence:otel:calls-scoped:v2:" + _sha(
        {
            "contract_version": 2,
            "source_type": "OPENTELEMETRY",
            "evidence_type": "OBSERVED",
            "relation_type": "CALLS",
            "environment": environment,
            "bucket_utc_day": day,
            "subject_id": subject,
            "object_id": operation,
            "caller_cluster_uid": cluster,
            "caller_pod_uid": pod,
        }
    )


def assertion_id(*, subject, operation, environment, first_day, last_day, workload) -> str:
    return "aip:local-assertion:v1:" + _sha(
        {
            "version": 1,
            "subject_service_id": subject,
            "relation_type": "CALLS",
            "object_operation_id": operation,
            "environment": environment,
            "first_utc_day": first_day,
            "last_utc_day": last_day,
            "workload": {k: workload[k] for k in ("cluster_uid", "kind", "namespace", "uid")},
        }
    )


RULES = [
    {"id": "declared-observed-qualification", "version": 1},
    {"id": "otel-calls-scoped-evidence-v2-key", "version": 1},
    {"id": "otel-client-caller-attribution", "version": 1},
    {"id": "scoped-caller-locality-applicability", "version": 1},
]

# --- Worlds -------------------------------------------------------------------------------------

# The I2.6a rehearsal recording (REHEARSAL - NOT I5), tests/fixtures/locality/rehearsal/.
REHEARSAL = {
    "subject": "service:orders",
    "environment": "locality-capture",
    "day": "2026-09-30",
    "cluster": "3c9b3e0f-1239-404a-8a45-c1195a7918f5",
    "namespace": "aip-locality",
    "pods": {
        "P1": {"uid": "1cda6fde-9aa4-409d-baff-8b0604b0f63b", "workload": "W1"},
        "P2": {"uid": "d005b4f6-5377-410d-aad7-15233aed7bac", "workload": "W2"},
    },
    "workloads": {
        "W1": {
            "name": "orders",
            "kind": "Deployment",
            "uid": "9b85fa34-e343-4bb6-ad52-3c55381408d7",
        },
        "W2": {
            "name": "orders-canary",
            "kind": "Deployment",
            "uid": "87a6fe2b-eb3b-424f-affb-6028679fd607",
        },
    },
    "captures": {
        "C1": {
            "revision": "rehearsal-c1-2026-09-30T14-38-11Z",
            "captured_at": "2026-09-30T14:38:11Z",
            "pods": ["P1", "P2"],
        },
        "C2": {
            "revision": "rehearsal-c2-2026-09-30T14-40-42Z",
            "captured_at": "2026-09-30T14:40:42Z",
            "pods": ["P2"],
        },
    },
}
O_PRICING = "operation:service:pricing:GET:/prices"
O_LEGACY = "operation:service:legacy-pricing:GET:/prices"

# World K: synthetic fixtures for the remaining rows (I3 §14 "separate negative fixtures").
K = {
    "subject": "service:orders",
    "environment": "production",
    "day": "2026-09-28",
    "namespace": "shop",
    "clusters": {
        "K1": "11111111-1111-4111-8111-000000000001",
        "K2": "11111111-1111-4111-8111-000000000002",
    },
    "workloads": {
        "W1": {
            "name": "orders",
            "kind": "Deployment",
            "uid": "aaaaaaaa-0000-4000-8000-000000000001",
        },
        "W2": {
            "name": "orders-canary",
            "kind": "Deployment",
            "uid": "aaaaaaaa-0000-4000-8000-000000000002",
        },
        "WB": {
            "name": "billing",
            "kind": "Deployment",
            "uid": "aaaaaaaa-0000-4000-8000-000000000009",
        },
    },
    "pods": {
        "P1": {
            "uid": "bbbbbbbb-0000-4000-8000-000000000001",
            "name": "orders-5d9f7c-p1",
            "workload": "W1",
            "service": "service:orders",
        },
        "P2": {
            "uid": "bbbbbbbb-0000-4000-8000-000000000002",
            "name": "orders-canary-7c4b9d-p2",
            "workload": "W2",
            "service": "service:orders",
        },
        "P9": {
            "uid": "bbbbbbbb-0000-4000-8000-000000000009",
            "name": "billing-6b8f5d-p9",
            "workload": "WB",
            "service": "service:billing",
        },
    },
}
O1 = "operation:service:pricing:GET:/prices"
O2 = "operation:service:legacy-pricing:GET:/prices"
O3 = "operation:service:pricing:GET:/prices/{id}"
O4 = "operation:service:catalog:GET:/items"
O5 = "operation:service:catalog:GET:/stock"
PROVIDER = {
    O1: "service:pricing",
    O2: "service:legacy-pricing",
    O3: "service:pricing",
    O4: None,  # owner missing (D8)
    O5: None,  # owner ambiguous (D8)
}
# Short, brace-free tags for symbol labels.
OP_TAG = {O1: "O1", O2: "O2", O3: "O3", O4: "O4", O5: "O5"}
OWNER_REASON = {O4: "PROVIDER_OWNER_MISSING", O5: "PROVIDER_OWNER_AMBIGUOUS"}
DECLARED_CALLS = {
    O1
}  # service:orders -[:CALLS]-> O1 is declared (manifest); the rest observed only

K_CAPTURES = {
    # label: cluster, namespaces, revision, captured_at, captured Pods
    "A": ("K1", ["shop"], "rev-a-1", "2026-09-28T10:00:00Z", ["P1", "P2", "P9"]),
    "B": ("K1", ["shop"], "rev-b-1", "2026-09-28T10:05:00Z", ["P2"]),
    "C": ("K2", ["billing"], "rev-c-1", "2026-09-28T10:10:00Z", []),
    "X": ("K2", ["shop"], "rev-x-1", "2026-09-28T10:15:00Z", ["P1"]),
}


def _k_capture_input(label: str) -> dict:
    cluster, namespaces, revision, captured_at, pods = K_CAPTURES[label]
    return {
        "label": label,
        "source_instance_id": f"{{{{SOURCE:{label}}}}}",
        "cluster_uid": K["clusters"][cluster],
        "namespaces": namespaces,
        "revision": revision,
        "captured_at": captured_at,
        "evidence_mode": "CAPTURED_RESOURCE",
        "completeness": "COMPLETE",
        "pods": [
            {
                "uid": K["pods"][pod]["uid"],
                "name": K["pods"][pod]["name"],
                "namespace": K["namespace"],
                "owner": {
                    "kind": K["workloads"][K["pods"][pod]["workload"]]["kind"],
                    "name": K["workloads"][K["pods"][pod]["workload"]]["name"],
                    # X captures P1's UID in another cluster (I2 D4 S04): its owner is another
                    # incarnation, so the UID differs.
                    "uid": (
                        K["workloads"][K["pods"][pod]["workload"]]["uid"]
                        if label != "X"
                        else "cccccccc-0000-4000-8000-000000000001"
                    ),
                },
            }
            for pod in pods
        ],
    }


def _k_v2(pod: str, operation: str, *, environment=None, day=None, at=("09:00:00", "09:30:00")):
    environment = environment or K["environment"]
    day = day or K["day"]
    info = K["pods"][pod]
    workload = K["workloads"][info["workload"]]
    times = [f"{day}T{t}Z" for t in at]
    traces = [_sha([pod, operation, environment, t])[:32] for t in times]
    return {
        "id": v2_id(
            subject=info["service"],
            operation=operation,
            environment=environment,
            day=day,
            cluster=K["clusters"]["K1"],
            pod=info["uid"],
        ),
        "subject_id": info["service"],
        "object_id": operation,
        "environment": environment,
        "bucket_utc_day": day,
        "caller_cluster_uid": K["clusters"]["K1"],
        "caller_pod_uid": info["uid"],
        "client_resource": {
            "k8s.namespace.name": K["namespace"],
            "k8s.pod.name": info["name"],
            "k8s.deployment.name": workload["name"],
        },
        "spans": [{"timestamp": t, "trace_id": tr} for t, tr in zip(times, traces, strict=True)],
        "correlation_mode": "CLIENT_SERVER",
        "pod": pod,
    }


# --- Answer builders ----------------------------------------------------------------------------

PRODUCER = {
    "name": "architecture-intelligence-platform",
    "version": "{{PRODUCER_VERSION}}",
    "build_revision": "{{BUILD_REVISION}}",
}
SNAPSHOT = {"snapshot_id": "{{SNAPSHOT_ID}}", "model_revision": "{{MODEL_REVISION}}"}
BOUNDS = {
    "pair_bound": 2000,
    "capture_source_bound": 2000,
    "max_localities": 50,
    "max_memberships": 200,
}


def page_size(sources: int) -> int:
    return 500 if sources == 0 else min(500, 2000 // sources)


def identity(world: dict, workload: str, cluster: str) -> dict:
    w = world["workloads"][workload]
    return {
        "cluster_uid": cluster,
        "namespace": world["namespace"],
        "kind": w["kind"],
        "uid": w["uid"],
    }


def workload_ref(world: dict, workload: str, cluster: str) -> dict:
    return {
        "workload_id": f"{{{{WORKLOAD_ID:{workload}}}}}",
        "name": world["workloads"][workload]["name"],
        **identity(world, workload, cluster),
    }


def limitation(code: str, reasons: list[str] | None = None) -> dict:
    return {"code": code, "message": "{{*}}", "reasons": reasons or []}


def envelope(mode: str, outcome: str, data: dict | None, limitations: list[dict]) -> dict:
    return {
        "schema_version": "0.6",
        "producer": PRODUCER,
        "tool": "get_service_dependencies_by_locality",
        "mode": mode,
        "outcome": outcome,
        "snapshot": SNAPSHOT,
        "data": data,
        "limitations": sorted(limitations, key=lambda item: item["code"]),
    }


def refusal(code: str, reasons: list[str] | None = None, mode: str = "query") -> dict:
    return envelope(mode, "NOT_ANSWERED", None, [limitation(code, reasons)])


class Pair:
    """One admitted pair as the expected answer shows it."""

    def __init__(
        self,
        source,
        revision,
        admission,
        phase,
        disposition,
        reasons=(),
        limitations=(),
        workload=None,
        refs=None,
    ):
        self.value = {
            "source": {"source_instance_id": source, "revision": revision},
            "admission": sorted(admission),
            "phase": phase,
            "disposition": disposition,
            "reasons": sorted(reasons),
            "limitations": sorted(limitations),
            "workload": workload,
            "evidence_refs": refs or [],
        }


def candidate(
    v2: str, disposition: str, pairs: list[dict], *, reasons=(), limitations=(), workload=None
) -> dict:
    return {
        "v2_evidence_id": v2,
        "disposition": disposition,
        "reasons": sorted(reasons),
        "limitations": sorted(limitations),
        "workload": workload,
        "pairs": pairs,
    }


def assessment(
    *,
    label,
    assertion,
    operation,
    qualification,
    v2s,
    declared,
    captures,
    refs,
    source_limitations=(),
    first="{{FIRST_SEEN:%s}}",
    last="{{LAST_SEEN:%s}}",
    lineage_complete=True,
) -> dict:
    return {
        "assertion_id": assertion,
        "assessment_id": f"{{{{ASSESSMENT:{label}}}}}",
        "object_operation_id": operation,
        "applicability": "APPLICABLE",
        "qualification": qualification,
        "observation": {
            "evidence_ids": sorted(v2s),
            "first_seen": first % label if "%s" in first else first,
            "last_seen": last % label if "%s" in last else last,
            "lineage_complete": lineage_complete,
        },
        "declared_evidence_ids": declared,
        "selected_captures": captures,
        "capture_evidence_refs": refs,
        "source_limitations": list(source_limitations),
        "rules": RULES,
    }


def locality(workload: dict, assessments: list[dict], *, lineage_complete=True) -> dict:
    groups: dict[str, list[dict]] = {}
    unresolved = []
    for item in assessments:
        provider = item.pop("_provider")
        if provider is None:
            unresolved.append(
                {"operation_id": item["object_operation_id"], "reason": item.pop("_owner_reason")}
            )
        else:
            item.pop("_owner_reason", None)
            groups.setdefault(provider, []).append(item)
    provider_groups = [
        {
            "provider_service_id": provider,
            "operation_ids": sorted(m["object_operation_id"] for m in members),
            "member_qualifications": sorted({m["qualification"] for m in members}),
            "evidence_refs": sorted(
                {
                    ref
                    for m in members
                    for ref in (
                        *m["observation"]["evidence_ids"],
                        *m["declared_evidence_ids"],
                        *m["capture_evidence_refs"],
                    )
                }
            ),
        }
        for provider, members in sorted(groups.items())
    ]
    return {
        "workload": workload,
        "assessments": sorted(assessments, key=lambda a: a["assertion_id"]),
        "provider_groups": provider_groups,
        "unresolved_owner_operations": sorted(unresolved, key=lambda u: u["operation_id"]),
        "target_runtime_scope": "UNKNOWN",
        "lineage_complete": lineage_complete,
    }


def evaluated_source(source, revision, cluster, namespaces, captured_at) -> dict:
    return {
        "source_instance_id": source,
        "revision": revision,
        "cluster_uid": cluster,
        "namespaces": namespaces,
        "evidence_mode": "CAPTURED_RESOURCE",
        "captured_at": captured_at,
    }


def _membership_map(loc: dict | None) -> dict:
    if loc is None:
        return {}
    owner = {
        op: g["provider_service_id"] for g in loc["provider_groups"] for op in g["operation_ids"]
    }
    return {
        (owner.get(a["object_operation_id"], ""), a["object_operation_id"]): {
            "qualification": a["qualification"],
            "assertion_id": a["assertion_id"],
            "assessment_id": a["assessment_id"],
        }
        for a in loc["assessments"]
    }


def comparison(scopes: list[tuple[dict, str]], locs: list[dict | None], complete: bool) -> dict:
    first, second = (_membership_map(loc) for loc in locs)
    unknown = any(evaluation == "UNKNOWN" for _, evaluation in scopes)
    in_both = [
        {
            "provider_service_id": k[0] or None,
            "operation_id": k[1],
            "first": first[k],
            "second": second[k],
        }
        for k in sorted(first.keys() & second.keys())
    ]
    return {
        "scopes": [{"workload": w, "evaluation": e} for w, e in scopes],
        "in_both": in_both,
        "only_in_first": [
            {"provider_service_id": k[0] or None, "operation_id": k[1], "side": first[k]}
            for k in sorted(first.keys() - second.keys())
        ],
        "only_in_second": [
            {"provider_service_id": k[0] or None, "operation_id": k[1], "side": second[k]}
            for k in sorted(second.keys() - first.keys())
        ],
        "qualification_differs": [
            m for m in in_both if m["first"]["qualification"] != m["second"]["qualification"]
        ],
        "completeness": "PARTIAL" if not complete else "NOT_ESTABLISHED" if unknown else "COMPLETE",
    }


def query_answer(
    *,
    context: dict,
    sources_considered: int,
    evaluated: list[dict],
    candidates: list[dict],
    localities: list[dict],
    selection=None,
    compared=None,
    extra_codes=(),
) -> dict:
    """D9/D10: a complete (single-page) evaluated query answer."""
    pairs = sum(len(c["pairs"]) for c in candidates)
    codes = set(extra_codes)
    if compared is not None and compared["completeness"] != "COMPLETE":
        codes.add("COMPARISON_INCOMPLETE")
    scopes = [*(selection or ()), *((compared or {}).get("scopes", ()))]
    if any(s["evaluation"] == "UNKNOWN" for s in scopes):
        codes.add("SELECTION_NOT_ESTABLISHED")
    if any(loc["unresolved_owner_operations"] for loc in localities):
        codes.add("PROVIDER_OWNER_UNRESOLVED")
    if not localities:
        codes.add("INSUFFICIENT_EVIDENCE")
    outcome = (
        "NOT_ANSWERED" if "INSUFFICIENT_EVIDENCE" in codes else "PARTIAL" if codes else "ANSWERED"
    )
    data = {
        "request_context": context,
        "coverage": "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE",
        "inventory": {
            "considered_capture_source_count": sources_considered,
            "evaluated_v2_candidate_count": len(candidates),
            "admitted_pair_count": pairs,
            "evaluated_sources": evaluated,
            "bounds": {**BOUNDS, "candidate_page_size": page_size(sources_considered)},
            "i2_truncated": False,
            "continuation": False,
            "cap_reached": [],
            "next_cursor": None,
            "completeness": "COMPLETE",
        },
        "candidates": sorted(candidates, key=lambda c: c["v2_evidence_id"]),
        "localities": sorted(
            localities,
            key=lambda loc: tuple(
                loc["workload"][k] for k in ("cluster_uid", "namespace", "kind", "uid")
            ),
        ),
        "selection": selection,
        "comparison": compared,
    }
    return envelope("query", outcome, data, [limitation(code) for code in codes])


def context(
    world: dict,
    *,
    operation=None,
    provider=None,
    selector=None,
    caller_localities=None,
    compare=None,
    environment=None,
    first=None,
    last=None,
) -> dict:
    return {
        "subject_service_id": world["subject"],
        "environment": environment or world["environment"],
        "first_day": first or world["day"],
        "last_day": last or world["day"],
        "relation_type": "CALLS",
        "dimensions": ["cluster", "namespace", "workload"],
        "object_operation_id": operation,
        "provider_service_id": provider,
        "source_selector": selector,
        "caller_localities": caller_localities,
        "compare": compare,
        "selection_mode": "EXPLICIT_SOURCE" if selector else "IMPLICIT_COVERING_SOURCES",
    }


def request_from(ctx: dict, **extra) -> dict:
    request = {"mode": "query"}
    for key, value in ctx.items():
        if key != "selection_mode" and value is not None:
            request[key] = value
    request.update(extra)
    return request


# --- Rehearsal cases (E1-E7, L04a) ----------------------------------------------------------------


def _rehearsal_parts(capture: str):
    r = REHEARSAL
    cap = r["captures"][capture]
    source = f"{{{{SOURCE:{capture}}}}}"
    v2 = {
        pod: v2_id(
            subject=r["subject"],
            operation=op,
            environment=r["environment"],
            day=r["day"],
            cluster=r["cluster"],
            pod=r["pods"][pod]["uid"],
        )
        for pod, op in (("P1", O_PRICING), ("P2", O_LEGACY))
    }
    candidates, localities = [], []
    for pod, op, qual, declared in (
        ("P1", O_PRICING, "CONFIRMED", ["{{DECLARED:orders->pricing}}"]),
        ("P2", O_LEGACY, "OBSERVED_ONLY", []),
    ):
        workload = r["pods"][pod]["workload"]
        if pod in cap["pods"]:
            refs = [f"{{{{...K8S:{capture}/{pod}}}}}"]
            pair = Pair(
                source,
                cap["revision"],
                ["CLUSTER_NAMESPACE", "POD_UID"],
                4,
                "APPLICABLE",
                workload=workload_ref(r, workload, r["cluster"]),
                refs=refs,
            ).value
            candidates.append(
                candidate(
                    v2[pod], "APPLICABLE", [pair], workload=workload_ref(r, workload, r["cluster"])
                )
            )
            item = assessment(
                label=f"{capture}/{workload}/{'pricing' if op == O_PRICING else 'legacy'}",
                assertion=assertion_id(
                    subject=r["subject"],
                    operation=op,
                    environment=r["environment"],
                    first_day=r["day"],
                    last_day=r["day"],
                    workload=identity(r, workload, r["cluster"]),
                ),
                operation=op,
                qualification=qual,
                v2s=[v2[pod]],
                declared=declared,
                captures=[
                    {
                        "source_instance_id": source,
                        "revision": cap["revision"],
                        "evidence_mode": "CAPTURED_RESOURCE",
                        "captured_at": cap["captured_at"],
                    }
                ],
                refs=refs,
            )
            item["_provider"] = {O_PRICING: "service:pricing", O_LEGACY: "service:legacy-pricing"}[
                op
            ]
            localities.append(locality(workload_ref(r, workload, r["cluster"]), [item]))
        else:
            pair = Pair(
                source,
                cap["revision"],
                ["CLUSTER_NAMESPACE"],
                4,
                "UNRESOLVED",
                reasons=["LOCALITY_CAPTURE_MISSING_POD"],
            ).value
            candidates.append(
                candidate(v2[pod], "UNRESOLVED", [pair], reasons=["LOCALITY_CAPTURE_MISSING_POD"])
            )
    evaluated = [
        evaluated_source(
            source, cap["revision"], r["cluster"], [r["namespace"]], cap["captured_at"]
        )
    ]
    return candidates, localities, evaluated


def rehearsal_inputs(capture: str) -> dict:
    return {
        "world": "rehearsal",
        "fixture": "tests/fixtures/locality/rehearsal/",
        "replay": f"declarations + {capture} capture + otlp.jsonl into one clean state (flag on)",
    }


def case_rehearsal(case_id, title, capture, refs, compare=False) -> dict:
    r = REHEARSAL
    candidates, localities, evaluated = _rehearsal_parts(capture)
    w1, w2 = identity(r, "W1", r["cluster"]), identity(r, "W2", r["cluster"])
    ctx = context(r, compare=[w1, w2] if compare else None)
    compared = None
    if compare:
        compared = comparison([(w1, "POSITIVE"), (w2, "POSITIVE")], localities, complete=True)
    answer = query_answer(
        context=ctx,
        sources_considered=1,
        evaluated=evaluated,
        candidates=candidates,
        localities=localities,
        compared=compared,
    )
    return {
        "id": case_id,
        "kind": "answer",
        "title": title,
        "spec_refs": refs,
        "inputs": rehearsal_inputs(capture),
        "request": request_from(ctx),
        "expected": answer,
    }


# --- World K cases --------------------------------------------------------------------------------


def k_inputs(captures: list[str], v2s: list[dict], *, owners=None, extra=None) -> dict:
    inputs = {
        "world": "K",
        "declarations": {
            "services": sorted(
                {
                    "service:orders",
                    "service:billing",
                    "service:pricing",
                    "service:legacy-pricing",
                    "service:catalog",
                    "service:inventory",
                }
            ),
            "declared_operations": [{"id": O1, "provider": "service:pricing"}],
            "declared_calls": [{"subject": "service:orders", "operation": O1}],
        },
        "observed_providers": {
            O2: "service:legacy-pricing (SERVER spans; observed PROVIDES)",
            O3: "service:pricing (SERVER spans; observed PROVIDES)",
        },
        "captures": [_k_capture_input(label) for label in captures],
        "v2": [{k: v for k, v in item.items() if k != "pod"} for item in v2s],
    }
    if owners:
        inputs["graph_adjustments"] = owners
    if extra:
        inputs.update(extra)
    return inputs


def _k_cap_tuple(label):
    cluster, namespaces, revision, captured_at, _pods = K_CAPTURES[label]
    return K["clusters"][cluster], namespaces, revision, captured_at


def k_positive(v2s: list[dict], capture="A", *, other_pairs=None, lineage=True):
    """Candidates and localities when every v2 is APPLICABLE at capture `capture`."""
    cluster, namespaces, revision, captured_at = _k_cap_tuple(capture)
    source = f"{{{{SOURCE:{capture}}}}}"
    other_pairs = other_pairs or {}
    candidates = []
    by_workload: dict[str, list[dict]] = {}
    for item in v2s:
        pod = item["pod"]
        workload = K["pods"][pod]["workload"]
        ref = workload_ref(K, workload, K["clusters"]["K1"])
        refs = [f"{{{{...K8S:{capture}/{pod}}}}}"]
        pair = Pair(
            source,
            revision,
            ["CLUSTER_NAMESPACE", "POD_UID"],
            4,
            "APPLICABLE",
            workload=ref,
            refs=refs,
        ).value
        extra = other_pairs.get(item["id"], [])
        pairs = sorted(
            [pair, *extra],
            key=lambda p: (p["source"]["source_instance_id"], p["source"]["revision"]),
        )
        candidates.append(candidate(item["id"], "APPLICABLE", pairs, workload=ref))
        by_workload.setdefault(workload, []).append((item, pair, extra))
    localities = []
    for workload, items in by_workload.items():
        by_op: dict[str, list] = {}
        for item, pair, extra in items:
            by_op.setdefault(item["object_id"], []).append((item, pair, extra))
        group = []
        for op, members in by_op.items():
            label = f"K/{workload}/{OP_TAG[op]}"
            entry = assessment(
                label=label,
                assertion=assertion_id(
                    subject=K["subject"],
                    operation=op,
                    environment=K["environment"],
                    first_day=K["day"],
                    last_day=K["day"],
                    workload=identity(K, workload, K["clusters"]["K1"]),
                ),
                operation=op,
                qualification="CONFIRMED" if op in DECLARED_CALLS else "OBSERVED_ONLY",
                v2s=[m[0]["id"] for m in members],
                declared=["{{DECLARED:orders->pricing}}"] if op in DECLARED_CALLS else [],
                captures=[
                    {
                        "source_instance_id": source,
                        "revision": revision,
                        "evidence_mode": "CAPTURED_RESOURCE",
                        "captured_at": captured_at,
                    }
                ],
                refs=sorted({r for m in members for r in m[1]["evidence_refs"]}),
                source_limitations=[
                    {"v2_evidence_id": m[0]["id"], "pair": p} for m in members for p in m[2]
                ],
                first=min(s["timestamp"] for m in members for s in m[0]["spans"]),
                last=max(s["timestamp"] for m in members for s in m[0]["spans"]),
                lineage_complete=lineage,
            )
            entry["_provider"] = PROVIDER[op]
            entry["_owner_reason"] = OWNER_REASON.get(op)
            group.append(entry)
        localities.append(
            locality(
                workload_ref(K, workload, K["clusters"]["K1"]), group, lineage_complete=lineage
            )
        )
    evaluated = [evaluated_source(source, revision, cluster, namespaces, captured_at)]
    return candidates, localities, evaluated


def k_case(
    case_id,
    title,
    refs,
    *,
    v2s,
    captures=("A",),
    ctx=None,
    owners=None,
    candidates=None,
    localities=None,
    evaluated=None,
    selection=None,
    compared=None,
    sources=None,
    request=None,
    extra_inputs=None,
) -> dict:
    ctx = ctx or context(K)
    if candidates is None:
        candidates, localities, evaluated = k_positive(v2s)
    answer = query_answer(
        context=ctx,
        sources_considered=len(captures) if sources is None else sources,
        evaluated=evaluated,
        candidates=candidates,
        localities=localities,
        selection=selection,
        compared=compared,
    )
    return {
        "id": case_id,
        "kind": "answer",
        "title": title,
        "spec_refs": refs,
        "inputs": k_inputs(list(captures), v2s, owners=owners, extra=extra_inputs),
        "request": request or request_from(ctx),
        "expected": answer,
    }


def cases() -> list[dict]:
    out: list[dict] = []
    out.append(
        case_rehearsal(
            "X01",
            "Rehearsal C1: two caller Workloads of one Service, O1 CONFIRMED, O2 OBSERVED_ONLY",
            "C1",
            ["I3 §14 row 1", "I3 §1", "E1", "E2", "E3", "L04a"],
        )
    )
    out.append(
        case_rehearsal(
            "X02",
            "Rehearsal C1 with compare [W1, W2]: positive-only differences",
            "C1",
            ["I3 §14 'Selected comparison'", "I3 §10", "D10"],
            compare=True,
        )
    )
    out.append(
        case_rehearsal(
            "X03",
            "Rehearsal C2 (Pod churn): retained P1 v2 UNRESOLVED, W2 still positive",
            "C2",
            ["I3 §14 'Pod churn C1 -> C2'", "E4", "E5"],
        )
    )

    v11 = _k_v2("P1", O1)
    v13 = _k_v2("P1", O3)
    v22 = _k_v2("P2", O2)
    v21 = _k_v2("P2", O1)
    v14 = _k_v2("P1", O4)
    v15 = _k_v2("P1", O5)
    billing = _k_v2("P9", O1)

    out.append(
        k_case(
            "X04",
            "Same provider, two Operations: one group, two members, no pooling",
            ["I3 §14 'Same provider, two Operations'", "I3 §8", "L32a", "D8"],
            v2s=[v11, v13],
        )
    )
    out.append(
        k_case(
            "X05",
            "Missing provider owner: Operation visible, no provider dependency",
            ["I3 §14 'Missing/ambiguous provider'", "L32b", "D8", "D9"],
            v2s=[v11, v14],
            owners={O4: "PROVIDES edge whose evidence does not resolve (no accepted owner)"},
        )
    )
    out.append(
        k_case(
            "X06",
            "Ambiguous provider owner: two evidenced providers",
            ["I3 §14 'Missing/ambiguous provider'", "L32b", "D8"],
            v2s=[v15],
            owners={O5: "two evidenced PROVIDES: service:catalog and service:inventory"},
        )
    )

    # X07: no v2 at all (one capture exists).
    out.append(
        k_case(
            "X07",
            "No v2: NOT_ANSWERED / INSUFFICIENT_EVIDENCE with the empty inventory",
            ["I3 §14 'No v2 / refused attribution'", "I3 §9", "D9 (Q1)", "I2 D8"],
            v2s=[],
            candidates=[],
            localities=[],
            evaluated=[],
        )
    )

    # X08: wrong day (L10b) and X09: wrong environment (L17d) stay phase-3 candidates.
    late = _k_v2("P1", O1, day="2026-09-29")
    src_a = "{{SOURCE:A}}"
    pair_late = Pair(
        src_a,
        "rev-a-1",
        ["CLUSTER_NAMESPACE", "POD_UID"],
        3,
        "INAPPLICABLE",
        reasons=["LOCALITY_OBSERVATION_TEMPORAL_MISMATCH"],
    ).value
    out.append(
        k_case(
            "X08",
            "Wrong UTC day: the candidate reaches phase 3 INAPPLICABLE, not an empty read",
            ["I3 §14 'Wrong day / environment'", "L10b", "I3 §5"],
            v2s=[late],
            candidates=[
                candidate(
                    late["id"],
                    "INAPPLICABLE",
                    [pair_late],
                    reasons=["LOCALITY_OBSERVATION_TEMPORAL_MISMATCH"],
                )
            ],
            localities=[],
            evaluated=[
                evaluated_source(
                    src_a, "rev-a-1", K["clusters"]["K1"], ["shop"], "2026-09-28T10:00:00Z"
                )
            ],
        )
    )
    staging = _k_v2("P1", O1, environment="staging")
    pair_env = Pair(
        src_a,
        "rev-a-1",
        ["CLUSTER_NAMESPACE", "POD_UID"],
        3,
        "INAPPLICABLE",
        limitations=["REQUEST_ENVIRONMENT_MISMATCH"],
    ).value
    out.append(
        k_case(
            "X09",
            "Wrong environment: phase 3 INAPPLICABLE with REQUEST_ENVIRONMENT_MISMATCH",
            ["I3 §14 'Wrong day / environment'", "L17d", "I2 D13.4"],
            v2s=[staging],
            candidates=[
                candidate(
                    staging["id"],
                    "INAPPLICABLE",
                    [pair_env],
                    limitations=["REQUEST_ENVIRONMENT_MISMATCH"],
                )
            ],
            localities=[],
            evaluated=[
                evaluated_source(
                    src_a, "rev-a-1", K["clusters"]["K1"], ["shop"], "2026-09-28T10:00:00Z"
                )
            ],
        )
    )

    # X10: two covering captures (S03) + an unrelated one that never pairs.
    pair_b = Pair(
        "{{SOURCE:B}}",
        "rev-b-1",
        ["CLUSTER_NAMESPACE"],
        4,
        "UNRESOLVED",
        reasons=["LOCALITY_CAPTURE_MISSING_POD"],
    ).value
    cands, locs, evaluated = k_positive([v11], other_pairs={v11["id"]: [pair_b]})
    b_cluster, b_ns, b_rev, b_at = _k_cap_tuple("B")
    evaluated = sorted(
        [*evaluated, evaluated_source("{{SOURCE:B}}", b_rev, b_cluster, b_ns, b_at)],
        key=lambda s: (s["source_instance_id"], s["revision"]),
    )
    out.append(
        k_case(
            "X10",
            "Two covering captures: the missing-Pod source stays a pair limitation; the "
            "unrelated capture is not a pair",
            ["I3 §14 'Two captures / source selection'", "I2 D4 S01-S03", "I3 §6", "D16.6"],
            v2s=[v11],
            captures=("A", "B", "C"),
            candidates=cands,
            localities=locs,
            evaluated=evaluated,
        )
    )

    # X11: explicit current selector.
    sel = {"source_instance_id": "{{SOURCE:A}}", "revision": "rev-a-1"}
    a_cluster, a_ns, a_rev, a_at = _k_cap_tuple("A")
    ref1 = workload_ref(K, "W1", K["clusters"]["K1"])
    pair_x = Pair(
        src_a, a_rev, ["EXPLICIT"], 4, "APPLICABLE", workload=ref1, refs=["{{...K8S:A/P1}}"]
    ).value
    cands, locs, _ = k_positive([v11])
    cands[0]["pairs"] = [pair_x]
    out.append(
        k_case(
            "X11",
            "Explicit current source selector (R3): S = 1, k = 500, EXPLICIT admission only",
            ["I3 §14 'Two captures / source selection'", "D15 R3", "D4", "I2 D13.3"],
            v2s=[v11],
            captures=("A", "B"),
            ctx=context(K, selector=sel),
            sources=1,
            candidates=cands,
            localities=locs,
            evaluated=[evaluated_source(src_a, a_rev, a_cluster, a_ns, a_at)],
        )
    )

    # X12 stale selector vs X13 implicit no-cover: the same I2 disposition (D13.3).
    no_cover = {
        "reasons": ["LOCALITY_LOCAL_COVERAGE_UNAVAILABLE"],
        "limitations": ["NO_SELECTABLE_COVERING_SOURCE"],
    }
    stale = {"source_instance_id": "{{SOURCE:A}}", "revision": "rev-a-0"}
    out.append(
        k_case(
            "X12",
            "Stale explicit selector (R3): S = 0, zero pairs, D13.3 no-cover disposition",
            ["I3 §14 'Complete and incomplete inventory'", "D15 R3", "I2 D13.3", "I3 §5"],
            v2s=[v11],
            ctx=context(K, selector=stale),
            sources=0,
            candidates=[candidate(v11["id"], "INSUFFICIENT_EVIDENCE", [], **no_cover)],
            localities=[],
            evaluated=[],
        )
    )
    out.append(
        k_case(
            "X13",
            "Implicit no-cover (I2 S06): the same disposition as the stale selector",
            ["I3 §14 'Complete and incomplete inventory'", "I2 D4 S06", "I2 D13.3"],
            v2s=[v11],
            captures=("C",),
            candidates=[candidate(v11["id"], "INSUFFICIENT_EVIDENCE", [], **no_cover)],
            localities=[],
            evaluated=[],
        )
    )

    # X14: R5 - I2 S04 conflict makes W1 EVALUATED_NO_POSITIVE; W2 positive.
    w1, w2 = identity(K, "W1", K["clusters"]["K1"]), identity(K, "W2", K["clusters"]["K1"])
    pair_x_conflict = Pair(
        "{{SOURCE:X}}",
        "rev-x-1",
        ["POD_UID"],
        4,
        "CONFLICT",
        reasons=["LOCALITY_CLUSTER_UID_CONFLICT"],
        refs=["{{...K8S:X/P1}}"],
    ).value
    cands_w2, locs_w2, ev_a = k_positive([v22])
    pair_a_w1 = Pair(
        src_a,
        a_rev,
        ["CLUSTER_NAMESPACE", "POD_UID"],
        4,
        "APPLICABLE",
        workload=ref1,
        refs=["{{...K8S:A/P1}}"],
    ).value
    conflict = candidate(
        v11["id"],
        "CONFLICT",
        sorted(
            [pair_a_w1, pair_x_conflict],
            key=lambda p: (p["source"]["source_instance_id"], p["source"]["revision"]),
        ),
        reasons=["LOCALITY_CLUSTER_UID_CONFLICT"],
    )
    x_cluster, x_ns, x_rev, x_at = _k_cap_tuple("X")
    ev_x = sorted(
        [*ev_a, evaluated_source("{{SOURCE:X}}", x_rev, x_cluster, x_ns, x_at)],
        key=lambda s: (s["source_instance_id"], s["revision"]),
    )
    ctx14 = context(K, compare=[w1, w2])
    out.append(
        k_case(
            "X14",
            "R5: an APPLICABLE pair under a CONFLICT candidate is EVALUATED_NO_POSITIVE",
            ["I3 §14 'Selected comparison'", "D15 R5", "D10", "I2 D4 S04"],
            v2s=[v11, v22],
            captures=("A", "X"),
            ctx=ctx14,
            candidates=[conflict, *cands_w2],
            localities=locs_w2,
            evaluated=ev_x,
            compared=comparison(
                [(w1, "EVALUATED_NO_POSITIVE"), (w2, "POSITIVE")], [None, locs_w2[0]], complete=True
            ),
        )
    )

    # X15: R4 - an invented identity.
    invented = {**w1, "uid": "dddddddd-0000-4000-8000-00000000dead"}
    cands, locs, ev = k_positive([v11, v22])
    loc_by = {loc["workload"]["uid"]: loc for loc in locs}
    out.append(
        k_case(
            "X15",
            "R4: an invented compare identity is UNKNOWN; comparison NOT_ESTABLISHED",
            ["I3 §14 'Selected comparison'", "D15 R4", "D10", "D16.10"],
            v2s=[v11, v22],
            ctx=context(K, compare=[invented, w2]),
            candidates=cands,
            localities=locs,
            evaluated=ev,
            compared=comparison(
                [(invented, "UNKNOWN"), (w2, "POSITIVE")], [None, loc_by[w2["uid"]]], complete=True
            ),
        )
    )

    # X16: R6b - W1 only reachable through a phase-3 INAPPLICABLE candidate.
    pair_env_w1 = Pair(
        src_a,
        a_rev,
        ["CLUSTER_NAMESPACE", "POD_UID"],
        3,
        "INAPPLICABLE",
        limitations=["REQUEST_ENVIRONMENT_MISMATCH"],
    ).value
    cands_w2, locs_w2, ev_a = k_positive([v22])
    out.append(
        k_case(
            "X16",
            "R6b: a Workload reachable only via a phase-3 INAPPLICABLE candidate is UNKNOWN",
            ["I3 §14 'Selected comparison'", "D15 R6b", "D10"],
            v2s=[staging, v22],
            ctx=context(K, compare=[w1, w2]),
            candidates=[
                candidate(
                    staging["id"],
                    "INAPPLICABLE",
                    [pair_env_w1],
                    limitations=["REQUEST_ENVIRONMENT_MISMATCH"],
                ),
                *cands_w2,
            ],
            localities=locs_w2,
            evaluated=ev_a,
            compared=comparison(
                [(w1, "UNKNOWN"), (w2, "POSITIVE")], [None, locs_w2[0]], complete=True
            ),
        )
    )

    # X17: caller_localities filter [W2]; candidates stay complete.
    cands, locs, ev = k_positive([v11, v22])
    only_w2 = [loc for loc in locs if loc["workload"]["uid"] == w2["uid"]]
    out.append(
        k_case(
            "X17",
            "caller_localities = [W2]: localities filtered, candidates complete",
            ["I3 §5", "D3", "D10"],
            v2s=[v11, v22],
            ctx=context(K, caller_localities=[w2]),
            candidates=cands,
            localities=only_w2,
            evaluated=ev,
            selection=[{"workload": w2, "evaluation": "POSITIVE"}],
        )
    )

    # X18: provider filter (D16.4).
    cands, locs, ev = k_positive([v11, v22])
    only_pricing = [loc for loc in locs if loc["workload"]["uid"] == w1["uid"]]
    out.append(
        k_case(
            "X18",
            "provider_service_id = service:pricing narrows localities (D16.4)",
            ["D3", "D16.4"],
            v2s=[v11, v22],
            ctx=context(K, provider="service:pricing"),
            candidates=cands,
            localities=only_pricing,
            evaluated=ev,
        )
    )

    # X19: the same Operation positive in both Workloads.
    cands, locs, ev = k_positive([v11, v21])
    loc_by = {loc["workload"]["uid"]: loc for loc in locs}
    out.append(
        k_case(
            "X19",
            "Same Operation in both compared Workloads: in_both, no qualification difference",
            ["I3 §10", "D10"],
            v2s=[v11, v21],
            ctx=context(K, compare=[w1, w2]),
            candidates=cands,
            localities=locs,
            evaluated=ev,
            compared=comparison(
                [(w1, "POSITIVE"), (w2, "POSITIVE")],
                [loc_by[w1["uid"]], loc_by[w2["uid"]]],
                complete=True,
            ),
        )
    )

    # Refusals (D9).
    base = request_from(context(K))
    for case_id, title, change, reason, refs in (
        (
            "X20",
            "Unsupported dimension region",
            {"dimensions": ["cluster", "region"]},
            "LOCALITY_UNSUPPORTED_DIMENSION",
            ["I3 §14 'Unsupported scope/relations'"],
        ),
        (
            "X21",
            "Unsupported dimension tenant",
            {"dimensions": ["namespace", "tenant"]},
            "LOCALITY_UNSUPPORTED_DIMENSION",
            ["I3 §14 'Unsupported scope/relations'"],
        ),
        (
            "X22",
            "Unsupported messaging relation",
            {"relation_type": "PUBLISHES_TO"},
            "LOCALITY_UNSUPPORTED_RELATION",
            ["I3 §14 'Unsupported scope/relations'"],
        ),
        (
            "X23",
            "Sub-day window",
            {"first_day": "2026-09-28T00:00:00Z", "last_day": "2026-09-28T12:00:00Z"},
            "LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION",
            ["I3 §14 'Unsupported scope/relations'"],
        ),
    ):
        out.append(
            {
                "id": case_id,
                "kind": "answer",
                "title": f"{title}: UNSUPPORTED_REQUEST",
                "spec_refs": [*refs, "D9"],
                "inputs": k_inputs(["A"], [v11]),
                "request": {**base, **change},
                "expected": refusal("UNSUPPORTED_REQUEST", [reason]),
            }
        )
    stale_snapshot = "aip:snapshot:v1:" + "0" * 64
    out.append(
        {
            "id": "X24",
            "kind": "answer",
            "title": "A snapshot_id that is not current: SNAPSHOT_NOT_AVAILABLE",
            "spec_refs": ["I3 §5", "D9", "I2 §11"],
            "inputs": k_inputs(["A"], [v11]),
            "request": {**base, "snapshot_id": stale_snapshot},
            "expected": refusal("SNAPSHOT_NOT_AVAILABLE"),
        }
    )
    out.append(
        {
            "id": "X25",
            "kind": "answer",
            "title": "R1: 2,001 accepted capture sources refuse before any candidate is read",
            "spec_refs": ["D15 R1", "D4", "D6"],
            "inputs": {
                **k_inputs(["A"], [v11]),
                "generated_captures": generated_captures(2000),
            },
            "request": base,
            "expected": refusal("RESULT_LIMIT_EXCEEDED"),
        }
    )

    # Evidence mode (D11).
    scoped = {
        "id": v11["id"],
        "subject_id": "service:orders",
        "object_id": O1,
        "environment": K["environment"],
        "bucket_utc_day": K["day"],
        "caller_cluster_uid": K["clusters"]["K1"],
        "caller_pod_uid": K["pods"]["P1"]["uid"],
        "first_seen": v11["spans"][0]["timestamp"],
        "last_seen": v11["spans"][-1]["timestamp"],
        "observation_count": len(v11["spans"]),
        "correlation_mode": "CLIENT_SERVER",
        "sample_trace_ids": sorted(s["trace_id"] for s in v11["spans"]),
        "key_rule_id": "otel-calls-scoped-evidence-v2-key",
        "key_rule_version": 1,
        "normalization_rule_id": "otel-client-caller-attribution",
        "normalization_rule_version": 1,
    }
    entries = sorted(
        [
            {
                "ref": v11["id"],
                "status": "RESOLVED",
                "ref_kind": "SCOPED_V2",
                "scoped_record": scoped,
                "capture_record": None,
            },
            {
                "ref": billing["id"],
                "status": "NOT_FOUND",
                "ref_kind": None,
                "scoped_record": None,
                "capture_record": None,
            },
        ],
        key=lambda e: e["ref"],
    )
    out.append(
        {
            "id": "X26",
            "kind": "answer",
            "title": "Evidence mode: own v2 resolves; another caller's v2 is NOT_FOUND",
            "spec_refs": ["I3 §14 'Scoped drill-down'", "D11", "D16.1"],
            "inputs": k_inputs(["A"], [v11, billing]),
            "request": {
                "mode": "evidence",
                "subject_service_id": "service:orders",
                "snapshot_id": "{{SNAPSHOT_ID}}",
                "refs": sorted([v11["id"], billing["id"]]),
            },
            "expected": envelope(
                "evidence",
                "PARTIAL",
                {
                    "subject_service_id": "service:orders",
                    "object_operation_id": None,
                    "entries": entries,
                },
                [limitation("INSUFFICIENT_EVIDENCE")],
            ),
        }
    )
    refs = ["{{REF:DECLARED:orders->pricing}}", "{{REF:K8S_POD:A/P9}}", "{{REF:V1:orders->O1}}"]
    out.append(
        {
            "id": "X27",
            "kind": "answer",
            "title": "R8: declared, legacy v1 and another caller's capture refs are all NOT_FOUND",
            "spec_refs": ["I3 §14 'Scoped drill-down'", "D15 R8", "D11"],
            "inputs": k_inputs(["A"], [v11, billing]),
            "request": {
                "mode": "evidence",
                "subject_service_id": "service:orders",
                "snapshot_id": "{{SNAPSHOT_ID}}",
                "refs": refs,
            },
            "expected": envelope(
                "evidence",
                "NOT_ANSWERED",
                {
                    "subject_service_id": "service:orders",
                    "object_operation_id": None,
                    "entries": [
                        {
                            "ref": ref,
                            "status": "NOT_FOUND",
                            "ref_kind": None,
                            "scoped_record": None,
                            "capture_record": None,
                        }
                        for ref in refs
                    ],
                },
                [limitation("INSUFFICIENT_EVIDENCE")],
            ),
        }
    )
    out.append(
        {
            "id": "X28",
            "kind": "answer",
            "title": "Evidence mode with a snapshot that is not current: SNAPSHOT_NOT_AVAILABLE",
            "spec_refs": ["I3 §14 'Scoped drill-down'", "D11"],
            "inputs": k_inputs(["A"], [v11]),
            "request": {
                "mode": "evidence",
                "subject_service_id": "service:orders",
                "snapshot_id": stale_snapshot,
                "refs": [v11["id"]],
            },
            "expected": refusal("SNAPSHOT_NOT_AVAILABLE", mode="evidence"),
        }
    )

    # Property cases: shapes too large or multi-step to state as one literal answer.
    out.extend(property_cases(v11, v22))
    out.extend(request_cases(base))
    return out


def generated_captures(count: int) -> dict:
    """`count` accepted K2 captures that pair with no candidate (other cluster, other namespace,
    no Pods): they raise S without adding pairs (D4)."""
    return {
        "count": count,
        "label": "G{n:04d}",
        "cluster_uid": K["clusters"]["K2"],
        "namespaces": ["gen-{n:04d}"],
        "revision": "rev-g{n:04d}-1",
        "captured_at": "2026-09-28T11:00:00Z",
        "evidence_mode": "CAPTURED_RESOURCE",
        "completeness": "COMPLETE",
        "pods": [],
        "n": "1..count",
    }


def generated_pods(count: int, *, workload: str | None, capture: str = "A") -> dict:
    """`count` caller Pods captured **in `capture`** (the review fix for #388): each Pod and its
    `WORKLOAD_OWNS_POD` owner are imported, so I2 resolves it. With `workload` all Pods share that
    Workload; without, Pod n is owned by its own Deployment `orders-w{n:02d}`."""
    owner = (
        {
            "kind": K["workloads"][workload]["kind"],
            "name": K["workloads"][workload]["name"],
            "uid": K["workloads"][workload]["uid"],
        }
        if workload
        else {
            "kind": "Deployment",
            "name": "orders-w{n:02d}",
            "uid": "aaaaaaaa-1000-4000-8000-{n:012d}",
        }
    )
    return {
        "count": count,
        "capture": capture,
        "uid": "bbbbbbbb-1000-4000-8000-{n:012d}",
        "name": "orders-gen-{n:04d}",
        "namespace": K["namespace"],
        "owner": owner,
        "n": "0..count-1",
    }


def generated_v2(count: int, operation: str) -> dict:
    """One v2 per generated Pod n: caller service:orders, cluster K1, namespace shop, the Pod's
    name and owner name as CLIENT Resource, one CLIENT_SERVER span at 09:00:00Z on the K day."""
    return {
        "count": count,
        "pod": "generated Pod n",
        "subject_id": "service:orders",
        "object_id": operation,
        "environment": K["environment"],
        "bucket_utc_day": K["day"],
        "caller_cluster_uid": K["clusters"]["K1"],
        "spans": [{"timestamp": f"{K['day']}T09:00:00Z", "trace_id": "sha256('gen', n)[:32]"}],
        "correlation_mode": "CLIENT_SERVER",
        "n": "0..count-1",
    }


def property_cases(v11: dict, v22: dict) -> list[dict]:
    def prop(case_id, title, refs, inputs, steps, asserts):
        return {
            "id": case_id,
            "kind": "property",
            "title": title,
            "spec_refs": refs,
            "inputs": inputs,
            "steps": steps,
            "assert": asserts,
        }

    w1_uid = K["workloads"]["W1"]["uid"]
    w2_uid = K["workloads"]["W2"]["uid"]
    one_locality = [
        {"path": "len(data.localities)", "equals": 1},
        {"path": "data.localities[0].workload.uid", "equals": w1_uid},
        {"path": "len(data.localities[0].assessments)", "equals": 1},
        {"path": "data.localities[0].assessments[0].object_operation_id", "equals": O1},
    ]
    return [
        prop(
            "P01",
            "R2: S = 5 and 500 resolvable candidates read k = 400",
            ["D15 R2", "D4", "D5"],
            {
                **k_inputs(["A"], []),
                "generated_captures": generated_captures(4),
                "generated_pods": generated_pods(500, workload="W1"),
                "generated_v2": generated_v2(500, O1),
            },
            ["query without cursor"],
            [
                {"path": "data.inventory.considered_capture_source_count", "equals": 5},
                {"path": "data.inventory.bounds.candidate_page_size", "equals": 400},
                {"path": "data.inventory.evaluated_v2_candidate_count", "equals": 400},
                {"path": "data.inventory.admitted_pair_count", "equals": 400},
                {"path": "len(data.inventory.evaluated_sources)", "equals": 1},
                {"path": "data.candidates[*].disposition", "all_equal": "APPLICABLE"},
                {"path": "data.inventory.i2_truncated", "equals": True},
                {"path": "data.inventory.continuation", "equals": False},
                {"path": "data.inventory.completeness", "equals": "PARTIAL"},
                {"path": "outcome", "equals": "PARTIAL"},
                {
                    "path": "cursor(data.inventory.next_cursor).after_id",
                    "equals_expr": "the 400th generated v2 ID in ascending order",
                },
                *one_locality,
                {
                    "path": "len(data.localities[0].assessments[0].observation.evidence_ids)",
                    "equals": 400,
                },
                {"path": "data.localities[*].lineage_complete", "all_equal": False},
            ],
        ),
        prop(
            "P02",
            "I2 page boundary: 501 resolvable candidates, two pages, one snapshot",
            ["I3 §14 'Complete and incomplete inventory'", "I3 §7", "D5", "D7", "D16.11"],
            {
                **k_inputs(["A"], []),
                "generated_pods": generated_pods(501, workload="W1"),
                "generated_v2": generated_v2(501, O1),
            },
            ["page 1: query", "page 2: same query + page 1 next_cursor"],
            [
                {"step": 1, "path": "data.inventory.evaluated_v2_candidate_count", "equals": 500},
                {"step": 1, "path": "data.inventory.i2_truncated", "equals": True},
                {"step": 1, "path": "data.candidates[*].disposition", "all_equal": "APPLICABLE"},
                *({**item, "step": 1} for item in one_locality),
                {
                    "step": 1,
                    "path": "len(data.localities[0].assessments[0].observation.evidence_ids)",
                    "equals": 500,
                },
                {"step": 1, "path": "data.localities[*].lineage_complete", "all_equal": False},
                {"step": 2, "path": "data.inventory.evaluated_v2_candidate_count", "equals": 1},
                {"step": 2, "path": "data.inventory.continuation", "equals": True},
                {"step": 2, "path": "data.inventory.next_cursor", "equals": None},
                {"step": 2, "path": "data.inventory.completeness", "equals": "PARTIAL"},
                {"step": 2, "path": "outcome", "equals": "PARTIAL"},
                {"step": 2, "path": "limitations[*].code", "contains": "INVENTORY_INCOMPLETE"},
                *({**item, "step": 2} for item in one_locality),
                {"step": 2, "path": "data.localities[*].lineage_complete", "all_equal": False},
                {"step": 2, "path": "snapshot.snapshot_id", "equals_step": 1},
                {
                    "path": "union of candidates[*].v2_evidence_id over both pages",
                    "equals_expr": "all 501 generated v2 IDs, each exactly once",
                },
            ],
        ),
        prop(
            "P03",
            "I3 Workload cap splits the page although I2 truncated = false",
            ["I3 §14 'I2 page or I3 presentation cap'", "D4", "D7", "D16.11"],
            {
                **k_inputs(["A"], []),
                "generated_pods": generated_pods(60, workload=None),
                "generated_v2": generated_v2(60, O1),
            },
            ["page 1: query", "page 2: query + page 1 next_cursor"],
            [
                {"step": 1, "path": "data.inventory.i2_truncated", "equals": False},
                {"step": 1, "path": "data.inventory.cap_reached", "equals": ["WORKLOADS"]},
                {"step": 1, "path": "data.inventory.evaluated_v2_candidate_count", "equals": 50},
                {"step": 1, "path": "len(data.localities)", "equals": 50},
                {"step": 1, "path": "data.localities[*].lineage_complete", "all_equal": False},
                {"step": 1, "path": "outcome", "equals": "PARTIAL"},
                {"step": 2, "path": "data.inventory.continuation", "equals": True},
                {"step": 2, "path": "data.inventory.evaluated_v2_candidate_count", "equals": 10},
                {"step": 2, "path": "len(data.localities)", "equals": 10},
                {"step": 2, "path": "data.inventory.next_cursor", "equals": None},
                {"step": 2, "path": "data.inventory.completeness", "equals": "PARTIAL"},
                {
                    "path": "union of localities[*].workload.uid over both pages",
                    "equals_expr": "all 60 generated Workload UIDs, each exactly once",
                },
            ],
        ),
        prop(
            "P04",
            "Cursor misuse: other query or changed snapshot",
            ["I3 §7", "D5", "D9"],
            {
                **k_inputs(["A"], []),
                "generated_pods": generated_pods(501, workload="W1"),
                "generated_v2": generated_v2(501, O1),
            },
            [
                "page 1",
                "page 2 with object_operation_id added and the page-1 cursor",
                "graph change (import capture B)",
                "page 2 with the page-1 cursor",
            ],
            [
                {"step": 1, "path": "len(data.localities)", "equals": 1},
                {"step": 2, "path": "limitations[0].code", "equals": "CURSOR_QUERY_MISMATCH"},
                {"step": 2, "path": "data", "equals": None},
                {"step": 4, "path": "limitations[0].code", "equals": "SNAPSHOT_NOT_AVAILABLE"},
                {"step": 4, "path": "data", "equals": None},
            ],
        ),
        prop(
            "P05",
            "R7: capture refs of a positive assessment resolve in evidence mode only",
            ["D15 R7", "D11", "I3 §12"],
            {**k_inputs(["A"], [v11]), "note": "no Service-level DEPLOYED_AS is declared"},
            [
                "query; take every ref of the bound set {{...K8S:A/P1}}",
                "evidence mode with those refs",
                "legacy get_evidence with the same refs",
            ],
            [
                {"step": 1, "path": "len(data.localities)", "equals": 1},
                {"step": 2, "path": "len(data.entries)", "at_least": 1},
                {"step": 2, "path": "data.entries[*].status", "all_equal": "RESOLVED"},
                {
                    "step": 2,
                    "path": "data.entries[*].ref_kind",
                    "subset_of": ["OWNER_CAPTURE", "POD_CAPTURE"],
                },
                {
                    "step": 2,
                    "path": "data.entries[*].capture_record.source_type",
                    "all_equal": "KUBERNETES",
                },
                {
                    "step": 3,
                    "path": "legacy get_evidence result",
                    "equals_expr": "none of the refs resolved (not deployment-reachable)",
                },
            ],
        ),
        prop(
            "P06",
            "v2 stays isolated from legacy readers",
            ["I3 §14 'Scoped drill-down'", "I3 §12", "I2 D1", "D11"],
            k_inputs(["A"], [v11, v22]),
            [
                "legacy get_evidence / POST /api/evidence/resolve / GET /api/evidence with v2 IDs",
                "NL question naming the v2 IDs",
                "get_service_dependencies",
            ],
            [
                {"path": "every legacy read", "equals_expr": "no v2 ID, record or field returned"},
                {
                    "path": "get_service_dependencies evidence_refs",
                    "equals_expr": "contain no v2 ID",
                },
            ],
        ),
        prop(
            "P07",
            "Replay and permutation",
            ["I3 §14 'Replay and permutation'", "I3 §11"],
            {"world": "K", "inputs_of": ["X10", "X14", "X19"]},
            ["build each fixture twice with permuted import/span order", "same request"],
            [
                {
                    "path": "canonical answer bytes without producer",
                    "equals_expr": "identical across permutations",
                }
            ],
        ),
        prop(
            "P08",
            "C1 -> C2: a C1-snapshot request after C2 is imported",
            ["I3 §14 'Pod churn C1 -> C2'", "I3 §10", "E7"],
            {"world": "rehearsal", "replay": "C1, then import C2 into the same state"},
            [
                "query at C1 (bind snapshot)",
                "import C2",
                "query with the C1 snapshot_id",
                "query without snapshot_id",
            ],
            [
                {"step": 1, "path": "len(data.localities)", "equals": 2},
                {"step": 3, "path": "limitations[0].code", "equals": "SNAPSHOT_NOT_AVAILABLE"},
                {"step": 4, "path": "snapshot.snapshot_id", "not_equals_step": 1},
            ],
        ),
        prop(
            "P09",
            "R6: the R5 construction on a PARTIAL inventory is UNKNOWN, not EVALUATED_NO_POSITIVE",
            ["D15 R6", "D10", "D7"],
            {
                **k_inputs(["A", "X"], [v11, v22]),
                "generated_pods": generated_pods(500, workload="W2"),
                "generated_v2": generated_v2(500, O2),
            },
            ["query with compare [W1, W2] (502 candidates, S = 2, k = 500: page 1 is PARTIAL)"],
            [
                {"path": "data.inventory.i2_truncated", "equals": True},
                {"path": "data.inventory.completeness", "equals": "PARTIAL"},
                {"path": "data.localities[*].workload.uid", "contains": w2_uid},
                {"path": "data.comparison.scopes[0].evaluation", "equals": "UNKNOWN"},
                {"path": "data.comparison.scopes[1].evaluation", "equals": "POSITIVE"},
                {"path": "data.comparison.completeness", "equals": "PARTIAL"},
                {"path": "limitations[*].code", "contains": "SELECTION_NOT_ESTABLISHED"},
                {"path": "limitations[*].code", "contains": "COMPARISON_INCOMPLETE"},
            ],
        ),
    ]


def request_cases(base: dict) -> list[dict]:
    w = identity(K, "W1", K["clusters"]["K1"])
    w2 = identity(K, "W2", K["clusters"]["K1"])

    def bad(case_id, title, request):
        return {
            "id": case_id,
            "kind": "request",
            "title": title,
            "spec_refs": ["D3", "D9"],
            "request": request,
            "expected": {"validation_error": True},
        }

    return [
        bad("Q01", "Malformed day", {**base, "first_day": "28.09.2026"}),
        bad("Q02", "Reversed window", {**base, "first_day": "2026-09-29"}),
        bad(
            "Q03",
            "Three compared Workloads",
            {**base, "compare": [w, w2, {**w, "uid": "eeeeeeee-0000-4000-8000-000000000003"}]},
        ),
        bad(
            "Q04",
            "compare outside caller_localities",
            {**base, "caller_localities": [w], "compare": [w, w2]},
        ),
        bad(
            "Q05",
            "21 evidence refs",
            {
                "mode": "evidence",
                "subject_service_id": "service:orders",
                "snapshot_id": "aip:snapshot:v1:" + "1" * 64,
                "refs": [f"evidence:ref:{n:02d}" for n in range(21)],
            },
        ),
        bad("Q06", "A cursor that is not a locality cursor", {**base, "cursor": "bm90LWpzb24"}),
        bad("Q07", "An unknown field", {**base, "cypher": "MATCH (n) RETURN n"}),
        bad(
            "Q08",
            "A compared Workload without a UID",
            {**base, "compare": [{k: v for k, v in w.items() if k != "uid"}, w2]},
        ),
    ]


def document() -> dict:
    return {
        "contract": "aip-v0.6-i3-expected-answers",
        "vector_set": 1,
        "governing": [
            "docs/specifications/0.6.0/i3-bounded-current-state-projection-and-public-answers.md rev 0.2",
            "docs/specifications/0.6.0/i3-decision-record.md D1-D16",
        ],
        "authored": "I3.1c, by author_expected_answers.py (stdlib only, no app import), before any "
        "I3.2 semantic code",
        "schemas": [
            "schemas/architecture_intelligence/v0.6/service-dependencies-by-locality-request.schema.json",
            "schemas/architecture_intelligence/v0.6/service-dependencies-by-locality-answer.schema.json",
        ],
        "matching": "docs/specifications/0.6.0/i3-expected-answer-matrix.md §2",
        "cases": cases(),
    }


def render() -> str:
    return (
        json.dumps(copy.deepcopy(document()), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
