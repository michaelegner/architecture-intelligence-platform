# I5.2 actual controlled-reference qualification

Governing: merged v0.6.0 I5 revision 0.1 §§4-5, I1 E1-E7 and the frozen I3 public contract.
This adds qualification tooling only; it does not change production code, public APIs or defaults.

The independent oracle is `tests/fixtures/locality/two-workload-capture/expected.md`.
Michael Egner adopted its source-derived facts before evaluation. `expected_actual.py` prepares
source-only facts for review using the original recording/captures and the frozen v2 key helper;
it never imports AIP. Do not regenerate or rewrite the adopted dossier to fit output.

From a clean candidate checkout, with Docker available:

```bash
uv run python -m evaluation.i5.qualify run \
  --candidate <explicit-40-hex-checkout-SHA> \
  --expectation-commit <prior-oracle-commit-SHA> \
  --output /tmp/i5-qualification
```

The runner verifies original checksums, owner adoption, the unchanged expectation commit and its
ancestry before ingestion. It builds the production image with the candidate's `AIP_BUILD_REVISION`.
Two independent worker processes each start fresh Neo4j/AIP/Collector containers. Each imports C1,
replays the original recording exactly once through the pinned JSON-to-protobuf Collector, evaluates
C1, replaces capture bytes at the same configured `capture` root, then imports/evaluates C2.
The original acquisition files remain read-only; no live Kubernetes cluster is needed.

Each state checks actual unfiltered inventory, selected comparison, same-snapshot v2/capture refs,
wrong-caller/Operation authorization and unknown local coverage. C2 also checks retained counts,
missing-P1 abstention and stale C1 evidence/query/cursor refusal. A protocol-generated C1 cursor
is labelled a negative control: this two-candidate recording emits no continuation. Existing frozen
pagination, cap, declared-only and missing-attribute regressions remain separately synthetic.

Artifacts retain requests, direct-service answers, actual HTTP REST and initialized negotiated MCP
responses, graph state/revisions, candidate/image/config/source identity, process/container IDs,
commands and failures. Semantic outputs are serialized to canonical JSON bytes and compared directly;
only REST/MCP transport wrappers are removed, with no field masking or identifier normalization.
The A/B comparator requires the complete fixed artifact set, so missing cases cannot pass silently.
Wire checks require one Collector success and one AIP HTTP 200 per recorded request.

Run the repository's required local gate separately: Ruff format/check, Pyright, import boundaries,
unit and integration suites. The existing frozen upstream scenario/dossier and no-v2 tests are reused;
I5.3 owns the new per-system dossier presentation and task-led walkthrough. Report every skip/failure
and the exact qualification scope. I6 must rerun against its final candidate; this is not release
readiness, product-pilot validation or production-capacity evidence.
