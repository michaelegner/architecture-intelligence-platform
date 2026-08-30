# AIP Evaluation Suite

Deterministic evaluation kernel for AIP, implementing Iteration 1 (`v0.2.0-alpha.1`) of
[`docs/specifications/0.2.0/i1-evaluation-kernel.md`](../docs/specifications/0.2.0/i1-evaluation-kernel.md).

> **Status:** I1.1 (evaluation skeleton) - scenario discovery and `expected.yaml` validation only.
> End-to-end execution against AIP (ingesting fixtures, injecting runtime telemetry, projecting
> canonical facts, comparing against ground truth, and reporting PASS/FAIL) lands across I1.2-I1.4.
> This file will be expanded to cover the full I1 Definition of Done (spec §21) once execution is
> implemented.

## Running

```bash
uv run python -m evaluation run
uv run python -m evaluation run 01-rest-confirmed
uv run python -m evaluation run --scenario 01-rest-confirmed
```

## Scenarios

Three scenarios live under `evaluation/scenarios/`, each a self-contained directory with an
`expected.yaml` declaring the scenario's scope and expected canonical facts:

- `01-rest-confirmed`
- `02-rest-observed-only`
- `03-async-confirmed`

See the I1 specification for the full rationale and schema.
