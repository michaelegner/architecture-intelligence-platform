# AIP v0.5.0 I5 — Completion Record

**Status:** COMPLETE (`FINAL_CANDIDATE_QUALIFIED`) once the Slice 7 PR carrying this record merges.
I5 qualification is neither a publication decision nor evidence of a shipped artifact; I6 owns
release (spec §16, §17).

This record covers the governing specification
[`i5-cross-system-qualification.md`](i5-cross-system-qualification.md), Draft 0.3 (#238). I5 answered
§1's question on two materially different real systems:
- **Quarkus Super Heroes**, pin `8ea0337`, with its upstream Kubernetes manifests;
- **Apache Airflow 3.3.1**, pin `3adbbe1`.

Both targets were frozen before inspection, run, corrected where the evidence required, and
revalidated in full at one final candidate:

> **Candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9` is `FINAL_CANDIDATE_QUALIFIED`.**

The evidence is
[`../../real-world-validation/v0.5.0/final-candidate/finding-ledger.md`](../../real-world-validation/v0.5.0/final-candidate/finding-ledger.md).

## Run identity

| Item | Scope | Merge commit | PR # |
|---|---|---|---|
| Spec Draft 0.1 | I5 specification | `3f413f63ac904b4327821cc8c973de42a05a3b9c` | #235 |
| Spec Draft 0.2 | Increment-spec structure, parent §33 decisions | `b868732df159ba47741f9ac3f3ce506f79921055` | #236 |
| Slice 1 | Qualification tooling foundation | `9c123aab261c97ec882e27743a49b4108a9534a5` | #237 |
| Spec Draft 0.3 | Namespace-less upstream Quarkus manifests | `41b2ee17051eedecbf9600a6f813f041eea2673b` | #238 |
| Slice 2 | Quarkus v0.5 freeze dossier (**the Quarkus freeze**) | `ef503a536910fd834fe4d58851b6c172c8ab8255` | #240 |
| Slice 3 | Airflow v0.5 freeze dossier (**the Airflow freeze**) | `17607864a8963487b3b2de1395f6346ad035b12d` | #242 |
| Profile hardening | Both profiles hardened against environment and Compose overrides (not a re-freeze) | `8b5e6f20d69cfd813b376cbf47e1d8f223036ee1` | #243 |
| Slice 4 | Supporting-evidence and lifecycle freeze | `8432efa56d7cf26ccf7890ec5f17435a0639fcfb` | #244 |
| Bindings layout | Dossier input correction (F5); the Slice 5 candidate | `174a17c5d0f8be35291032c677585291c330cc0a` | #246 |
| Slice 5 | Qualifying runs, results, finding ledger F1-F7 | `e5f272c085f267e0d8ce6e4260c5f94e68e46796` | #253 |
| Slice 6 (F2 FIX) | Versioned I1 §10 import report `aip-import-report/1` | `efca20d48eb76559c842ab282abe7b3a6df729a8` | #254 |
| Slice 6 (F1 FIX) | Canonical-validation failures become per-source results | `b0aa67ae748eb51bbe047c0c2f21e5b0af5fd945` | #255 |
| Slice 6 (F7, F6) | I5 §6 re-freeze of the Quarkus lifecycle X; `without_x.py` | `d6d9f97d33db2cf8584be0ba19374e366fb98f54` | #256 |
| Pre-Slice-7 amendment | L4a/L4b/L6 result labels frozen before the run; **the final candidate** | `aa04a150965924bd23ecf0125bcf7095a3cf72d9` | #257 |
| Slice 7 | Final-candidate revalidation, this record | this PR's own merge commit (not citable from inside this record; see Immutable qualification identity) | this PR |

A first Slice 5 attempt at `34067b7` was aborted before any comparison (F5). Its records are
summarized in the Slice 5 ledger and are not a qualifying run.

**Rule identity at the candidate:**
- **Snapshot and schema:** `_CANONICALIZATION_VERSION = 3`
  (`app/architecture_intelligence/repository.py`). The public Architecture Answer
  `schema_version` is `"0.5"`, under `schemas/architecture_intelligence/v0.5` (git tree
  `02db433c773ebd17df17b016b647218025d65ad0`).
- **Import report:** `aip-import-report/1`, under `schemas/import/v0.5` (git tree
  `953b15e590ffbb1caa5bda89539e5f164f618466`).
- **Adapters:** `openapi-adapter@1` v1, `asyncapi-adapter@1` v1, `manifest-adapter@1` v1 and
  `kubernetes-adapter@1` rule 1.
- **New diagnostic codes in I5:** `MANIFEST_CALL_SOURCE_UNRESOLVED` and `CANONICAL_MODEL_INVALID`
  (#255).

## Frozen inputs and fixture identities (git trees at the candidate)

| Artifact | Identity |
|---|---|
| Quarkus dossier `docs/real-world-validation/v0.5.0/quarkus-super-heroes` | tree `293d1a25652b3199c0e66ffc8fcfbe92ac5f3dd3` (runtime `b553edd12ab1ec3257e81e543dcaa78d05242cec`) |
| Airflow dossier `…/apache-airflow` | tree `194bd7e3f1b8d530648dd84d21b44c13eb2c8eac` (runtime `3d6226920f2ad152678c8beea692d28c460ab4b6`) |
| Lifecycle ledger and mutations `…/lifecycle` | tree `7525b0bfa6911a38223e2d24712b5263b222dfc7`. The step digests are pinned in `tests/unit/test_i5_lifecycle_freeze.py`. |
| Frozen queries `…/queries` | tree `c7b377f4deab1fa18c582207bafe781bfdead8a7` |
| `coverage-matrix.md` / `public-surfaces.md` | blobs `05e71e2c8e6cfb3135d4c863fa58cd169cf7f231` / `a009911fb54354ce5b0ffc6a5284ed0658516e30` |
| I5 specification | blob `7b31bda8bee266393e387b9eab7b113ff6949925` |
| I2 independent capture fixture | `tree_digest` `ae995c5f25649861c381c9870aff98cd6dbc3f9e137940fada2016227d156bb6` |
| I3 cross-source fixture | `e4034677a15053215fa7a89d744fde04e56a9206e46ca3bf48983e158096e9bd` |
| I4 Pub/Sub fixtures / Kafka | `1dd57b82092c43f452328fcb474bcc8d978db127507391370e8dc7934cf06ca3` / `326c4bf3e0c90561041d1f306ea00533470041a19bf664142d61da8b92acf67a` |
| Evaluation scenarios | `98ab04c8cf0a464ab88dfdc423ea261616ee1f7493f5261ed24615872c039aa0` |

The fixture digests are the `coverage-matrix.md` pins, which `test_i5_lifecycle_freeze.py` asserts
at the candidate.

## Final-candidate run identities (2026-09-25; one clean checkout at the frozen location)

| Run | Identity |
|---|---|
| Quarkus | AIP image `sha256:5573927999a4b845d11b485c0206063649f4c6fa67aee6e82b4bffc468587a09`. The six service images were rebuilt with `--no-cache` at `8ea0337` (`../../real-world-validation/v0.5.0/final-candidate/quarkus-super-heroes/artifacts/service-images`). The window was `2026-09-25T13:06:47Z` to `13:06:54Z`. |
| Airflow | AIP image `sha256:b8975d29964e1aa414e8e62fa0a74c655b150cf5dc4b6b2b12993d9956a40fcf`. The window was `2026-09-25T13:18:45Z` to `13:19:14Z`. |
| Lifecycle | AIP image `sha256:1bf871c401e7d1f1eb25568c036831df937b61cc3466c278bcb8111d85cbd879`, used by the 9 steps on each target and by the supplementary L1 snapshot replay |
| Evaluation | Two runs, byte-identical, result sha256 `03dc173098a92806c3c32dc714219636b37a11ceeeb50231a855c7ec958bb92c` |

Each AIP image was built with `--no-cache` from the verified clean candidate. Each running container
was checked against its image id and `AIP_BUILD_REVISION`. The image ids differ between runs because
the builds are not byte-reproducible; identity is established per run.

## Immutable qualification identity

This section is record-only. The Slice 7 PR adds records and documentation only: `docs/`, with no
code, test, fixture, schema or runtime-input change. So the qualified candidate is the
already-merged `aa04a150965924bd23ecf0125bcf7095a3cf72d9`, and the record never cites its own
merge commit.

**CI at the exact candidate SHA,** read through the GitHub check-runs API, not through
`gh pr checks` (`../../real-world-validation/v0.5.0/final-candidate/suites/ci-check-runs.tsv`). All seven check-runs are `success`:
- `analyze (actions)` and `analyze (python)`, which are CodeQL;
- `demo-e2e`;
- `dependency security scan (pip-audit, spec §29)`;
- `integration-core`;
- `lint + test`;
- `quality`.

**Local suites at the candidate:** `tests/unit` 2221 passed, and `tests/integration` 466 passed
(`../../real-world-validation/v0.5.0/final-candidate/suites/`).

## §16 Definition of Done

| Condition | Evidence |
|---|---|
| Both dossiers frozen before their first qualifying comparison | #240 and #242, before Slice 5. The lifecycle (#244), its correction (#256) and the result labels (#257) were each frozen before the runs that use them. |
| Both fresh real-system comparisons complete | Quarkus 45/45 and Airflow 9/9 `CORRECT`, with 0 incorrect, at the candidate |
| Every §9 row qualified or recorded as a gap | Final ledger rows 1-15. Rows 7, 8, 9 and 13 are fixture-only by design. |
| Every §13 item holds at one candidate | The final ledger's §13 table, with F8's limitation stated |
| Every finding has exactly one disposition; no material supported mismatch unresolved | F1-F8 (next section) |
| Every `FIX` meets §11 and none is target-specific | #254 and #255. Each has a contract-level explanation, distilled regressions, guard proofs, and a two-target impact test. Neither adds a product name, alias or special case. |
| §12 byte-identity evidence recorded | `../../real-world-validation/v0.5.0/final-candidate/evaluation-artifacts/summary.txt` |
| This record pins the candidate, revisions, digests, run identities, CI evidence, limitations and the I6 handoff | this document |

## Findings and dispositions

| Id | Finding | Disposition |
|---|---|---|
| F1 | A canonical-validation failure escaped as HTTP 500 | `FIX` (#255) |
| F2 | The import report omitted I1 §10 content | `FIX` (#254) |
| F3 | Airflow OpenAPI `SCHEMA_COMPOSITION_UNINTERPRETED` | `DOCUMENT_UNSUPPORTED` |
| F4 | A relation-less `OBSERVED_ONLY` `service:grpc-locations` | `NO_CHANGE` |
| F5 | A dossier bindings-layout defect; no diagnostic for un-enumerated files | `DEFER` |
| F6 | A `without_x.py` header on an empty result | `NO_CHANGE` for AIP (harness fixed in #256) |
| F7 | The frozen Quarkus lifecycle mutation was invalid | `NO_CHANGE` for AIP (I5 §6 re-freeze, #256) |
| F8 | Unsupported Kubernetes kinds cannot be attributed per object; the false "server log" claim | `DEFER`; the docs claim is corrected in this PR |

The full entries are in the Slice 5 ledger (F1-F7) and the final ledger (F8 and the final outcomes).

## Limitations and unsupported constructs (explicitly disclosed)

- **gRPC, Kafka `fights`, and the legacy OTel messaging operation key** are `UNSUPPORTED` on Quarkus.
  Kafka creates no Queue, Topic or Subscription fact. The consumer-group boundary holds.
- **Postgres** is `UNSUPPORTED`, the **roles and Execution API** are `UNRESOLVED_IDENTITY`, and
  **Celery** is `INSUFFICIENT_EVIDENCE` on Airflow.
- **F3:** Airflow schema composition is structurally preserved but uninterpreted.
- **F5:** a present but un-enumerated declaration file produces no diagnostic.
- **F8:** `K8S_RESOURCE_UNSUPPORTED` names the file and kind, not the object. Import diagnostic
  messages are neither in the report (by design) nor in the log.
- **Coverage gaps on the real targets:** I3 Path A (no upstream annotation evidence) and
  messaging-claim parity (both targets are messaging negatives). Both are covered only by
  supporting fixtures, which are not real-system evidence.
- **Name similarity never resolves `DEPLOYED_AS`,** by design: rest-narration and event-statistics
  stay unresolved.

## Handoff to I6 (§17)

I6 receives:
- the qualified candidate `aa04a150965924bd23ecf0125bcf7095a3cf72d9`;
- the frozen dossiers and the coverage matrix (identities above);
- the finding ledgers (Slice 5 and final), their dispositions, and the limitations above;
- the byte-identical evaluation evidence.

I6 performs its own exact clean-checkout release gates and records distinct candidate, evidence and
decision identities.

**Notes for I6:**
- **The evaluation report is not refreshed.** The committed
  `evaluation/architecture_answers/results/architecture-answers-evaluation-result.json` still
  reflects an earlier candidate. Refreshing it is I6's job.
- **Deferred follow-ups outside I5:**
  - an object identity in the unsupported-resource pointer, and either logged diagnostics or a
    corrected `app/ingestion/import_report.py` docstring (F8);
  - a diagnostic for un-enumerated files (F5).
- **Product version.** The answers' `producer.version` at the candidate is `0.4.2`, the unchanged
  project version. Versioning the release is I6's decision.

## I5 exit statement

I5 is complete. Both real systems were qualified against independently frozen ground truth at one
candidate. Every §13 item holds. Two general, evidence-justified FIXes (#254, #255) were made
without any target-specific production change, and every limitation is explicit.
