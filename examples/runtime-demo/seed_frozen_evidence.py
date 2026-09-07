"""One-shot deterministic evidence seed for the v0.4.0 I3.4 hero demo (spec §41-43).

`traffic_generator.py`'s live loop uses wall-clock timestamps (`datetime.now(UTC)`) and runs
forever, which I3 spec §43 explicitly forbids for the hero demo: "The hero demo SHALL not rely on
a moving `now - 24h` window" and SHALL instead use "fixed bundled telemetry timestamps + fixed
explicit window". This script builds the *exact same* topology as
`traffic_generator.build_batch()` (same services, same undeclared OrderService ->
LegacyPricingService call), but pins every span's timestamp to `SEED_TIMESTAMP` below instead of
send time, and sends it once instead of looping - so `hero-demo.md`'s `get_architecture_drift`/
`get_evidence` calls can use a hardcoded, copy-paste observation window that never needs
recomputing relative to "now", and the demo's result is byte-for-byte reproducible across runs.

Run once, after `POST /api/import` and before calling the MCP tools - see
`examples/runtime-demo/hero-demo.md`. Does not affect `traffic_generator.py`'s own live-loop
behavior; the two scripts are independent entry points into the same span-building helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from traffic_generator import ENVIRONMENT, build_batch, send_batch, wait_for_declared_import

# Anchors every seeded span. Frozen deliberately - never derive this from wall-clock time. Must
# fall strictly inside [WINDOW_START, WINDOW_END) below, which `hero-demo.md`'s
# get_architecture_drift/get_evidence calls use verbatim as `observation_context`.
SEED_TIMESTAMP = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"

_FIXED_NANOS = int(SEED_TIMESTAMP.timestamp() * 1e9)


def _frozen_now_nanos() -> int:
    return _FIXED_NANOS


def main() -> None:
    wait_for_declared_import()
    batch = build_batch(now_nanos=_frozen_now_nanos)
    send_batch(batch)
    print(
        f"[seed-frozen-evidence] sent {len(batch.resource_spans)} resource span blocks anchored "
        f"at {SEED_TIMESTAMP.isoformat()}",
        flush=True,
    )
    print(
        "[seed-frozen-evidence] use this observation_context for get_architecture_drift/"
        f"get_evidence: environment={ENVIRONMENT!r} window_start={WINDOW_START!r} "
        f"window_end={WINDOW_END!r}",
        flush=True,
    )


if __name__ == "__main__":
    main()
