# Findings: `apache-airflow` (v0.5.0, I5 Slice 5)

These are the findings at candidate `174a17c5d0f8be35291032c677585291c330cc0a`. The full §11 fields
and the proposed dispositions are in `../finding-ledger.md`.

| Id | Finding | Proposed disposition |
| --- | --- | --- |
| F2 | The import report has no diagnostics, so the source's limitation code cannot be observed | FIX |
| F3 | The OpenAPI source is `ACCEPTED_WITH_LIMITATIONS` (`SCHEMA_COMPOSITION_UNINTERPRETED`), which the dossier did not anticipate | DOCUMENT_UNSUPPORTED |
| F6 | The lifecycle `without_x.py` header-only diff on L2 and L3 (a harness artifact; the row sets are equal) | NO_CHANGE (AIP) |

The qualifying comparison itself has no mismatch: 9/9 `CORRECT`, 2/2 forbidden facts absent, and
the classifications are as frozen.
