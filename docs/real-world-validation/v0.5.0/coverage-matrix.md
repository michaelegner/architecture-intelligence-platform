# I5 Coverage Matrix (frozen, Slice 4)

This is I5 §9's matrix with every row's evidence type, frozen source revision, qualifying step or
test, and required outcome. Slice 5 runs every row against one candidate, and the Slice 7 report
reconciles it row by row. **An area with no eligible evidence is a gap and is never claimed
qualified.** Supporting fixtures are never called real-system evidence (I5 §9).

**Revisions:**
- The real-target dossiers are frozen at their merge commits: Quarkus #240 `ef503a5`, Airflow #242
  `1760786`. Two post-freeze corrections apply. Neither changes an expected fact, the scope or a
  comparison rule (see each `profile.md` "Revision history"):
  - the profile hardening in #243 `8b5e6f2`;
  - the input-layout correction in #246. It moves each dossier's bindings document, with unchanged
    bytes, to `runtime/declarations/bindings/architecture-identity-bindings.yaml`, the path that
    `FilesystemSourceDiscoverer` enumerates. It also moves the lifecycle `mutate.py` `BINDINGS`
    path, which re-pins the lifecycle step digests.
- The Slice 5 candidate is #246's merge commit. The Slice 5 results record it, because a merge
  commit is only known after the merge. An earlier Slice 5 attempt at `34067b7` aborted on the
  defect #246 corrects. It is disclosed in the Slice 5 results and is not a qualifying run.
- Each fixture is pinned by a content digest: sha256 over the sorted `relative-path NUL
  sha256(bytes)` lines of every file (`lifecycle/mutate.py::tree_digest`), plus its git tree at
  `8b5e6f2`. `tests/unit/test_i5_lifecycle_freeze.py` asserts every digest.

