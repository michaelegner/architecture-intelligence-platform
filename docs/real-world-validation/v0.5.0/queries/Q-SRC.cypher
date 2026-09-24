// I5 §10 lifecycle, frozen read-only query: every committed source state with its scope digest.
MATCH (s:SourceState)
RETURN s.source_instance_id, s.discovery_scope_id, s.scope_definition_digest, s.semantic_input_digest
ORDER BY s.source_instance_id;
