# v0.7.2 I1 — Hosted six-tool deployment record

Governing: the [v0.7.2 specification](specification.md) §3. The hosted Pitstop demo now serves the
complete six-tool v0.7.1 surface through its public read-only edge. Its dataset is unchanged; the
move to Sokol111 is I2.

## Deployment (2026-10-21)

| Item | Value |
|---|---|
| Public MCP endpoint | `https://mcp.daip.io/mcp` (anonymous, read-only; the host is not named here) |
| AIP image | `ghcr.io/michaelegner/architecture-intelligence-platform@sha256:2f6f2a211da941bb48a27e5d90d0732facf66913509153870e8db5d88d850a47`, the published v0.7.1 digest ([release record](../../release-validation/v0.7.1-release-record.md)). The previous image was the v0.6.3 digest `sha256:e6632982…0a50fe` |
| Identity in the answers | `producer.version 0.7.1`, `build_revision b0d7448469cb2e84acf09a2759f061767822eaba` |
| What changed | The owner set the image digest in the deployment's environment file and recreated only the AIP service (`docker compose up -d --no-deps`). Unchanged: the graph volume, Neo4j, the Collector, the traffic generator, the Pitstop services and the Caddy edge with its configuration |

## External check

Run with `examples/pitstop-demo/hosted/verify_public_edge.py --url https://mcp.daip.io/mcp`, from
outside the demo network with no credentials. The completed UTC day was 2026-10-20. The rate-limit
check was not enforced, because no threshold was given; the edge configuration is unchanged.

| Check | Before (15:18:30Z, v0.6.3) | After (16:02:18Z, v0.7.1) |
|---|---|---|
| anonymous initialize | PASS | PASS |
| tool inventory (six-tool allowlist) | **FAIL**: `get_api_consumer_usage`, `get_destination_consumers` missing | PASS: exactly the 6 allowlisted tools |
| Pitstop answer + evidence drill-down | PASS: 12 refs, resolved on its snapshot | PASS: 12 refs, resolved on its snapshot |
| source-dependent tools refuse | **FAIL**: `get_api_consumer_usage` unknown | PASS: `get_api_consumer_usage` `MEASUREMENT_WINDOW_NOT_AVAILABLE`; `get_destination_consumers` `UNKNOWN_DESTINATION` |
| non-MCP routes closed | PASS (10 routes) | PASS (10 routes) |
| invalid Host rejected | PASS (empty 200) | PASS (empty 200) |
| oversized body rejected | PASS (413) | PASS (413) |
| rate limit | SKIPPED | SKIPPED |

The "before" run showed that both new checks fail against the four-tool deployment. On Pitstop the
two source-dependent tools answer `NOT_ANSWERED` with one typed refusal and `data: null`: the demo has
no gateway or Kafka source, so there is nothing to evaluate. A positive answer from either tool would
fail the check.

## Notes

- Three Pitstop services (`customermanagementapi`, `vehiclemanagementapi`, `workshopmanagementapi`)
  had reported `unhealthy` for 13 days before the redeploy. That is outside I1. The 2026-10-20
  dependency answer was `ANSWERED` with 12 evidence refs.
- The hosted image is v0.7.1, so it still has the pip-bundled `certifi` and `ca-certificates` findings
  accepted in the v0.7.1 release record. The v0.7.2 image (with #617) replaces it at release.
