// I5 §10 lifecycle, frozen read-only query: each committed source's semantic input digest.
// It binds the common mapping context (I1 §5.3). A change to the identity-bindings document may
// therefore legitimately change it for every remaining source (PR #244 review), so the ledger
// asserts it only where it is normative.
MATCH (s:SourceState)
RETURN s.source_instance_id, s.semantic_input_digest
ORDER BY s.source_instance_id;
