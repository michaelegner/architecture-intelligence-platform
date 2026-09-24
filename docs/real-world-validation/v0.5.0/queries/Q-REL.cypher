// I5 §10 lifecycle, frozen read-only query: every owned relationship's identity with its sorted
// owners (PR #244 review). A relationship replaced with an equal count still changes this output.
MATCH (a)-[r]->(b) WHERE r.owner_source_ids IS NOT NULL
UNWIND r.owner_source_ids AS o
WITH a, r, b, o ORDER BY o
WITH type(r) AS type, a.id AS source, b.id AS target, r.key AS key, collect(o) AS owners
RETURN type, source, target, key, owners
ORDER BY type, source, target, key;
