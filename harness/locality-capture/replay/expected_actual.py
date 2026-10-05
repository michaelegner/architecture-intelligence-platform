"""Source-only preparation of the actual I5 oracle; no AIP imports or evaluation.

Uses the frozen v2 key helper, raw Collector JSON and YAML captures. The emitted dossier
requires Michael Egner's independent review/adoption before commit and first AIP evaluation.
Usage: uv run python harness/locality-capture/replay/expected_actual.py ARTIFACT_DIR
"""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import yaml
from analyze import _attributes
from expected import v2_id


def digest_parts(*values: str) -> str:
    encoded = [value.encode() for value in values]
    return hashlib.sha256(
        b"".join(len(part).to_bytes(8, "big") + part for part in encoded)
    ).hexdigest()


def verified_hashes(artifact: Path) -> dict[str, str]:
    hashes = {}
    for line in (artifact / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split(None, 1)
        name = name.removeprefix("*")
        assert hashlib.sha256((artifact / name).read_bytes()).hexdigest() == digest, name
        hashes[name] = digest
    return hashes


def source_facts(artifact: Path) -> dict:
    hashes = verified_hashes(artifact)
    identities = dict(
        line.split("=", 1) for line in (artifact / "identities.env").read_text().splitlines()
    )
    registration = json.loads((artifact / "source-registration.json").read_text())
    operations = (artifact / "accepted-operations.txt").read_text().splitlines()
    assert (
        operations
        == json.loads((artifact / "import-declarations.json").read_text())["accepted_operation_ids"]
    )
    source_id = "urn:aip:source:kubernetes:" + digest_parts(
        registration["id"], identities["CLUSTER_UID"]
    )
    counts = Counter()
    witnesses = {}
    request_count = 0
    for number, line in enumerate((artifact / "otlp.jsonl").read_text().splitlines(), 1):
        assert line.strip(), "blank request in actual recording"
        request_count += 1
        for batch in json.loads(line)["resourceSpans"]:
            resource = _attributes(batch["resource"].get("attributes"))
            for scope in batch["scopeSpans"]:
                for span in scope["spans"]:
                    if span["kind"] not in (3, "SPAN_KIND_CLIENT"):
                        continue
                    attributes = _attributes(span.get("attributes"))
                    pod, target = resource["k8s.pod.uid"], attributes["peer.service"]
                    assert resource["k8s.cluster.uid"] == identities["CLUSTER_UID"]
                    assert resource["deployment.environment.name"] == "locality-capture"
                    assert resource["service.name"] == "orders"
                    assert pod in (identities["P1_UID"], identities["P2_UID"])
                    counts[(pod, target)] += 1
                    witnesses.setdefault(
                        pod,
                        {
                            "line": number,
                            "trace_id": span["traceId"],
                            "span_id": span["spanId"],
                            "resource": resource,
                            "attributes": attributes,
                        },
                    )
    capture_facts = {}
    chains = {}
    for state in ("c1", "c2"):
        envelope = yaml.safe_load((artifact / state / "envelope.yaml").read_text())
        revision = envelope["metadata"]["revision"]
        assert envelope["source"]["clusterUid"] == identities["CLUSTER_UID"]
        resources = []
        for entry in envelope["files"]:
            path = artifact / state / entry["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
            for document in yaml.safe_load_all(path.read_text()):
                resources.extend(document["items"] if document["kind"] == "List" else [document])
        by_uid = {r["metadata"]["uid"]: r for r in resources}
        state_chains = {}
        for label in ("P1", "P2"):
            uid = identities[f"{label}_UID"]
            if uid not in by_uid:
                assert state == "c2" and label == "P1"
                continue
            chain, refs = [], []
            resource = by_uid[uid]
            while True:
                metadata = resource["metadata"]
                chain.append(metadata["uid"])
                group = (
                    resource["apiVersion"].split("/")[0] if "/" in resource["apiVersion"] else ""
                )
                logical = "urn:aip:k8s-resource:" + digest_parts(
                    identities["CLUSTER_UID"],
                    group,
                    resource["kind"],
                    metadata.get("namespace", ""),
                    metadata["name"],
                )
                refs.append(f"evidence:kubernetes:{logical}#resources.yaml:{revision}")
                if resource["kind"] == "Deployment":
                    assert metadata["uid"] == identities[f"{label}_WORKLOAD_UID"]
                    break
                [owner] = [o for o in metadata["ownerReferences"] if o.get("controller")]
                resource = by_uid[owner["uid"]]
                assert (
                    resource["kind"] == owner["kind"]
                    and resource["metadata"]["name"] == owner["name"]
                )
            state_chains[label] = {"uids": chain, "capture_refs": sorted(refs)}
        chains[state] = state_chains
        capture_facts[state] = {
            "source_instance_id": source_id,
            "revision": revision,
            "captured_at": envelope["metadata"]["capturedAt"],
            "namespaces": envelope["scope"]["namespaces"],
            "evidence_mode": envelope["source"]["mode"],
        }
    assert chains["c1"]["P2"]["uids"] == chains["c2"]["P2"]["uids"]
    candidates = {}
    for label, target, qualification in (
        ("P1", "pricing", "CONFIRMED"),
        ("P2", "legacy-pricing", "OBSERVED_ONLY"),
    ):
        operation = f"operation:service:{target}:GET:/prices"
        assert operation in operations
        pod = identities[f"{label}_UID"]
        candidates[label] = {
            "pod_uid": pod,
            "workload_uid": identities[f"{label}_WORKLOAD_UID"],
            "operation_id": operation,
            "qualification": qualification,
            "count": counts[(pod, target)],
            "v2_id": v2_id(
                day=identities["DAY"],
                operation=operation,
                cluster=identities["CLUSTER_UID"],
                pod=pod,
            ),
            "source_witness": witnesses[pod],
        }
    assert sum(counts.values()) == sum(c["count"] for c in candidates.values())
    return {
        "day": identities["DAY"],
        "cluster_uid": identities["CLUSTER_UID"],
        "recorded_requests": request_count,
        "candidates": candidates,
        "captures": capture_facts,
        "chains": chains,
        "original_hashes": hashes,
    }


def main(path: str) -> None:
    facts = source_facts(Path(path))
    print("""# I5.2 actual-capture expected answers

**Label:** independently expected facts for `ACTUAL_CONTROLLED_REFERENCE`, not rehearsal.
**Expected-answer author:** Michael Egner.
**Review/adoption:** PENDING — this source-only preparation has not been independently adopted.
**Chronology:** no actual-capture AIP evaluation has run. Commit this dossier after owner review
and before the first evaluation; retain that commit separately from the qualification candidate.

Source justification: original `otlp.jsonl` CLIENT spans/Resources, canonical Operation IDs from
`import-declarations.json`, original C1/C2 resources and envelopes, and I1 E1-E7/I5 revision 0.1 §4.
The facts below are calculated without importing AIP. Witness line numbers are one-based.
Exact Kubernetes refs use the frozen logical-resource and revision/pointer identity rules.
Original input hashes remain unchanged; this dossier is separate from the acquisition manifest.

Query: `service:orders`, environment `locality-capture`, the recorded whole UTC day.

| Gate | Expected answer and forbidden claims |
|---|---|
| E1 | C1 P1 resolves to the exact W1 UID; pricing is APPLICABLE and CONFIRMED. |
| E2 | C1 P2 resolves to the exact W2 UID; legacy-pricing is APPLICABLE and OBSERVED_ONLY. |
| E3 | C1 unfiltered inventory contains both Workloads and exactly their two supported Operations. Comparison shows distinct positive memberships; no cross-attribution, absence or exclusive-use inference. Each target runtime scope is UNKNOWN and coverage LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE. Exact v2/capture refs resolve only for the authorized caller/Operation and current snapshot. |
| E4 | C2 retains P1's original v2 record/count; UNRESOLVED with LOCALITY_CAPTURE_MISSING_POD; no positive W1, no reassignment to W2 and no local absence claim. |
| E5 | C2 P2 remains APPLICABLE/OBSERVED_ONLY at its unchanged owner UID with C2 lineage. |
| E6 | Each Operation's v1 OBSERVED bucket count and v2 count equal the raw CLIENT counts below, unchanged by C2 import; no fabricated Workload attribution in v1. |
| E7 | C1 and C2 snapshot IDs differ; accepted v2 contributes the conditional scoped fingerprint. C1-bound evidence/query/cursor after C2 is refused, never silently restarted or served historically. |

All supported assessments carry the exact source revision and owner-chain refs below.
Wrong-caller and unauthorized refs are NOT_FOUND without records. No local NOT_OBSERVED_IN_WINDOW,
global dependency set, target placement, inferred caller from DEPLOYED_AS/labels or historical
browsing claim is allowed. Declared-only/missing-scope and pagination boundary controls reuse the
separately labelled frozen synthetic oracle; they are not actual-capture observations.

## Source-derived executable facts

```json""")
    print(json.dumps(facts, indent=2, sort_keys=True))
    print("```")


if __name__ == "__main__":
    main(sys.argv[1])
