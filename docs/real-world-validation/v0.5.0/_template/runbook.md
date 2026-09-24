# Runbook — `<system-id>`

Ordered, reproducible process (I1 §28). Mark any manual step explicitly.

1. **Prerequisites** — <!-- tooling, Docker, credentials (none secret) -->
2. **Fetch pinned upstream version** — <!-- exact commands against upstream.md's pinned commit -->
3. **Configure profile** — <!-- apply profile.md's configuration -->
4. **Start system** — <!-- ordered startup commands -->
5. **Enable/configure telemetry** — <!-- OTLP endpoint/Collector config -->
6. **Exercise declared validation flows** — <!-- traffic/exercise procedure from profile.md -->
7. **Import declared architecture sources into AIP** — <!-- OpenAPI/AsyncAPI/manifest ingestion -->
8. **Send/capture runtime observations** — <!-- OTLP ingestion into AIP -->
9. **Query/capture AIP result** — <!-- produce the actual-facts capture consumed by step 10 -->
10. **Execute comparison** —
    ```bash
    uv run python -m real_world_validation compare \
      --expected docs/real-world-validation/<system-id>/expected.yaml \
      --actual   docs/real-world-validation/<system-id>/artifacts/actual.yaml
    ```
11. **Store deterministic report** — <!-- save the comparator's output into results.md -->
12. **Tear down environment** — <!-- reset upstream/broker/AIP graph/telemetry state to clean
     (I1 §29); a validation must not depend on unexplained data from an earlier run -->