| # | Area | Evidence type | Source and frozen revision | Qualifying step or test | Required outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | I1 lifecycle | Real declarations | Both dossiers' declarations, mutated per `lifecycle/` (#244; bindings path corrected in #246; Quarkus X corrected under I5 §6 for finding F7, see `lifecycle/README.md` "Revision history") | `lifecycle/runbook.md`, steps S0-L3 per target | Every `lifecycle/README.md` expected outcome |
| 2 | I1 lifecycle (not safely inducible upstream) | Regression (existing I1 tests) | `tests/integration/test_importer.py`, `tests/unit/test_orchestrator.py`, `test_sources_tombstones.py`, `test_sources_removal_authority.py`, `test_sources_replay.py` at the candidate | The full `tests/unit` + `tests/integration` suites | Pass. Regression evidence only. |
| 3 | I2 offline discovery | Upstream-derived input | Quarkus `runtime/k8s/namespaced/` (sha256 `4ba52254…`), #240 | Quarkus runbook steps 6 and 11, and the `ground-truth.md` manual checks 1-2 | `ACCEPTED_WITH_LIMITATIONS` with exactly the frozen limitation list. 13 Workloads, 13 Kubernetes Services, 1 Ingress and 2 routes, all `DECLARED_MANIFEST`. No interaction fact. |
| 4 | I2 namespace-less rejection | Upstream-supplied input | Quarkus `runtime/k8s/unmodified/` (sha256 `a1cd8183…`), #240 | Quarkus runbook step 6 | `REJECTED_INVALID` (`K8S_RESOURCE_INVALID`), and nothing commits |
| 5 | I2 captured resources and owner chain | Independent capture (AIP-operated `kind`; not a third target) | `tests/fixtures/kubernetes/i2-independent-capture`, digest `ae995c5f25649861c381c9870aff98cd6dbc3f9e137940fada2016227d156bb6`, tree `8cd33bf1060ac6bf9991c28bff34ae4a839650ce` | `tests/integration/test_kubernetes_independent_capture.py` | Pass. Supporting evidence only. |
| 6 | I3 Path B, and the name-only negative | Real target plus a disclosed mapping | Quarkus `runtime/mapping.yaml` and `expected.yaml` `deployments`/`forbidden.deployments`, #240 | Quarkus capture (`--aip-config`) and compare | 3 `RESOLVED_CONFIGURED` outcomes with `[RESOLVED_CONFIGURED]`. The rest-narration and event-statistics pairs never resolve. |
| 7 | I3 Path A (explicit annotation) | **Gap on the real targets**: no upstream Workload carries the annotation (Quarkus `upstream.md`). Covered only by a fixture over a real capture. | `tests/fixtures/deployment/i3-cross-source`, digest `e4034677a15053215fa7a89d744fde04e56a9206e46ca3bf48983e158096e9bd`, tree `007e2325f271c87abd81af4fc404396c8702c093` | `tests/integration/test_i3_cross_source_qualification.py` | Pass. Supporting evidence only. |
| 8 | I3 Path C, conflict, ambiguity | Hand-authored fixture over a real capture | The same fixture as row 7 | `test_i3_cross_source_qualification.py` (Path A vs B and A vs C conflicts, all-paths agreement, ordering, zero writes) | Pass. Supporting evidence only. |
| 9 | I4 positive (fan-out, competing consumers, scoped DLQ) | Hand-authored fixtures; no live broker | `tests/fixtures/pubsub` (ASB, GCP), digest `1dd57b82092c43f452328fcb474bcc8d978db127507391370e8dc7934cf06ca3`, tree `e738c43a69ad04193932ff4b35c947b3dbe63221` | `tests/integration/test_i4_pubsub_qualification.py` | Pass. Supporting evidence only. |
| 10 | I4 negative (consumer group ≠ Subscription) | Real target plus a fixture | Quarkus Kafka `fights` (`expected.yaml` scope closure and forbidden facts, #240), and `tests/fixtures/pubsub/kafka` (digest `326c4bf3e0c90561041d1f306ea00533470041a19bf664142d61da8b92acf67a`, inside row 9's tree) | Quarkus compare, the manual check "no messaging entities", and `test_i4_pubsub_qualification.py` | No Queue, Topic or Subscription, and no `SENDS`, `PUBLISHES_TO` or `RECEIVES_FROM` for `fights` |
| 11 | Airflow messaging negative | Real target | Airflow `expected.yaml` (scope closure over `queue:default` and forbidden facts), #242 | Airflow compare, and the manual check "no messaging entities" | No messaging fact is guessed. Celery stays `INSUFFICIENT_EVIDENCE`. |
| 12 | Public answers and provenance | Real runs | `public-surfaces.md` (this PR), and `queries/Q-GRAPH.cypher` | `public-surfaces.md`, per target | Service = REST = negotiated MCP. Same-snapshot drill-down. Exactly three MCP tools. Zero writes (the Q-GRAPH digest is unchanged). |
| 13 | Public messaging-claim parity | **Gap on the real targets**: neither target has a supported messaging claim. Covered only by fixtures. | Row 9's fixtures | `test_i4_pubsub_qualification.py`, and `tests/integration/test_mcp_*_equivalence.py` at the candidate | Pass. Supporting evidence only. |
| 14 | v0.4 Architecture Answer contract | Regression | `evaluation/architecture_answers/scenarios`, digest `98ab04c8cf0a464ab88dfdc423ea261616ee1f7493f5261ed24615872c039aa0`, tree `44f44878f7550c1aca92541fb05ae6a6baefd55f` | `uv run python -m evaluation answers`, twice at the one frozen checkout location (I5 §12) | Byte-identical results, and the v0.4 contract preserved under the documented v0.5 changes |
| 15 | Import-report observability | **Pre-identified limitation** (`lifecycle/README.md`) | — | Every lifecycle step | Recorded in Slice 5 as a finding with one disposition. FAILED, PARTIAL and `REJECTED_CONFLICT` cannot be told apart through any surface. |

Rows 3-4 and 11 separate the upstream-derived, upstream-supplied and real-target negatives that
Draft 0.3 added to §9. Row 13 is the messaging half of row 12, split out because it has no
real-target evidence.
