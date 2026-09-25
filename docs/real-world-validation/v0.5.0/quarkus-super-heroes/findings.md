# Findings: `quarkus-super-heroes` (v0.5.0, I5 Slice 5)

These are the findings at candidate `174a17c5d0f8be35291032c677585291c330cc0a`. The full §11 fields
and the proposed dispositions are in `../finding-ledger.md`.

| Id | Finding | Proposed disposition |
| --- | --- | --- |
| F1 | Lifecycle L2, L5 and L3 end in HTTP 500: a `CanonicalValidationError` escapes unhandled instead of producing an I1 result | FIX |
| F2 | The import report has no inventory status or diagnostics, so the Kubernetes rejection code and the frozen limitation list cannot be observed | FIX |
| F4 | An OBSERVED_ONLY `service:grpc-locations` entity with no relations | NO_CHANGE |
| F5 | A dossier input-authoring defect: the bindings layout broke the discoverer's documented convention (attempt 1 at `34067b7`; corrected in #246). A diagnostic for skipped files is deferred. | DEFER |
| F7 | The frozen lifecycle mutation for L2, L5 and L3 is invalid: X (`rest-fights/openapi.yml`) is the only minter of the Service the manifest's CALLS come from. It needs an I5 §6 correction, a re-freeze and a rerun. | NO_CHANGE (AIP) |

The qualifying comparison itself has no mismatch: 45/45 `CORRECT`, and 4/4 forbidden facts absent.
