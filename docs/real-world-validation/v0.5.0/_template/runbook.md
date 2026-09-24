# Runbook — `<system-id>` (v0.5.0)

Ordered, reproducible process (I1 §28). Mark any manual step explicitly.

1. **Prerequisites** — <!-- tooling, Docker, credentials (none secret) -->
2. **Fetch pinned upstream version** — <!-- exact commands against upstream.md's pinned commit -->
3. **Configure profile** — <!-- apply profile.md's configuration -->
4. **Start system** — <!-- ordered startup commands -->
5. **Enable/configure telemetry** — <!-- OTLP endpoint/Collector config -->
6. **Exercise declared validation flows** — <!-- traffic/exercise procedure from profile.md -->
7. **Import declared architecture sources into AIP** — <!-- OpenAPI/AsyncAPI/manifest ingestion -->
8. **Send/capture runtime observations** — <!-- OTLP ingestion into AIP -->
9. **Query/capture AIP result** — run from the dossier's one absolute checkout location (I5 §12).
    Pass `--aip-config` whenever expected.yaml has `deployments`:
    ```bash
    uv run python -m real_world_validation capture --neo4j-uri ... --neo4j-user ... \
      --environment <env> --since <ts> --until <ts> --scope-entities <ids> \
      --aip-config <aip-config.yaml> \
      --out docs/real-world-validation/v0.5.0/<system-id>/artifacts/actual.yaml
    ```
10. **Execute comparison** —
    ```bash
    uv run python -m real_world_validation compare \
      --expected docs/real-world-validation/v0.5.0/<system-id>/expected.yaml \
      --actual   docs/real-world-validation/v0.5.0/<system-id>/artifacts/actual.yaml
    ```
11. **Store deterministic report** — <!-- save the comparator's output into results.md -->
12. **Tear down environment** — <!-- reset upstream/broker/AIP graph/telemetry state to clean
     (I1 §29); a validation must not depend on unexplained data from an earlier run -->
