# AIP v0.5.0 I6 — Completion Record

**Status:** COMPLETE. The terminal outcome is **`SHIPPED_VERIFIED`**.

This record covers the governing specification
[`i6-release-candidate-publication-and-post-release-verification.md`](i6-release-candidate-publication-and-post-release-verification.md),
Draft 0.3 (§30). It is written after the post-release record was committed. It does not cite its
own merge commit.

## Terminal outcome

```text
SHIPPED_VERIFIED
```

## Identities

| Identity | Value |
|---|---|
| I5 semantic baseline | `aa04a150965924bd23ecf0125bcf7095a3cf72d9` (`FINAL_CANDIDATE_QUALIFIED`) |
| I5 completion | `1ebca5e96a24156179f0a57b5abbdfe9b51c1ee7` (#258) |
| `RELEASE_CANDIDATE_SHA` | `8f63c2369084df9c57535f9112fe2dfa17154505`. This is candidate attempt `rc.1`, the only attempt, with no candidate-level `NO_GO`. It is the #264 merge. |
| `EVIDENCE_COMMIT_SHA` | `fa8a72bc542d0aa774b4f849f162033f672e6a3f` (#265): [`v0.5.0-release-readiness.md`](../../release-validation/v0.5.0-release-readiness.md), `RELEASE_READY` |
| `DECISION_COMMIT_SHA` | `069944b949abc473c848dcb3e00ae74a8fce1f5b` (#266): [`v0.5.0-publication-decision.md`](../../release-validation/v0.5.0-publication-decision.md) |
| Publication authorization | **GRANTED** by the repository owner, for exactly the candidate and evidence above |
| Tag | `v0.5.0`, annotated tag object `5631b9e225661bbaeae35c8c999e5b4544383fba`. `FINAL_TAG_TARGET_SHA` = `8f63c2369084df9c57535f9112fe2dfa17154505`. |
| GitHub Release | [`v0.5.0`](https://github.com/michaelegner/architecture-intelligence-platform/releases/tag/v0.5.0), published 2026-09-26T18:25:00Z |
| `FINAL_RELEASE_WORKFLOW_RUN_ID` | `36262460652`, 1 attempt, `success` |
| `FINAL_IMAGE_DIGEST` | `ghcr.io/michaelegner/architecture-intelligence-platform@sha256:f3c5fdc3691cc10f1de3a190c83e4749c4aadd0c37bf7d0b5385c99de38f9b65` |
| `POST_RELEASE_COMMIT_SHA` | `4d0cf30a1060ce99b13e703dc4ae8bb3fcb7330e` (#267): [`v0.5.0-post-release-verification.md`](../../release-validation/v0.5.0-post-release-verification.md) |

## Final SBOM and security status

- **SBOM:** CycloneDX 1.6, 1223 components, SHA-256 `412dcac0…`. Its subject is
  `FINAL_IMAGE_DIGEST`.
- **Full Trivy report:** v0.70.0, unfixed findings included, bound to the same digest. It holds
  46 HIGH and 0 CRITICAL, the same set as the candidate image:
  - 44 Debian base-image OS findings, none with a fix available;
  - 2 packages vendored in the base image's system `pip` (`msgpack`, `setuptools`).
- **Disposition:** the repository owner recorded the final disposition as `KNOWN_LIMITATION`,
  bound to the final digest and run.
- **Blockers:** zero unresolved release-blocking findings.

## Slices

| Slice | Deliverable | PR / merge |
|---|---|---|
| Spec | Draft 0.1 (owner) plus the review findings as Draft 0.2 | #259, `3966a53` |
| Spec | Draft 0.3: the phased release golden path (§7) | #260, `a4f69d8` |
| 1a | Entry audit and the golden-path profile freeze | #261, `6d9e21b` |
| 1b-i | The golden-path harness (`run.sh`, `golden_path.py`, Compose) | #262, `c7b339d` |
| 1b-ii | The digest-bound release workflow (SBOM, full report) | #263, `7d228c1` |
| 1b-iii | Candidate preparation (0.5.0, release notes); its merge is `rc.1` | #264, `8f63c23` |
| 2 | Exact-candidate qualification: `RELEASE_READY` | #265, `fa8a72b` |
| 3 | Publication decision: **GRANTED** | #266, `069944b` |
| 4B | Publication: the tag, the GitHub Release and the release workflow | tag `v0.5.0`, run `36262460652` |
| 5 | Post-release verification: `SHIPPED_VERIFIED` | #267, `4d0cf30` |
| §24 | Status closure and this record | this PR |

## Known limitations

These are carried unchanged from the published release notes, the readiness record and the
post-release record:
- Kubernetes discovery is `OFFLINE_ONLY`. There is no live-RBAC qualification.
- One Service per Workload, and no locality semantics.
- Pub/Sub scope exclusions. The queue-only analyses do not traverse Pub/Sub.
- I5: F3 `DOCUMENT_UNSUPPORTED` (schema composition uninterpreted); F5 and F8 `DEFER`.
- Snapshot identity depends on the configured source-root path.
- Real-target coverage limits: gRPC, Kafka streaming and Postgres are unsupported. Some identities
  are unresolved, and some coverage is fixture-only.
- The v0.4.2 client matrix has not been re-qualified for v0.5.0.
- The evaluation report in the tagged source is the pre-refresh one (`a906a58`). The refreshed
  report is on `main`, identifying `8f63c23`.
- Base-image findings: readiness R1 and R2, re-confirmed for the final image.
- The Dockerfile uses mutable base-image tags (R4). The resolved digests are recorded.

The two historical documentation links from readiness finding R3 are fixed in this closure PR.

## Exit statement

> AIP v0.5.0 is `SHIPPED_VERIFIED`: the exact qualified release candidate was published, the
> tagged source and final GHCR artifact identify that candidate, the final artifact passed the v0.5
> golden path and security disposition, and every known unsupported, unresolved, deferred, or
> coverage-limited case remains explicit.
