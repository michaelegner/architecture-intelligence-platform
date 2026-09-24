// I5 §10 lifecycle, frozen read-only query: how many nodes and relations each source owns.
CALL {
  MATCH (n) WHERE n.owner_source_ids IS NOT NULL
  UNWIND n.owner_source_ids AS owner RETURN owner, 'node' AS kind
  UNION ALL
  MATCH ()-[r]->() WHERE r.owner_source_ids IS NOT NULL
  UNWIND r.owner_source_ids AS owner RETURN owner, 'relation' AS kind
}
RETURN owner, kind, count(*) AS owned
ORDER BY owner, kind;
