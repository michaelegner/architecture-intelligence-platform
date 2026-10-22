# v0.7.2 I3 — Comparison record: Unblocked only vs. Unblocked + AIP

Governing: [spec §5](specification.md), kit and rubric in [`i3-evidence/`](i3-evidence/README.md). The ground truth in [`scoring.md`](i3-evidence/scoring.md) was committed (`de51afd`) before either run. This is **one run of each arm**, so it is an observation, not a measurement.

## Result

**No additional value from AIP in this run, because the agent never made a valid `get_destination_consumers` query.** All 14 `get_destination_consumers` calls of the AIP arm were refused (`UNKNOWN_DESTINATION` or `BROKER_MISMATCH`), although the hosted instance serves the right answer (a [post-run check](#setup) at 11:59:59Z returned both consumers). The agent did not reach the AIP query context even though AIP's own answers contained the ids; the identifier forms and refusal messages misled it (Finding 2). That is the finding for the owner checkpoint (spec §5.4, last paragraph). Both arms found the correct consumer set from source, configuration and the stock `rpk` files, so AIP changed nothing the engineers would have done. No new tool is proposed here.

## Setup

| Item | Value |
|---|---|
| Runs | **Run 2** (2026-10-22T11:36:45Z–11:58:39Z) is the record. **Run 1** (07:37Z) is invalid: both arms hit the Claude session limit mid-implementation, and eval and attribution failed. Its `result.json` is kept in [`results/run1-invalid/`](i3-evidence/results/run1-invalid/) and is not used |
| Harness | `context-engine-simulator@837eb0a` with [`simulator.patch`](i3-evidence/simulator.patch) (sha256 `02c2c909…`); fixture, settings and arm configs as committed |
| Agent | Claude Code 2.1.308, `claude-opus-5-5`, effort high, same in every step of both arms |
| Repository | Synthetic repo `3d6a311a90a4eb4adf4d3f152ecc7cd74c88744f`: the 8 frozen Sokol111 repos plus the C1-time stock `rpk` output |
| Unblocked | Indexed forks of the same 8 repos at the freeze commits, in a GitHub organization. Tools exposed: `context_research`, `context_get_urls`, `context_get_rules` |
| AIP | https://mcp.daip.io/mcp, six tools, frozen Sokol111 C1 (snapshot `a08b1bad…`). Post-run `verify_public_edge.py --profile sokol111 --expect-429-within 121`: all PASS, incl. 429 after 114 requests |
| Equivalent workflow | Both arms ran the same six-step chain; every invocation's `system/init` was checked (12 of 12 recorded in `result.json`). `--check-arms` passed, and the swapped negative failed both arms, before the run |
| Hosted edge limits | 120 requests/min per client, 600/min global (unchanged) |

Outputs: [`results/run2/`](i3-evidence/results/run2/) (`result.json`, `report.html`, `simulator.log`, `transcripts.tar.gz`).

## Scoring against `scoring.md`

| # | Unblocked only (A) | Unblocked + AIP (B) |
|---|---|---|
| R1 consumers | Both found: product-query and image-service, with code, config and local `rpk` lines; category-query and catalog ruled out; tenant-service marked "medium, repo not checked out". No false consumer | Both found, from the same kinds of source. No false consumer. B notes that one Unblocked answer listed only product-query and missed image-service (Unblocked's output varied between runs) |
| R2 unsupported claims | None found | None found |
| R3 Current State vs. history | Good: labels the `rpk` evidence "Runtime (local only)", says that environment is no longer running, and asserts nothing for production | Good: "the only capture is local (2026-10-21) and that environment has been torn down" |
| R4 unresolved | Production consumers, group-less readers (Redpanda Console), the missing `rpk` files 09–10, prod topic settings, unreviewed api 1.3.7/1.3.8 | Same list, plus "AIP gives no answer" with its refusal codes |
| R5 provenance used | Unblocked `context_research` (10 calls); source files; `rpk` files | Unblocked (12 calls); 34 AIP calls (14 `get_destination_consumers`, 12 `get_service_dependencies`, 6 `get_architecture_drift`, 2 `get_evidence`); source files; `rpk` files. No evidence ref from AIP was resolved into a consumer |
| R6 concrete change | — | **None.** AIP did not change the consumer set, the rollout order or any gate |
| R7 navigation | n/a | **Failed.** The agent guessed `redpanda`/`production`, then `topic:owned:5534…` with `broker:owned:69a6…` (`BROKER_MISMATCH`), then `kafka:sokol111-local` with the raw topic name `catalog.product.events` (`UNKNOWN_DESTINATION`). It never combined the owned Topic id with `kafka:sokol111-local`. Later it tried `kafka:sokol111-prod`/`prod`, a context that does not exist |
| R8 contamination | **Fails one check:** a `git branch` listed arm B's branch name (`ces-context-…`), which the kit's own after-run check forbids. Impact judged negligible: it was a name only, arm A read nothing from that branch, and the name carries no AIP content. The cause, shared worktree refs, is fixed for run 3 | Pass |

R8 detail, for both arms: the Unblocked token appears in no output; neither the AIP repository nor the answer key (`michaelegner/architecture-intelligence-platform`, `i2-evidence`) appears; `context_get_urls` was never called; `gh`/`curl`/`wget` were attempted 3 times in A and 4 times in B, and every attempt was denied; no 429s or edge errors occurred; the plugins and auto-memory were off in every invocation.

## Findings

1. **Source plus Unblocked was already strong.** The correct consumer set, its evidence and its uncertainty came from Unblocked, the code and the stock `rpk` files alone. This repeats the Round 4 baseline (`round4-sokol111-baseline.md`).
2. **The obstacle was navigation, not data, and the ids were discoverable.** One `get_service_dependencies` answer for the catalog service already gave the agent `topic:owned:5534…` (the Topic's **id**, named `catalog.product.events`) and a broker with id `broker:owned:69a6…` and **name** `kafka:sokol111-local`. The query needs the Topic's id together with the broker's name; the answers label both as "id". The agent tried each half correctly once, never both in one call:
   - calls 7–10: correct Topic id, broker **id** → `BROKER_MISMATCH`;
   - calls 11–12: Topic **name**, correct broker name → `UNKNOWN_DESTINATION`.

   The refusal text did not help: `BROKER_MISMATCH` ("not declared on the requested broker") reads as a wrong pairing, and `UNKNOWN_DESTINATION` ("no declared Topic has this destination id") does not say that the Topic's owned id is needed. After call 12 the agent stopped trying valid Topic and broker combinations, then guessed a non-existent `kafka:sokol111-prod`, and reported "AIP gives no answer". It kept honest uncertainty instead of inventing an answer. That was good behavior, but it added no AIP value. This is an existing-contract clarity finding (identifier forms in the tool description and the two refusal messages), recorded for the owner checkpoint. It is not a case for a discovery tool, and none is proposed.
3. **No confusion of history with Current State** in either arm. Both kept the single local capture dated and marked its environment as gone.
4. **What this does not show.** It does not show that AIP adds nothing once the right context is known. A run with the context card (Topic id, broker id, environment), as in the v0.7.1 session kit, would test AIP's value separately from discovery. It is one run per arm, one model, one task.
5. **Simulator limits.** Both agents committed their work, so the simulator's diff stat (0 files) and its evaluator score (10/100 in both arms) are meaningless and are not used. The agents' actual commits are saved as [`arm-a-commits.patch`](i3-evidence/results/run2/arm-a-commits.patch) and [`arm-b-commits.patch`](i3-evidence/results/run2/arm-b-commits.patch). The patch's `--check-arms` and init recording worked as designed. Run 2 used patch sha256 `02c2c909…`; the current [`simulator.patch`](i3-evidence/simulator.patch) adds only the per-arm clones (R8).

## Follow-up in this PR

Run 2 measured the **unfixed** wording. This PR changes only text: the `get_destination_consumers` tool description and the `UNKNOWN_DESTINATION` / `BROKER_MISMATCH` refusal messages now say that `destination_id` is the canonical Topic id (never a name) and `broker_id` is the stable broker id (the `BrokerRef` `name`, not its canonical `broker:owned:` id). Refusal codes, `data: null`, the request and answer schemas, and the tool inventory are unchanged.

- **Run 3 (pending the usage-limit reset and the owner's GO), in two stages.** Both use the same task and no context card. The arm config variant for each stage is committed before that stage runs. Run 2 stays the record of the shipped v0.7.1 wording.
  1. **Probe, local:** arm B's initial-context step only (about $3), against a local AIP built from this branch on the frozen C1 package. It passes if a `get_destination_consumers` call returns the two RESOLVED consumers instead of a refusal. A local server is enough for this yes/no question.
  2. **Full run, hosted, only if the probe passes:** both arms, with arm B on `https://mcp.daip.io/mcp` serving a candidate image of this branch. This keeps the same server, edge and frozen data as run 2, so only the wording changes; whether the snapshot id is also unchanged is checked and recorded. The image is loaded onto the VPS directly (`docker save | docker load`), never published, and set in `.env` as in I1. The record notes the temporary candidate, and the v0.7.2 release replaces it with the published digest and re-verifies (spec §6.2).

  If the probe fails, the wording is not enough on its own, and the next step is the schema-description idea below.

**Probe result (2026-10-22, run 3 stage 1): PASS.** Kit commit `ebfe2ed`, pushed before the probe ran; local AIP from this branch on the frozen C1 package, snapshot `aip:snapshot:v1:6d41bcf3…` (location-bound, so it differs from the hosted `a08b1bad…`); $2.69, 42 turns. Outputs are in [`results/run3-probe/`](i3-evidence/results/run3-probe/), with no token, no answer-key content, no `gh`/`curl`/`wget` and no `context_get_urls`.
- **R7 navigation:** the agent's **first** `get_destination_consumers` call was valid (`topic:owned:5534…`, `kafka:sokol111-local`, `local`). It answered `PARTIAL` with both consumers `RESOLVED` and `CAPTURE_SCOPE_LIMITED`; a second valid-form call for `production` got the correct `NO_ACCEPTED_CAPTURE`. In run 2, all 14 calls were refused.
- **R3:** the context bundle reports both consumers from "the 2026-10-21T17:53:57Z capture", keeps `CAPTURE_SCOPE_LIMITED`, notes that AIP's answer derives from the same capture as the stock `rpk` files, and records production as **not observed** (`NO_ACCEPTED_CAPTURE`), not as "no consumers".
- **What AIP added here:** a qualified Service attribution with its capture time, and a typed statement that production is unobserved. It did not change the consumer set, which source and the `rpk` files already gave. Whether that changes the plan or the rollout gate is what the full run (stage 2) measures.
- **v0.7.3 candidate:** field `description`s for `destination_id` and `broker_id` in the request schema, where agents read them in `inputSchema`. That regenerates the frozen 0.7.1 request schema and needs a deliberate spec edit, so it is not part of this PR.

## Effort and cost

- **Setup:** planning started 05:47Z and the first run started 07:37Z, about 1h50m. That includes the harness patch, the synthetic repo, the owner's Unblocked organization and token steps, and the isolation probes (plugins and auto-memory leaked until explicitly disabled).
- **Run 2:** arm A 17m50s, $9.23; arm B 21m52s, $10.27 (3 minutes longer, 11% more cost). Run 1 added about $18 that produced nothing usable.
- **Upkeep:** every new Sokol111 capture needs an AIP mapping review and an import, about 40 minutes once the environment exists (I2 record).

## For the owner checkpoint (I4)

The record supports **NARROW or DEFER** over CONTINUE as it stands: AIP's data is correct and hosted, but a coding agent given ordinary task vocabulary did not reach it, and when it did not, nothing changed. The decision is yours. The navigation finding is recorded and no seventh or discovery tool is proposed or pre-authorized.

## Known limits

- The org name `architecture-intelligence-platform` is visible to both arms and held constant (disclosed in the kit README).
- Forks carry no upstream pull requests or issues.
- Dependabot's certifi advisory GHSA-6q48-6c7w-9gw2 (`harness/locality-capture`) stays open until after the release, as decided.
