# I5.2 actual-capture expected answers

**Label:** independently expected facts for `ACTUAL_CONTROLLED_REFERENCE`, not rehearsal.
**Expected-answer author:** Michael Egner.
**Review/adoption:** ADOPTED by Michael Egner before first AIP evaluation, by explicit owner instruction in the implementation session.
**Chronology:** no actual-capture AIP evaluation has run. Commit this dossier after owner review
and before the first evaluation; retain that commit separately from the qualification candidate.

Source justification: original `otlp.jsonl` CLIENT spans/Resources, canonical Operation IDs from
`import-declarations.json`, original C1/C2 resources and envelopes, and I1 E1–E7/I5 revision 0.1 §4.
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

```json
{
  "candidates": {
    "P1": {
      "count": 359,
      "operation_id": "operation:service:pricing:GET:/prices",
      "pod_uid": "d31ca716-e7fa-420c-821c-b79cd907d3c5",
      "qualification": "CONFIRMED",
      "source_witness": {
        "attributes": {
          "http.request.method": "GET",
          "http.response.status_code": "{\"intValue\": \"200\"}",
          "network.peer.address": "pricing",
          "network.protocol.version": "1.1",
          "peer.service": "pricing",
          "server.address": "pricing",
          "url.full": "http://pricing/prices",
          "user_agent.original": "python-requests/2.34.2"
        },
        "line": 1,
        "resource": {
          "deployment.environment.name": "locality-capture",
          "k8s.cluster.uid": "2fe6677a-390d-458c-9e4c-85ae44b62f91",
          "k8s.deployment.name": "orders",
          "k8s.namespace.name": "aip-locality",
          "k8s.pod.name": "orders-fdc669b5b-7sjlm",
          "k8s.pod.uid": "d31ca716-e7fa-420c-821c-b79cd907d3c5",
          "service.instance.id": "01700541-90c7-402c-b206-05266ce8f0be",
          "service.name": "orders",
          "telemetry.sdk.language": "python",
          "telemetry.sdk.name": "opentelemetry",
          "telemetry.sdk.version": "1.45.0"
        },
        "span_id": "d818e4122e15c82c",
        "trace_id": "ae10bd724cf1000fa6acc8ad8be905cb"
      },
      "v2_id": "evidence:otel:calls-scoped:v2:77dbb65f2aa3ff1625d87a732ef23ee6fe924fa2a3df94016a3f3a595a667381",
      "workload_uid": "a8df1913-530a-40cf-9fb4-f143f019ef08"
    },
    "P2": {
      "count": 508,
      "operation_id": "operation:service:legacy-pricing:GET:/prices",
      "pod_uid": "febe35bd-15a9-411a-ba33-cbd82da14169",
      "qualification": "OBSERVED_ONLY",
      "source_witness": {
        "attributes": {
          "http.request.method": "GET",
          "http.response.status_code": "{\"intValue\": \"200\"}",
          "network.peer.address": "legacy-pricing",
          "network.protocol.version": "1.1",
          "peer.service": "legacy-pricing",
          "server.address": "legacy-pricing",
          "url.full": "http://legacy-pricing/prices",
          "user_agent.original": "python-requests/2.34.2"
        },
        "line": 1,
        "resource": {
          "deployment.environment.name": "locality-capture",
          "k8s.cluster.uid": "2fe6677a-390d-458c-9e4c-85ae44b62f91",
          "k8s.deployment.name": "orders-canary",
          "k8s.namespace.name": "aip-locality",
          "k8s.pod.name": "orders-canary-55fd859f98-fzfj6",
          "k8s.pod.uid": "febe35bd-15a9-411a-ba33-cbd82da14169",
          "service.instance.id": "b37798a8-2dd1-4b33-bf11-a69e5725aadd",
          "service.name": "orders",
          "telemetry.sdk.language": "python",
          "telemetry.sdk.name": "opentelemetry",
          "telemetry.sdk.version": "1.45.0"
        },
        "span_id": "8f043e9ba636ebf4",
        "trace_id": "98ee61f4428eee215001c7c998480ff1"
      },
      "v2_id": "evidence:otel:calls-scoped:v2:2f3576e146bf60bfb83e3e00568b185295682f99c073b11ce41c7243253564da",
      "workload_uid": "e7d1033a-3b23-4913-bf59-c67de08d0f07"
    }
  },
  "captures": {
    "c1": {
      "captured_at": "2026-10-05T06:07:30Z",
      "evidence_mode": "CAPTURED_RESOURCE",
      "namespaces": [
        "aip-locality"
      ],
      "revision": "c1-2026-10-05T06-07-30Z",
      "source_instance_id": "urn:aip:source:kubernetes:72fa58e7a5ef25f04ec222abebc11788aaea21edf20d2159f691a4684f0367aa"
    },
    "c2": {
      "captured_at": "2026-10-05T06:10:02Z",
      "evidence_mode": "CAPTURED_RESOURCE",
      "namespaces": [
        "aip-locality"
      ],
      "revision": "c2-2026-10-05T06-10-02Z",
      "source_instance_id": "urn:aip:source:kubernetes:72fa58e7a5ef25f04ec222abebc11788aaea21edf20d2159f691a4684f0367aa"
    }
  },
  "chains": {
    "c1": {
      "P1": {
        "capture_refs": [
          "evidence:kubernetes:urn:aip:k8s-resource:aad06e5051667c2f83964290734fdbb9706669539be8736df33f5ce94d9dfb7b#resources.yaml:c1-2026-10-05T06-07-30Z",
          "evidence:kubernetes:urn:aip:k8s-resource:d5f1b2296f284eb28bd287dd3432c5797dc7987d88dae7dfcb6487a1c14c9935#resources.yaml:c1-2026-10-05T06-07-30Z",
          "evidence:kubernetes:urn:aip:k8s-resource:f9fe580c82beb9df515156ec0fc9a1b239ff1ebbc71fd47dc96478995ba6261e#resources.yaml:c1-2026-10-05T06-07-30Z"
        ],
        "uids": [
          "d31ca716-e7fa-420c-821c-b79cd907d3c5",
          "d4b249c0-4116-46cb-b6aa-da2258ba4d21",
          "a8df1913-530a-40cf-9fb4-f143f019ef08"
        ]
      },
      "P2": {
        "capture_refs": [
          "evidence:kubernetes:urn:aip:k8s-resource:7eb2e7f4c3c5136090c3da63bdbb0ac858506fea851f4a37e9d3859bb470912b#resources.yaml:c1-2026-10-05T06-07-30Z",
          "evidence:kubernetes:urn:aip:k8s-resource:ed95be659b140e22884c2070c02f6cde6f0653e2ef265ab85504bcc13e1431bc#resources.yaml:c1-2026-10-05T06-07-30Z",
          "evidence:kubernetes:urn:aip:k8s-resource:f68ecd17bd325c4d29c75c80321271f5dcd4673d291df0ba3475af0d4b351da0#resources.yaml:c1-2026-10-05T06-07-30Z"
        ],
        "uids": [
          "febe35bd-15a9-411a-ba33-cbd82da14169",
          "0c0019ff-9442-476e-aa0c-ec876aa2b717",
          "e7d1033a-3b23-4913-bf59-c67de08d0f07"
        ]
      }
    },
    "c2": {
      "P2": {
        "capture_refs": [
          "evidence:kubernetes:urn:aip:k8s-resource:7eb2e7f4c3c5136090c3da63bdbb0ac858506fea851f4a37e9d3859bb470912b#resources.yaml:c2-2026-10-05T06-10-02Z",
          "evidence:kubernetes:urn:aip:k8s-resource:ed95be659b140e22884c2070c02f6cde6f0653e2ef265ab85504bcc13e1431bc#resources.yaml:c2-2026-10-05T06-10-02Z",
          "evidence:kubernetes:urn:aip:k8s-resource:f68ecd17bd325c4d29c75c80321271f5dcd4673d291df0ba3475af0d4b351da0#resources.yaml:c2-2026-10-05T06-10-02Z"
        ],
        "uids": [
          "febe35bd-15a9-411a-ba33-cbd82da14169",
          "0c0019ff-9442-476e-aa0c-ec876aa2b717",
          "e7d1033a-3b23-4913-bf59-c67de08d0f07"
        ]
      }
    }
  },
  "cluster_uid": "2fe6677a-390d-458c-9e4c-85ae44b62f91",
  "day": "2026-10-05",
  "original_hashes": {
    "RUN-RECORD.md": "0d4384451b33529708e248d0622c764c6a2bb8697f5074b3a05debe932143509",
    "accepted-operations.txt": "bc117b02979209fe84bbbdcb0553556f03ec917b12f20acdf74fab2f8e6f53ed",
    "acquisition-checks.json": "4772e5bbc97f4ef8b74cfe1cddfa570c4637a13631ab1f22a1f780bea474735f",
    "analysis.json": "c882164abfcf58204abe9e04df13e3b2a9df4ce53c2cefac8e11aee4a06bfb87",
    "attempts/01-invalid-kind-name/run-log.txt": "769e6868a82337ea2ca16ae024498b991187c4de2d512598eb6b5ebb7d181f5a",
    "c1/envelope.yaml": "8102d10c277a4533eeec1dbd785c6dce00228a43bd82e683bfbf0ffaecff67c4",
    "c1/ns.yaml": "6b5e126537a1430ef65dae09984c51538c3c37f99cd8c7b75143fc1543e4ea0f",
    "c1/resources.yaml": "cbc709c161de2283149c6d422a95e25121061c8123a3542129275d6e23582957",
    "c1/rest.yaml": "45562044f33f348359483befac7b6ea02d3ee2a65ecdd6425f655f2f0dfacdf5",
    "c2/envelope.yaml": "abe7c1a091bbe45083af2ed010c08f4055dee046f5679251713bc4debfaef7c7",
    "c2/ns.yaml": "6b5e126537a1430ef65dae09984c51538c3c37f99cd8c7b75143fc1543e4ea0f",
    "c2/resources.yaml": "63593de9293722f86b6f20164ff692ff2348e64d350809c494fb25a9d21296df",
    "c2/rest.yaml": "64f4e95f4e4bbddc6f1a0c98827c86a998cb91541e6648dcd53913ef5475bfd9",
    "collector-end.log": "4d5a8f0cca58edc4b54a86697499d7e849c69edaec37908e01aedfbf75f904af",
    "collector-start.log": "4d5a8f0cca58edc4b54a86697499d7e849c69edaec37908e01aedfbf75f904af",
    "declarations/legacy-pricing/openapi.yaml": "df5dd8aa00fe00eba36db4a82a3ca784d141740086ec7c39dc49d139b5d17562",
    "declarations/orders/architecture.yaml": "23a6dbdd62c1949d72785c4b666660988d62931a9ec5c338eb6be9ff9e92f86c",
    "declarations/orders/openapi.yaml": "65fcc474f33ab35493c7aeed0eea5a11b01aad59dbc741628c7db3cb3c5095c4",
    "declarations/pricing/openapi.yaml": "f9b7dabc5813b354cd098dd1887ccab7a87a53f7b1bc317fb041a2ab0bd20f5d",
    "harness/app/Dockerfile": "d169b58991f4b1ff7cf40fa4ebe16ffb58b795c5d07bc8503fbf506f8d790092",
    "harness/app/app.py": "3c46b94c322d195b4a1f9cdf0658df9cff2f64fa11c57a2e07edba1161301320",
    "harness/app/requirements.in": "338dc06a9760b79fb635e7b8de97178e4fa88c516251ff1456aa567634527335",
    "harness/app/requirements.txt": "71b79ab8cf2d1e1e124307ebe8e9d9f1c213f2fdedec9401eb3d0da96b7d6d34",
    "harness/capture_metadata.py": "f0875108ea462a8fb9f46746bd575b9e22bd61e0c80562de8e9a3bc4ea4d2261",
    "harness/import-declarations.py.txt": "fdc62442f2a6b72dd5e78dbb4236f2f0788db064c13d608f891d88a799dd31e8",
    "harness/inspect-recording.py.txt": "04bb53d255519370f48b40c878a9e92bc3e43dfb258bf0fdc81c2f664b6c3757",
    "harness/rehearse.sh": "2a3007a748be997f199cd4cc74705b92452e425c6dbd3e9f3fd8b5f7fbadc2b8",
    "identities.env": "6e4db55e540cc4b02aae5c87a547d1127a77d69928cd086c198a693973879b02",
    "import-declarations.json": "98769b77156e3ec88358448d7c35aec0f8a52acb8551b875af1007ca7b6a96ae",
    "manifests/collector.yaml": "6e281d72be86e26e22ecd079eaea3e433373a58fae8db6d3f6c8a791928b74ee",
    "manifests/legacy-pricing.yaml": "aac92f26706d9c6c8236cbf475f5f559bdc4f0f46a6311d82c9454e383350777",
    "manifests/orders-canary.yaml": "8bcef077fe8038c856de2c08b1d98c14b8c383a76992e3f0cdd1c4d3a426b0ee",
    "manifests/orders.yaml": "9849e843cf9827ee8e7b7289b5b4dcb2c4179f5337ffa18d93e29c641844eede",
    "manifests/pricing.yaml": "d60f7b04af6c6416f54f472c69e33336f3d768242b029c60f91fcbc910ba9f3a",
    "otlp.jsonl": "76fe0043a9c0da853169b55e1767c38eceeb2e2294bc038a10861f752d0c5eac",
    "recording-inspection.json": "08b81397695b0d7e31a2e28d26f4a60fce40df288b710cbec727b2fed6eb86dd",
    "replay/analyze.py": "774d459fa6387b13dbcfc41418235277656f02c6371ff07ae35402fc26ff4725",
    "replay/collector-replay.yaml": "be565a74f10fa2be09de0bb23087cdebfb9d7ea4782945d58fabe6fdada01d86",
    "replay/replay.py": "e60155a90f0c1fb299a315d0107c961291fac51557ed0d9ab1e87c1a0c3b21ed",
    "run-log.txt.gz": "045f7921223256d77bd02be343922a17cac40dbe15975c53430255b07fe2f9fb",
    "source-registration.json": "55e6855aefd3ac3d9f27d3488b7e47d83d77a3361fa98f36113668ccdcbdb691",
    "teardown.log": "973392caa307ca121b45036a0e03da6dd290257e39f652b8f305fb5857a2d1d0"
  },
  "recorded_requests": 52
}
```
