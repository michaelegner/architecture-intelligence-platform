# GT 0.8.0 I3 report

Increment 3 of the [GT 0.8.0 specification](../specification.md). This is a lightweight pre-v0.9 experiment, so every result below is exploratory. The details are in the owner-approved [scoring](scoring.md). The session records are in [`sessions/`](sessions/), and the harness is in [`harness/`](harness/README.md).

## Question

Can an agent use GT's views of independently modeled promises, and AIP's qualified evidence, to reach a better-supported consumer-onboarding decision than it reaches from the same sources alone?

## What ran

Four agent sessions on the frozen I1 corpus and task. Each ran once, on `claude-opus-5-5` with Claude Code 2.1.322.

| Arm | Materials | Result |
|---|---|---|
| A | files | conditional proceed; 155 s, $0.82 |
| AA | files + hosted AIP | conditional proceed; 126 s, $0.84; one binding-picture query |
| G | GT views over the same corpus | conditional proceed; 370 s, $1.57 |
| GA | GT views + AIP through the I2 client | conditional proceed; 257 s, $1.34; **AIP never queried** |

All four audits are clean.

## Findings

**Same decision in all four arms.** Every arm:
- recommended conditional proceed and withheld the 15-minute guarantee until Catalog and the marketplace commit to time bounds;
- stated all six contract facts correctly;
- made none of the nine invalid inferences in the key;
- composed the requirement from separately owned stage budgets instead of one party's promise.

**No decision-changing insight.** Every first impression was already conditional proceed with the right multi-party structure. The investigation made the conditions stricter in every arm, but changed no decision class.

**The arms differ in discovery, not in comprehension.** Several implementation facts that the key did not anticipate were found, and the scorer verified each against the corpus:
- the 10-hour outbox backoff cap (G, A, AA);
- Product Query reads cannot report a disabled product (A, AA);
- retries can publish a stale update after a delete (AA);
- the generated event catalog omits deletion (GA, A, AA).

No arm found all of them.

**E1, incremental AIP qualification: not shown.**
- **G vs GA:** not measurable. The GA agent opened the AIP client's views and saw a `binding picture` row, but never selected it, so no query ran. AIP was reachable through GT, but nothing told the agent that selecting the row runs a query.
- **A vs AA:** AIP's answer was correct and correctly qualified. AA quoted that an attachment does not establish event handling. But the other arms reached the same consumer facts from the broker capture and the mapping in the common corpus, so AIP added no decision-relevant fact in this run.

**E2, promise navigation through GT: feasible, but no added value here.**
- An agent can investigate the whole corpus through GT views alone. That includes contracts, source files, the broker capture and the mapping, all reached by navigation.
- G reached the same decision and the same contract comprehension as A. It took 2.4× the duration, 3.5× the turns and 1.9× the cost.
- GT's modeled Contracts view did not lead to any finding that the file arm missed.

## Limits

- **One run per arm.** Differences between arms can be run-to-run variance.
- **Agent operators only.** The I2 done-when, a human unfamiliar with Sokol111, was **not evaluated**.
- **GT as an agent interface.** The GT arms used four read-only navigation tools, not the GT user interface. Stock gt4llm returns views only as screenshots, so I3 added a text tool, `getViewText`. The result says nothing about how a human would use GT.
- **Asymmetric AIP access.** GA could reach only the I2 client's fixed scope; AA had all seven tools. The only valid attribution pairs are G vs GA and A vs AA.
- **Isolation by procedure.** A fresh agent configuration, `dontAsk` permissions and a post-session audit, plus the GT boundary: a server bound to one address with no code evaluation. This is deviation detection, not a sandbox.
- **A fictional, easy task.** The contracts state their limits plainly ("no latency guarantee", "does not authorize a new consumer"). That favors early, correct first impressions and leaves little room for a decision-changing insight.

## Maintenance effort

| Part | Size | Note |
|---|---|---|
| I2 GT packages | 508 lines of Smalltalk | views, page, AIP client |
| I3 GT MCP package | 391 lines of Smalltalk | bound server, `getViewText`, `selectViewItem`, Files view |
| I3 harness | 737 lines of Python | setup, run, drift check, audit |
| Owner sittings | 6 | I2 smoke, spike (×2), G, GA, firewall |

Everything here exists only for the experiment.
