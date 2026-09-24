// I5 §13 "public reads cause zero graph writes", frozen read-only query. It dumps every node and
// relationship with all of its properties, ordered by element id. Slice 5 takes the sha256 of this
// output before and after the public-surface reads on the same database (../public-surfaces.md),
// and the two digests must be equal. Element ids are stable only within one database, so the
// digest is compared within one run, never across runs.
MATCH (n) RETURN 'N' AS kind, elementId(n) AS id, n AS entity ORDER BY id
UNION ALL
MATCH ()-[r]->() RETURN 'R' AS kind, elementId(r) AS id, r AS entity ORDER BY id;
