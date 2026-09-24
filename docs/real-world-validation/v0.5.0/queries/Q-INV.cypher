// I5 §10 lifecycle, frozen read-only query: the committed inventory for the declarations scope.
MATCH (i:CurrentInventory)
RETURN i.discovery_scope_id, i.scope_definition_digest, i.inventory_revision
ORDER BY i.discovery_scope_id;
