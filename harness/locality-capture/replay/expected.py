"""Author the rehearsal's expected answers (v0.6.0 I2.6a; I1 capture runbook §7).

Standalone, stdlib only, no AIP import: the concrete v2 ids come from the recorded UIDs, the run
day and the accepted Operation ids (from the import report), via the frozen v2 key rule (I1 v2
contract §2: sorted-key compact UTF-8 JSON of the ten key fields, full SHA-256). Writes
`expected.md`, which must be committed before any AIP evaluation of the recording.

Usage: python expected.py IDENTITIES_ENV ACCEPTED_OPERATIONS_TXT > expected.md
"""

import hashlib
import json
import sys
from pathlib import Path


def v2_id(*, day: str, operation: str, cluster: str, pod: str) -> str:
    key = {
        "contract_version": 2,
        "source_type": "OPENTELEMETRY",
        "evidence_type": "OBSERVED",
        "relation_type": "CALLS",
        "environment": "locality-capture",
        "bucket_utc_day": day,
        "subject_id": "service:orders",
        "object_id": operation,
        "caller_cluster_uid": cluster,
        "caller_pod_uid": pod,
    }
    encoded = json.dumps(key, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "evidence:otel:calls-scoped:v2:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def main(identities_path: str, operations_path: str) -> None:
    ids = dict(
        line.strip().split("=", 1)
        for line in Path(identities_path).read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    accepted = [
        line.strip().strip('"')
        for line in Path(operations_path).read_text(encoding="utf-8").splitlines()
        if ":" in line
    ]
    [o1] = [o for o in accepted if o.endswith(":pricing:GET:/prices") and "legacy" not in o]
    [o2] = [o for o in accepted if o.endswith(":legacy-pricing:GET:/prices")]
    day, cluster = ids["DAY"], ids["CLUSTER_UID"]
    v01 = v2_id(day=day, operation=o1, cluster=cluster, pod=ids["P1_UID"])
    v02 = v2_id(day=day, operation=o2, cluster=cluster, pod=ids["P2_UID"])
    print(f"""# Rehearsal expected answers (REHEARSAL - NOT I5 evidence)

**Label (runbook §8):** (b) independently authored expected answers, for the I2.6a **rehearsal**
recording in this directory. Authored with `harness/locality-capture/replay/expected.py` (stdlib
only, the frozen v2 key rule of I1 v2 contract §2) from `identities.env` and the accepted
Operation ids of the import report, **before** any AIP evaluation of the recording.

Query: caller `service:orders`, environment `locality-capture`, whole UTC day `{day}`.

| Symbol | Value |
|---|---|
| Cluster UID | `{cluster}` |
| P1 (`orders`) | `{ids["P1_NAME"]}` / `{ids["P1_UID"]}` |
| P2 (`orders-canary`) | `{ids["P2_NAME"]}` / `{ids["P2_UID"]}` |
| O1 (accepted) | `{o1}` |
| O2 (accepted) | `{o2}` |
| v2 (P1 -> O1) | `{v01}` |
| v2 (P2 -> O2) | `{v02}` |

| # | Selected capture | Candidate | Expected |
|---|---|---|---|
| E1 | C1 | v2 (P1 -> O1) | `APPLICABLE` at Deployment `orders` (namespace `aip-locality`, cluster above); `CONFIRMED` (declared orders -> pricing plus scoped observed) |
| E2 | C1 | v2 (P2 -> O2) | `APPLICABLE` at Deployment `orders-canary`; `OBSERVED_ONLY` (no declaration for legacy-pricing) |
| E3 | C1 | all | Exactly two assertions, (orders, O1) and (orders-canary, O2), with two distinct Workload UIDs; no (orders, O2) or (orders-canary, O1); target runtime scope `UNKNOWN`; no candidate limitation |
| E4 | C2 | v2 (P1 -> O1) | Retained and still P1's; candidate limitation `UNRESOLVED` [`LOCALITY_CAPTURE_MISSING_POD`]; no assertion for Deployment `orders` |
| E5 | C2 | v2 (P2 -> O2) | Still `APPLICABLE` at Deployment `orders-canary`, `OBSERVED_ONLY` (C2 is captured on `{day}`) |
| E6 | both | v1 | One v1 bucket per (orders, Operation, day); its observation count equals the flag-off replay's and the matching v2 record's count |
| E7 | both | snapshot | The C1-selected and C2-selected `snapshot_id`s differ; both states carry `scoped_observed_calls_v2` |
""")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
