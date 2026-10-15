# APISIX replay package (v0.7.0 I4.1c)

Frozen inputs of the I4 APISIX replay (I4 specification §5; decision record D4). Everything under
`r1/` and `r2/` is a **real capture** from the pinned containers, taken with the repository's own
tools. The committed bytes, not a regeneration, are the inputs: re-running the session does not
reproduce them (etcd revisions, instants, ports).

## Pins

| Component | Pin |
|---|---|
| APISIX 3.19.0 | `apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141` |
| etcd v3.5.16 | `quay.io/coreos/etcd@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159` |
| upstream | `traefik/whoami@sha256:43a68d10b9dfcfc3ffbfe4dd42100dc9aeaf29b3a5636c856337a5940f1b4f1c` |

Fake credentials only; the session asserts that no credential reaches the committed bytes.

## Real versus derived

| Case | Origin |
|---|---|
| `P1`, `P2`, `N1`, `N2`, `N3`, `N4`, `N4b`, `OBS` | real, revision R1, window W1 |
| `REVa`, `REVb`, `REVc` | real, revision R2 (a consumer removed from an allow-list, a Route removed, a Route added), window W2 |
| `EV`, `REVd`, `REVe` | structural: an evidence request at the first snapshot, and a cursor and a reference minted under R1 and presented after R2 |
| `W-INVALID` | **derived**: the real R1 manifest with `end_settled` set to `false`, applied to a copy at run time; the package is never written to |
| `W-NONE` | request-level: a window that was never imported |

`P2` is real: bob is allow-listed on `orders-route` (Prometheus enabled, window closed and settled)
and sends no traffic in W1, so the capture holds no series for him and the reading is a measured
zero, not an absent one.

## Files

- `expected-replay.json` is authored by `author_replay_expected.py` (stdlib only) from the traffic
  plan, before any capture or AIP run; `EXPECTED.sha256` is its digest and proves the readings did
  not change after the captures were taken.
- `capture_session.py` is the one-time session; `SHA256SUMS` covers every captured file.

## Discarded first attempt

The first session sent readiness probes through the gateway before window W1. They created series
that were outside the plan (for example alice on the shared Route), so that capture was discarded
and the session was re-run without probes (a fixed wait instead). `expected-replay.json` was not
changed between the two.
