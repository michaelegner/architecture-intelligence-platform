# AIP v0.6.0 I4 — Decision Record

**Status:** I4.1. Decisions D1–D4 are frozen with the I4.1 PR. They record how the specification's method is realized; they change no architecture semantics.
**Governing:** [I4 specification](i4-deterministic-semantic-qualification.md) revision 0.2.

## D1 — Register keys

Parent §20 is an unnumbered table of 25 rows. The register keys them `S20-01`…`S20-25` in table order, and groups them into the seven groups of I4 §3. Adapter and method gates that are not §20 rows carry `G-NN` keys. Keys are owner-assigned and have no meaning outside the register.

## D2 — Bridge vector representation

The I4-P3 bridge vector is an oracle JSON produced by a stdlib-only author script, `i4-vectors/author_i4_expected.py`, in the style of the I3 oracle. A unit test reproduces it byte for byte. Worlds are synthetic generated envelopes, disclosed as such; the I2.6a rehearsal fixture is not copied or edited. `B01a` keeps the Workload UID across C1 and C2; `B01b` gives the same-named Deployment a new UID. P1 and P3 call **different** Operations so that any transfer is visible. Gap cases `B02`–`B06` state an I3 world plus a delta and frozen expected/forbidden facts; the runner builds them in I4.2.

## D3 — Comparator scope in I4.1

I4.1 freezes the ledger schema and comparator design (`i4-ledger-and-comparator-design.md`) only. The runner, comparator and benchmark changes land in I4.2 and I4.3. Nothing in I4.1 evaluates AIP.

## D4 — Frozen expectations

After I4.1 merges, `i4-vectors/expected-i4.json` and the register's expected/forbidden facts change only through a reviewed specification amendment, never to accommodate code (I4 §3 coverage rule, §7).
