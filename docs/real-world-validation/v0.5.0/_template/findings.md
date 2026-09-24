# Findings — `<system-id>`

One entry per material finding from the qualifying comparison (I1 §20). For any finding that may
change AIP semantics, add a full model-hardening decision record using
[`decision-record.md`](decision-record.md) instead of the short form below.

## `<finding-id>`

```text
classification:  CORRECT | MISSING_SUPPORTED | INCORRECT_SUPPORTED | UNSUPPORTED
                  | UNRESOLVED_IDENTITY | INSUFFICIENT_EVIDENCE
severity:         CRITICAL | MAJOR | MINOR | INFO
expected:         <fact, or none>
actual:           <fact, or none>
disposition:      FIX | DOCUMENT_UNSUPPORTED | DEFER | NO_CHANGE
```

<!-- Repeat one block per material finding. Every finding needs an explicit disposition before the
     iteration exits (I1 §25-26). -->
