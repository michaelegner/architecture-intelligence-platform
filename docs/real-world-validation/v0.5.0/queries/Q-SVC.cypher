// I5 §10 lifecycle, frozen read-only query: the ids of every owned node, with its sorted owners.
MATCH (n) WHERE n.owner_source_ids IS NOT NULL AND n.id IS NOT NULL
WITH n, [o IN n.owner_source_ids | o] AS owners
UNWIND owners AS o
WITH n, o ORDER BY o
RETURN n.id, collect(o) AS owners
ORDER BY n.id;
