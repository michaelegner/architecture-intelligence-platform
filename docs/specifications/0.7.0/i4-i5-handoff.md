# v0.7.0 I4 → I5 handoff

**Status: provisional. I4.3 is not complete until the pilot is rerun (see the [completion record](i4-completion-record.md)); I5 does not start before that.**

**Qualified candidate:** `c662f3c440733a7b75252ba2466fee14c1c88f4a` (I4.2: PASS, 13 of 13 CI checks, A/B byte-identical). See the [completion record](i4-completion-record.md) and [execution record](i4-execution-record.md).

## What I5 owns

Release candidate freeze, release-content re-freeze, publication and post-publication verification. I5 must rerun the mandatory qualification on **its own exact candidate**; the I4 result is not carried over to a later commit.

## What I5 must carry or fix before it freezes

- **Five tools.** These still describe four tools: `examples/release-golden-path/golden_path.py` (`TOOLS`), `examples/mcp-clients/cursor.md` and `vscode.md`, and `examples/runtime-demo/hero-demo.md`. Update them to the five-tool list and re-pin. (`docs/mcp.md` already says five.)
- **Scope statement.** The v0.7 notes must say the gateway configured-access model is qualified for APISIX only (the Tyk `MODEL_GAP` scope exclusion, [dossier](i4-tyk-dossier.md)).
- **Mapping dependence.** State that associations to Operations and Services need an operator mapping or an exact contract match; without one the answer is unresolved by design.
- **Package version.** The package version is still `0.6.3`.
- **Known limits.** F1 to F3 (cost grows with the whole selection, not the page) and #323.
- **Pilot.** The first session (`CONTINUE`, [pilot record](i4-pilot-record.md)) deviated from the method and is to be replaced by a rerun. It is not user research.

## Not done in I4

A Tyk adapter, F1, any `app/` or schema change.
