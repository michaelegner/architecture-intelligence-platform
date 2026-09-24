// I5 §10 lifecycle, frozen read-only query: every committed source's identity and scope binding.
// This is the normative part of SourceState (I1 §6). The semantic input digest is Q-SRC-SEM.
MATCH (s:SourceState)
RETURN s.source_instance_id, s.discovery_scope_id, s.scope_definition_digest
ORDER BY s.source_instance_id;
