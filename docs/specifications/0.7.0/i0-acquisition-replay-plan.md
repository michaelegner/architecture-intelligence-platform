# AIP v0.7.0 I0 — Selected-Source Acquisition and Replay Plan (APISIX)

**Status:** Frozen (merged #509). Artifact 4 of spec §15.
**Governing specification:** [`i0-gateway-capability-survey-and-semantic-freeze.md`](i0-gateway-capability-survey-and-semantic-freeze.md) §10; decisions in [`i0-source-selection-decision.md`](i0-source-selection-decision.md) §§4–5. Evidence: [`i0-spike/`](i0-spike/README.md).
I1 owns the configuration adapter; I2 owns measurement acquisition and replay. This plan only freezes the acquisition contract far enough to show both are feasible.

## 1. Pins

| Item | Pin |
|---|---|
| Product | APISIX **3.19.0**, `apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141` |
| Config store | etcd v3.5.16, `quay.io/coreos/etcd@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159`, APISIX `config_provider: etcd` |
| Upstream (fixtures) | `traefik/whoami@sha256:43a68d10b9dfcfc3ffbfe4dd42100dc9aeaf29b3a5636c856337a5940f1b4f1c` |
| Credentials | Fake only (`SPIKE-FAKE-…`); no external accounts |

## 2. Configuration acquisition (I1)

Surface: **Admin API** (`/apisix/admin/…`), not standalone YAML (a duplicate username is overwritten silently there, F12).

1. Read, per resource kind in scope (consumers, per-consumer credentials, routes, services, upstreams, plugin_configs, consumer_groups, global_rules), the full list. Only consumers, credentials' ids, routes and services are interpreted; the others are recorded as unsupported scope when they reference or carry a `consumer-restriction`.
2. Record the etcd **header revision before and after** the reads. If they differ, the capture is refused and retried (consistency rule; the Admin API list is not documented as a single-revision read).
3. Revision identity of the capture = the etcd header revision plus the APISIX version; per-object `createdIndex`/`modifiedIndex` are retained for provenance. `create_time`/`update_time` are volatile and are dropped by normalization.
4. **Redact before anything is stored:** drop every `key-auth.key`, credential `plugins.*.key` and any token; keep the consumer `username`, credential ids and the plugin names present. The Admin API returns these values in plaintext on read (F15), so redaction is mandatory in the acquisition code, not in storage.
5. Authoritative inventory/removal scope: the objects of the interpreted kinds under the captured gateway instance's etcd prefix at the recorded revision. An object absent from a complete accepted capture is removed from that source's state; a failed or partial capture removes nothing (parent §13).
6. Normalization: sort by resource id; sort object keys; strip volatile fields (§2.3). The normalized capture is the replay artifact.

## 3. Measurement acquisition (I2)

1. Surface: the `prometheus` plugin text endpoint (default `127.0.0.1:9091/apisix/prometheus/metrics` in the spike).
2. **Settle before capture.** Counters lag behind traffic (F4). The capture waits until two consecutive scrapes are identical, with an explicit timeout, and records the number of scrapes taken. An unsettled capture is `UNKNOWN_COVERAGE`.
3. Keep only `apisix_http_status` series; drop the `node` label (runtime IP); sort lines. This normalized extract is the replay artifact (matches `i0-spike/apisix/expected-capture.txt`).
4. The capture manifest records: gateway instance id, **operator-asserted environment**, capture instants (start of window, end of window), APISIX version, the Plugin Metadata `disabled_labels` for `prometheus`, whether the `prometheus` plugin was enabled for each route in the window, the settle result, and the asserted "no restart in the window" (decision §5.3–5.4).
5. Each series becomes an observed fact under the interpretation of the decision record §5.2.

## 4. Fixture and replay format

- A fixture is a directory holding the redacted normalized configuration capture, the normalized measurement extract and the capture manifest, all JSON/text. Exact file names and schema are an I1/I2 deliverable (they are not part of the public contract, O10).
- Replay reads the fixture only. It never contacts a gateway, so it is independent of uncontrolled SaaS state.
- **Equality boundary.** The artifacts that must be byte-identical across runs are the *normalized, redacted* configuration capture and measurement extract. Raw vendor output (timestamps, ordering, node IPs, ciphertext of keys) is not compared.

## 5. Positive and negative cases the replay must support

| Case | Configuration | Measurement | Expected reading |
|---|---|---|---|
| P1 | whitelist contains C on route R | `response_source="upstream"` for (R, C) | configured; usage established |
| P2 | whitelist contains C on R | no series, closed-world asserted | configured; measured zero in window |
| N1 | whitelist contains C on R | no series, coverage unknown (unsettled, restart, label blanked) | configured; usage unestablished |
| N2 | C not in whitelist | `response_source="apisix"` 403 for C | rejected attempt only; no usage, no access fact |
| N3 | any | `consumer=""` series | unattributed; no consumer use |
| N4 | whitelist contains C on R | a series for C on a route other than R | usage on another route; not usage of R |

P1 and N2/N3 are already shown by the spike capture (one run); P2/N1/N4 need extra fixtures in I2. These cases are inputs to I2's truth table (O8), not a vocabulary.

## 6. Spike evidence index

Normalized replay twice, byte-identical: `i0-spike/apisix/run.sh` vs `expected-capture.txt`. Admin API duplicate, credentials, plaintext read, revision and inventory: `i0-spike/apisix-etcd/probe.sh` and `probe-output.txt` (F13–F16).
