# v0.7.0 I4 — Completion record

**Status: I4 complete for v0.7.0.** Governing: the [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) revision 0.2, §14. Qualified candidate: `c662f3c440733a7b75252ba2466fee14c1c88f4a`. A first pilot session did not follow the frozen method and was replaced by a rerun that did (see the pilot row). This record claims no release readiness and no production capacity.

## Definition of Done (§14)

| Requirement | Result and evidence |
|---|---|
| All 57 frozen I3 cases pass unchanged on the candidate | Yes. The I3 oracle is unchanged; both runs matched it on every record ([execution record](i4-execution-record.md)) |
| All twelve parent §22 rows mapped | Yes ([register](i4-coverage-register.md)). Row 6 (ambiguous consumer) is qualified by the [Tyk dossier](i4-tyk-dossier.md); row 7 (ambiguous Route to Operation) by `B07` (`B07a` and `B07b` as expected-negative, `B07c` correct) |
| Two fresh runs semantically identical | Yes: separate processes, fresh Neo4j each, 215 records and 80 cases each, A/B raw canonical bytes identical, no normalization |
| APISIX real-source replay passes | Yes: 8 positive and 8 abstaining replay cases (positive, negative or insufficient, revision and evidence cases) |
| Service, REST and MCP equivalent | Yes: zero byte differences; the independent client's query, evidence and reconnect agree |
| Tyk represented without semantic collapse | `MODEL_GAP` with a reviewed v0.7 scope exclusion (below) |
| v0.5/v0.6 regressions pass | Yes: unit 4,668 passed; integration 837 passed and 1 skipped (a private-fork smoke test, not a qualification case); the register anchors ran in both workers |
| Security, read-only and credential boundaries intact | Yes: no replay fake credential appears in the evidence bundle; the credential canary case passed |
| Cost and known limitations recorded | Yes: [cost artifact](../../release-validation/v0.7.0-i4.2/api-usage-cost.json) and the replay measurements ([execution record](i4-execution-record.md)); F1 to F3 and #323 carried |
| Product-value pilot ends in a disposition | `CONTINUE` ([pilot record](i4-pilot-record.md)), from the rerun: the agent used only the AIP tools and the refreshed R2 window was queried through them. It is one session, not user research |
| Every mandatory result bound to one exact SHA, no unexplained skip | Yes: `c662f3c`, 13 of 13 required CI checks green on that SHA; no mandatory case skipped |
| Completion record and I4 → I5 handoff reviewed | This record and the [handoff](i4-i5-handoff.md), for owner review in the PR |

## Findings the owner should keep in view

- **Tyk `MODEL_GAP`.** The canonical configured-access carrier is typed to the APISIX Route allow-list, so Tyk's key-held, API-definition and version-scoped rights cannot be preserved without a reviewed source-neutral amendment. The scope exclusion (accepted at review): v0.7 admits one source and no second adapter, and nothing in v0.7 depends on a Tyk fact. The v0.7 content must say the configured-access model is qualified for APISIX only.
- **Mapping dependence.** In the replay world every Route to Operation and Route to Service association is unresolved until an operator supplies a mapping (5 of 5 in both revisions). That is the frozen behavior, not a defect.
- **Pilot limits.** One session; its answers matched the specified behavior and the agent stayed inside the evidence apart from two hedged remarks. A first session the same day deviated from the method and was replaced. The mapping choice is an operator judgement with no tool support, and the other four Routes stayed unlinked.
- **Carried debt.** F1 (the projection builds the whole selection before paging), F2 (every request reads the whole canonical state), F3 (the evidence ref map is rebuilt per call), and #323.

## Post-candidate commits

After the candidate: I4.2a (#554) is the candidate itself; I4.2c (#555), I4.3a (#556), I4.3b (#557) and this PR are documentation, evidence and the pilot kit. None changes `app/`, a schema, an oracle, an expectation or the qualification code in the frozen sense. I4.3b added documentation and a config template only. They are not claimed to be separately A/B-qualified.
