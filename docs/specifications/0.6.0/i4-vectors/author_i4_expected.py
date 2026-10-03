"""Author the I4 independent bridge vectors (v0.6.0 I4.1; I4 spec §3, decision record D2).

Standalone and stdlib-only: it imports nothing from `app`, so the expectations cannot be derived
from the implementation they qualify. Literal IDs come from the frozen rules alone (I1 v2 contract
§2, I2 D9/D14.1), re-stated here rather than imported so the vector has no dependency on I3's code.

The set holds the mandatory I4-P3 bridge vector (I4 §3): a same-day C1 -> C2 rollout in which
caller Pod P1 is replaced by a different Pod P3 under the same-named Deployment, in two variants:

- `a`: the Deployment (Workload) UID is unchanged across C1 and C2;
- `b`: the same name is a new Workload UID (new incarnation) in C2.

Worlds are SYNTHETIC generated envelopes (not the I5 capture and not the I2.6a rehearsal). Values
only a run can know are `{{SYMBOL}}` placeholders, bound per
`../i3-expected-answer-matrix.md` §2. Usage, from the repository root:

    python docs/specifications/0.6.0/i4-vectors/author_i4_expected.py

writes `expected-i4.json` next to this file. Re-running must reproduce it byte for byte.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OUTPUT = Path(__file__).resolve().parent / "expected-i4.json"


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


SUBJECT = "service:orders"
ENVIRONMENT = "production"
DAY = "2026-09-28"
CLUSTER = "11111111-1111-4111-8111-000000000001"
NAMESPACE = "shop"
O1 = "operation:service:pricing:GET:/prices"
O2 = "operation:service:pricing:GET:/prices/{id}"
PROVIDER = "service:pricing"
DEPLOYMENT = "orders"

POD = {
    "P1": {"uid": "bbbbbbbb-0000-4000-8000-000000000001", "name": "orders-5d9f7c-p1"},
    "P3": {"uid": "bbbbbbbb-0000-4000-8000-000000000003", "name": "orders-6f8c2a-p3"},
    "P2": {"uid": "bbbbbbbb-0000-4000-8000-000000000002", "name": "orders-canary-7c4b9d-p2"},
}
# W2 is a second, stable caller Workload (same Service). It gives every variant a valid two-Workload
# comparison (D3 needs two distinct complete identities) and a control for leakage.
W2_UID = "aaaaaaaa-0000-4000-8000-000000000002"
W2_NAME = "orders-canary"
OWNER = {"P1": DEPLOYMENT, "P3": DEPLOYMENT, "P2": W2_NAME}
WORKLOAD_UID = {
    "C1": "aaaaaaaa-0000-4000-8000-000000000001",
    "C2-a": "aaaaaaaa-0000-4000-8000-000000000001",
    "C2-b": "aaaaaaaa-0000-4000-8000-0000000000b1",
}
# C1 is imported first; C2 is an authoritative later capture of the same source and scope.
CAPTURE = {
    "C1": {"revision": "i4p3-c1", "captured_at": f"{DAY}T10:00:00Z", "pods": ["P1", "P2"]},
    "C2": {"revision": "i4p3-c2", "captured_at": f"{DAY}T12:00:00Z", "pods": ["P3", "P2"]},
}
SPANS = {
    "P1": ("09:00:00", "09:30:00"),  # before C1
    "P3": ("12:30:00", "13:00:00"),  # after C2: P3's own events
    "P2": ("09:10:00", "09:40:00"),  # W2's own events, before C1
}
OPERATION = {"P1": O1, "P3": O2, "P2": O1}  # distinct Operations make any P1 -> P3 transfer visible


def _capture(label: str, variant: str) -> dict:
    cap = CAPTURE[label]
    uid = WORKLOAD_UID["C1" if label == "C1" else f"C2-{variant}"]
    return {
        "label": label,
        "source_instance_id": "{{SOURCE:S}}",
        "cluster_uid": CLUSTER,
        "namespaces": [NAMESPACE],
        "revision": cap["revision"],
        "captured_at": cap["captured_at"],
        "evidence_mode": "CAPTURED_RESOURCE",
        "completeness": "COMPLETE",
        "pods": [
            {
                "uid": POD[p]["uid"],
                "name": POD[p]["name"],
                "namespace": NAMESPACE,
                "owner": {
                    "kind": "Deployment",
                    "name": OWNER[p],
                    "uid": W2_UID if p == "P2" else uid,
                },
            }
            for p in cap["pods"]
        ],
    }


def _v2(pod: str) -> dict:
    times = [f"{DAY}T{t}Z" for t in SPANS[pod]]
    return {
        "id": v2_id(
            subject=SUBJECT,
            operation=OPERATION[pod],
            environment=ENVIRONMENT,
            day=DAY,
            cluster=CLUSTER,
            pod=POD[pod]["uid"],
        ),
        "subject_id": SUBJECT,
        "object_id": OPERATION[pod],
        "environment": ENVIRONMENT,
        "bucket_utc_day": DAY,
        "caller_cluster_uid": CLUSTER,
        "caller_pod_uid": POD[pod]["uid"],
        "client_resource": {
            "k8s.namespace.name": NAMESPACE,
            "k8s.pod.name": POD[pod]["name"],
            "k8s.deployment.name": OWNER[pod],
        },
        "spans": [{"timestamp": t, "trace_id": _sha([pod, OPERATION[pod], t])[:32]} for t in times],
        "correlation_mode": "CLIENT_SERVER",
    }


def _inputs(variant: str) -> dict:
    return {
        "world": "I4-P3",
        "variant": variant,
        "declarations": {
            "services": sorted({SUBJECT, PROVIDER}),
            "declared_operations": [
                {"id": O1, "provider": PROVIDER},
                {"id": O2, "provider": PROVIDER},
            ],
            "declared_calls": [],
        },
        "same_day": DAY,
        "state_sequence": [
            "import C1 (capture only)",
            "persist P1's and P2's v2 (each its own CLIENT identity, before C1)",
            "-> STEP 1 is asked here",
            "import C2 over C1 (authoritative replacement: P1 absent, P3 present)",
            "persist P3's v2 (own CLIENT identity, after C2)",
            "-> STEPS 2-4 are asked here",
        ],
        "captures": [_capture("C1", variant), _capture("C2", variant)],
        "v2": {"P1": _v2("P1"), "P3": _v2("P3"), "P2": _v2("P2")},
        "workload_uids": {
            "C1": WORKLOAD_UID["C1"],
            "C2": WORKLOAD_UID[f"C2-{variant}"],
            "W2": W2_UID,
        },
        "disclosure": "SYNTHETIC generated envelopes; not the I5 capture nor the I2.6a rehearsal.",
    }


def _identity(uid: str) -> dict:
    return {"cluster_uid": CLUSTER, "namespace": NAMESPACE, "kind": "Deployment", "uid": uid}


def _key(identity: dict) -> tuple:
    return (identity["cluster_uid"], identity["namespace"], identity["kind"], identity["uid"])


def _request(extra: dict | None = None) -> dict:
    base = {
        "mode": "query",
        "subject_service_id": SUBJECT,
        "environment": ENVIRONMENT,
        "first_day": DAY,
        "last_day": DAY,
    }
    return {**base, **(extra or {})}


def _case(variant: str) -> dict:
    p1, p2, p3 = (_v2(pod)["id"] for pod in ("P1", "P2", "P3"))
    same_uid = variant == "a"
    c1_workload = WORKLOAD_UID["C1"]
    c2_workload = WORKLOAD_UID[f"C2-{variant}"]
    asserts: list[dict[str, Any]] = [
        # STEP 1: C1's prior positive result, against C1's then-current snapshot only.
        {
            "step": 1,
            "kind": "positive",
            "workload_uid": c1_workload,
            "operation": O1,
            "evidence_ids_exactly": [p1],
            "why": "P1's own v2 + C1 Pod/owner capture (I2 L15)",
        },
        # STEP 2: after C2, P3's assessment derives only from P3's own v2 and C2.
        {
            "step": 2,
            "kind": "positive",
            "workload_uid": c2_workload,
            "operation": O2,
            "evidence_ids_exactly": [p3],
            "capture_revisions_exactly": [CAPTURE["C2"]["revision"]],
            "why": "P3's own v2 + C2 capture; name or Workload UID match grants nothing from P1",
        },
        # STEP 2: P1's retained v2 stays Pod-scoped; its Workload-local result is UNRESOLVED.
        {
            "step": 2,
            "kind": "unresolved",
            "v2_evidence_id": p1,
            "why": "C2 lacks P1's UID/owner chain (parent §20 row 12; I2 L18/L27)",
        },
        # STEP 2-3: leakage and absence guards.
        {
            "step": 2,
            "kind": "forbidden",
            "what": "O1 positive/qualified for the current Workload",
            "workload_uid": c2_workload,
            "operation": O1,
        },
        {
            "step": 2,
            "kind": "forbidden",
            "what": "NOT_OBSERVED_IN_WINDOW or verified absence for any Workload-local O1 or O2",
        },
        {
            "step": 2,
            "kind": "forbidden",
            "what": "P1's v2 id in any evidence_refs, assessment or provider group of P3's result",
            "v2_evidence_id": p1,
            "scope": "assessment of O2",
        },
        {
            "step": 2,
            "kind": "forbidden",
            "what": "P3's v2 id or P3's C2 capture ref in any result attributed to O1; W2's own "
            "C2 lineage (P2's v2 and C2's P2 capture ref) is expected there",
            "v2_evidence_id": p3,
            "scope": "assessment of O1",
        },
        # W2 (P2) is the control: stable across C1 and C2, positive from its own evidence only.
        {
            "step": 2,
            "kind": "positive",
            "workload_uid": W2_UID,
            "operation": O1,
            "evidence_ids_exactly": [p2],
            "capture_revisions_exactly": [CAPTURE["C2"]["revision"]],
            "why": "P2's own v2 + C2's P2 capture; unaffected by the P1 -> P3 replacement",
        },
        # STEP 3: a caller_localities selection returns exactly the selected Workload.
        {
            "step": 3,
            "kind": "localities_exactly",
            "workload_uids": [c2_workload],
            "why": "caller_localities = [current]; P1's retained evidence adds no locality for it",
        },
        # STEP 4: a valid two-Workload comparison (current vs W2) describes positives only.
        {
            "step": 4,
            "kind": "compare_only_in",
            "operation": O2,
            "workload_uid": c2_workload,
            "why": "O2 is positive only for the current Workload (P3's own evidence)",
        },
        {
            "step": 4,
            "kind": "compare_only_in",
            "operation": O1,
            "workload_uid": W2_UID,
            "why": "O1 is positive only for W2; P1's O1 is not transferred to the current Workload",
        },
        {
            "step": 4,
            "kind": "forbidden",
            "what": "O1 in_both, or O1 positive for the current Workload, in the comparison",
            "compare": sorted([c2_workload, W2_UID]),
        },
        # STEP 5: scoped drill-down.
        {
            "step": 5,
            "kind": "evidence_refs_resolve",
            "of": "the O2 assessment's capture and v2 refs",
            "resolve_to": [p3],
            "never_resolve_to": [p1],
        },
        # Snapshot semantics: a historical C1 query is not claimed to remain available.
        {
            "step": 6,
            "kind": "refusal",
            "code": "SNAPSHOT_NOT_AVAILABLE",
            "why": "the C1 snapshot_id after C2 replaced it (as I3 P08); no historical availability claim",
        },
        {"step": 6, "kind": "snapshot_differs_from_step", "other": 1},
    ]
    if same_uid:
        asserts.append(
            {
                "step": 2,
                "kind": "forbidden",
                "what": "qualifying the current Workload for O1 merely because its Workload UID equals C1's",
                "workload_uid": c2_workload,
                "operation": O1,
            }
        )
    else:
        asserts.append(
            {
                "step": 2,
                "kind": "forbidden",
                "what": "any assessment keyed to the C1 Workload UID that is positive after C2",
                "workload_uid": c1_workload,
                "positive": True,
            }
        )
        asserts.append(
            {
                "step": 2,
                "kind": "forbidden",
                "what": "carrying the same-NAME Workload's O1 over to the new Workload UID",
                "workload_uid": c2_workload,
                "operation": O1,
            }
        )
    return {
        "id": f"B01{variant}",
        "kind": "bridge",
        "title": (
            "I4-P3 bridge (a): P1 -> P3, Workload UID unchanged"
            if same_uid
            else "I4-P3 bridge (b): P1 -> P3, new Workload UID incarnation"
        ),
        "spec_refs": [
            "I4 §3 'Mandatory I4-P3 bridge vector'",
            "parent §20 row 12",
            "I1 L18, L27",
            "I2 D4",
        ],
        "inputs": _inputs(variant),
        "steps": [
            {"step": 1, "ask": "query at C1 (bind snapshot)", "request": _request()},
            {"step": 2, "ask": "query after C2 + P3 v2", "request": _request()},
            {
                "step": 3,
                "ask": "query with caller_localities = [current Workload]",
                "request": _request({"caller_localities": [_identity(c2_workload)]}),
            },
            {
                "step": 4,
                "ask": "query comparing the current Workload and W2",
                "request": _request(
                    {"compare": sorted([_identity(c2_workload), _identity(W2_UID)], key=_key)}
                ),
            },
            {
                "step": 5,
                "ask": "scoped evidence drill-down of the step-2 O2 refs at the step-2 snapshot",
                "request": {
                    "mode": "evidence",
                    "subject_service_id": SUBJECT,
                    "snapshot_id": "{{STEP2_SNAPSHOT_ID}}",
                    "refs": sorted([p3, "{{CAPTURE_REF:C2/P3}}"]),
                },
            },
            {
                "step": 6,
                "ask": "query with the step-1 snapshot_id after C2",
                "request": _request({"snapshot_id": "{{STEP1_SNAPSHOT_ID}}"}),
            },
        ],
        "assert": asserts,
        "two_run_note": "C1 then C2 are replayed within each of runs A and B, reset between A and B.",
    }


def _gap(
    case_id: str,
    title: str,
    rows: list[int],
    world: str,
    delta: str,
    asserts: list[dict],
    steps: list[dict] | None = None,
):
    """A compact gap case: an I3 world plus a stated delta; the runner builds it in I4.2."""
    return {
        "id": case_id,
        "kind": "bridge",
        "title": title,
        "spec_refs": ["I4 §3 coverage rule", *[f"parent §20 row {r}" for r in rows]],
        "inputs": {"world": world, "delta": delta, "same_day": DAY},
        "steps": steps or [{"step": 1, "ask": "query", "request": _request()}],
        "assert": asserts,
    }


# The frozen v0.5.1 Quarkus replay context (examples/quarkus-super-heroes-demo/check_ready.py).
QUARKUS_REQUEST = {
    "mode": "query",
    "subject_service_id": "service:rest-fights",
    "environment": "quarkus-i5",
    "first_day": "2026-09-25",
    "last_day": "2026-09-25",
}


def _gap_cases() -> list[dict]:
    return [
        _gap(
            "B02",
            "Configured DEPLOYED_AS mapping, spans without an admissible Pod UID",
            [10],
            "K",
            "Path B mapping artifact binds service:orders to a Workload via DEPLOYED_AS; v1 CALLS "
            "only (no v2); the CLIENT spans carry no k8s.pod.uid",
            [
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "any caller locality or Workload-local CALLS assessment",
                },
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "a Workload-local qualification inferred from DEPLOYED_AS alone",
                },
                {
                    "step": 1,
                    "kind": "snapshot_unchanged_except",
                    "what": "Service placement still "
                    "resolves through the existing deployments read; shared snapshot is the same",
                },
            ],
        ),
        _gap(
            "B03",
            "Service-level declaration without an explicit regional binding",
            [15],
            "K",
            "A declared Service CALLS Operation applies at Service level; a positive v2 exists in "
            "one cluster; no region/tenant binding exists anywhere",
            [
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "a per-region (or per-tenant) declared "
                    "assertion, or any region/tenant key in the answer",
                },
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "a declaration that becomes "
                    "Workload-local positive without the admitted scoped observation",
                },
            ],
        ),
        _gap(
            "B04",
            "Caller locality evidenced, target locality missing; two qualified one-hop edges",
            [22, 23],
            "K",
            "service:orders (Workload W1) positively calls O1 owned by service:pricing; "
            "service:pricing's own caller Workload positively calls a further Operation; neither "
            "target Workload is captured",
            [
                {
                    "step": 1,
                    "kind": "equals",
                    "path": "data.localities[*].target_runtime_scope",
                    "value": "UNKNOWN",
                },
                {"step": 1, "kind": "forbidden", "what": "a target-local or target-remote claim"},
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "a path, flow or end-to-end business "
                    "outcome joined from the two one-hop edges",
                },
            ],
        ),
        _gap(
            "B05",
            "Intent-like document or agent narrative added",
            [24],
            "K",
            "Baseline: the I3 K world with one positive v2. Then an intent-like Markdown document "
            "and an agent-generated narrative are offered to every ingestion path that accepts "
            "documents (accepted or rejected, either way)",
            [
                {
                    "step": 3,
                    "kind": "bytes_equal_to_step",
                    "other": 1,
                    "what": "answer bytes, including snapshot_id, equal the baseline's",
                },
                {
                    "step": 3,
                    "kind": "forbidden",
                    "what": "any change to Current State, lineage or evidence refs",
                },
            ],
            [
                {"step": 1, "ask": "baseline query", "request": _request()},
                {"step": 2, "ask": "offer the intent document and the narrative (no request)"},
                {"step": 3, "ask": "query again", "request": _request()},
            ],
        ),
        _gap(
            "B06",
            "Quarkus replay and operator AsyncAPI overlay with scoped evidence enabled",
            [25],
            "v0.5.1 Quarkus replay",
            "The frozen v0.5.1 dossier, operator AsyncAPI overlay and one-shot OTLP replay "
            "(`quarkus-i5`, 2026-09-25T13:06:47Z to 13:06:54Z) run with "
            "telemetry.scoped-evidence.enabled=true; the replay spans carry no k8s.pod.uid",
            [
                {"step": 1, "kind": "equals", "path": "v2 record count", "value": 0},
                {"step": 1, "kind": "equals", "path": "len(data.localities)", "value": 0},
                {
                    "step": 1,
                    "kind": "matches_frozen_pins",
                    "pins": "examples/quarkus-super-heroes-demo/check_ready.py "
                    "(expected qualifications, Kafka `fights` NOT_OBSERVED_IN_WINDOW)",
                },
                {
                    "step": 1,
                    "kind": "forbidden",
                    "what": "a newly inferred runtime locality or a Kafka/messaging observation "
                    "not present in the v0.5.1 pins",
                },
            ],
            [
                {
                    "step": 1,
                    "ask": "locality query for the replay context",
                    "request": QUARKUS_REQUEST,
                }
            ],
        ),
    ]


def document() -> dict:
    return {
        "vector_set": "aip-v0.6-i4-expected",
        "contract": "i4-bridge-vectors/1",
        "governing": [
            "docs/specifications/0.6.0/i4-deterministic-semantic-qualification.md",
            "docs/specifications/0.6.0/i4-decision-record.md",
        ],
        "authored": "I4.1, before any I4 execution against the candidate",
        "assertion_kinds": {
            "equals": "the value at `path` equals `value`",
            "localities_exactly": "data.localities holds exactly the Workloads `workload_uids`",
            "compare_only_in": "the comparison lists `operation` as present only for `workload_uid`",
            "bytes_equal_to_step": "the step's canonical answer bytes equal the other step's",
            "matches_frozen_pins": "the answer agrees with the frozen v0.5.1 pins at `pins`",
            "snapshot_unchanged_except": "the stated service-level read is unchanged",
            "positive": "an APPLICABLE POSITIVE assessment of `operation` in the locality of "
            "`workload_uid`, whose observation.evidence_ids equal `evidence_ids_exactly` as a set",
            "unresolved": "the candidate with this v2_evidence_id is not APPLICABLE for any "
            "Workload-local assessment and is reported UNRESOLVED/INAPPLICABLE, never absent",
            "forbidden": "the described fact appears nowhere in the step's answer JSON",
            "evidence_refs_resolve": "evidence-mode refs resolve to exactly `resolve_to` v2 "
            "records; `never_resolve_to` ids are never returned",
            "refusal": "the step's answer is a refusal with this code",
            "snapshot_differs_from_step": "snapshot.snapshot_id differs from the other step's",
        },
        "cases": [_case("a"), _case("b"), *_gap_cases()],
    }


def render() -> str:
    return json.dumps(document(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT}")
