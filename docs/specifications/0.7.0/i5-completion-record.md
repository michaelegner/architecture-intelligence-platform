# v0.7.0 I5 — Completion record

**Terminal outcome: `SHIPPED_VERIFIED`.** Governing: the
[I5 specification](i5-release-candidate-publication-and-verification.md).

| Item | Value |
|---|---|
| Candidate attempts | rc.1 `60e52a8` (#560, never qualified: closed #323 listed as a limitation), rc.2 `2cd42c0` (#561, fully qualified, superseded: README still said four tools), **rc.3 `fdbabcfa949836fbc654d01f2041bafb394bb74e`** (#563) |
| Preparation | [rc.3 record](../../release-validation/v0.7.0-rc.3-candidate-preparation.md) |
| Technical decision | `GO` — [readiness](../../release-validation/v0.7.0-release-readiness.md) |
| Publication decision | [authorized](../../release-validation/v0.7.0-publication-decision.md) for the release artifact and, separately, the MCP Registry |
| Tag, release, workflow, digest | `v0.7.0` → candidate; Docker run 38857729753; `sha256:ae59a4eeef75bdc4eae22f8029223139fd5af842c80603a4c6b79c1d7da2d4f3` |
| Verification | [post-release verification](../../release-validation/v0.7.0-post-release-verification.md): identity, anonymous digest pull, security and SBOM, tagged-source and published-image golden path, deterministic published APISIX replay, v0.6 preservation, registry |

## What the process caught

Two defects were found before qualification of the final candidate and fixed by a new candidate each time:
a limitation (#323) that no longer exists, in the release notes; and README tool-count and envelope
statements, which the first search terms missed. Both were release-facing content. The stale
"#323 remains open" narrative in earlier I4 records and the `V07` profile's `known_debt` text is
historical and superseded by the preparation record.

## Carried forward (not a v0.7 defect)

The configured-access model is qualified for APISIX only (Tyk `MODEL_GAP`, scoped out); associations need
a mapping or an exact match; F1 to F3 (cost grows with the whole selection); the Pitstop plugin and the
hosted demo are not part of this release; the hosted instance still runs an earlier version.
