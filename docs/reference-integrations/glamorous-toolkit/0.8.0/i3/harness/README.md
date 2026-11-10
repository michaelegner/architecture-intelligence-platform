# GT 0.8.0 I3 harness

The harness for **Increment 3** of the [GT 0.8.0 specification](../../specification.md): four agent sessions on the frozen I1 corpus, one per arm. The digests are in [`SHA256SUMS`](SHA256SUMS).

| Arm | Materials | Claude tools | MCP |
|---|---|---|---|
| A | the corpus as files | Read, Glob, Grep, Write | none |
| AA | the corpus as files | Read, Glob, Grep, Write | hosted AIP, all seven tools |
| G | GT with the common package and the I3 package | Write; Read of its own outputs | the GT server, four tools |
| GA | GT with both I2 packages and the I3 packages | Write; Read of its own outputs | the GT server, four tools; AIP only through the I2 client |

All arms run `claude -p` with model `claude-opus-5-5` from WSL. Each session has a fresh config directory and home, `--strict-mcp-config`, `--permission-mode dontAsk` and no Bash. The agent can write only `first-impression.md` and `answer.md`. In every arm, only the task read may come before the first impression. The first message differs between file arms and GT arms only in where the task is: [`prompts/files.md`](prompts/files.md) and [`prompts/gt.md`](prompts/gt.md).

## Files

| File | Purpose |
|---|---|
| [`AIP-GT-Promises-MCP.st`](AIP-GT-Promises-MCP.st) | GT server bound to one address with four read-only tools. `getViewText` returns a view as text and replaces the stock `getViewContent`, which returns a view only as a 1600×1200 screenshot and cuts off long content. `selectViewItem` navigates. The corpus gets a Files view confined to the corpus root |
| [`AIP-GT-Promises-MCP-AIP.st`](AIP-GT-Promises-MCP-AIP.st) | GA only: navigation from the I2 client to the binding picture and its rows |
| [`session.py`](session.py) | `setup ARM` builds the session; `run ARM` checks the preconditions, runs the agent once and writes `record/session.json` |
| [`check_hosted.py`](check_hosted.py) | Drift check before GA and AA: the frozen I1 query still gives the frozen snapshot and answer digest |
| [`audit.py`](audit.py) | Deviation detection after each session; writes `record/audit.json` |
| [`gt_client.py`](gt_client.py) | Minimal GT MCP client for the GT preflight |
| [`prompts/`](prompts/) | First messages; `probe-*.md` are the dry-run capability checks |

## Run order

G, GA, then A, then AA. For each arm:

1. `python3 session.py setup ARM`. For G and GA, this also prepares a fresh GT extraction, the `--gt` corpus and the arm's `.st` files under `C:\Users\megne\aip-gt-i3\sessions\ARM-N\`.
2. G and GA only: the owner starts GT, loads the packages, creates the page and starts the server. For G, the owner also checks that `GtAipHostedClient` is absent.
3. Dry run, required for G and GA: `python3 session.py run ARM --probe`, then `python3 audit.py ARM-N probe-1`. It checks the offered tools and that reads and writes outside the session are refused. A dry run keeps its own record and leaves the output directory empty. If it fails, fix the harness and re-freeze before the real run.
4. `python3 session.py run ARM`. For G and GA, the owner then stops the server; for GA, the owner first exports `GtAipHostedClient session exportLogTo:` to `aip-log.json` in the session's Windows directory. Then `python3 audit.py ARM-N`.
5. A void session is re-run once with `--attempt 2`. Both attempts are kept.

Session directories live under `~/aip-gt-i3-runs/`, outside every repository.

## Differences from the approved plan

- `session.py` replaces the planned `setup_session.sh` and `run_session.sh`.
- `getViewText` replaces GT's `getViewContent` (spike result, owner decision 2026-11-10).
- A and AA have no Bash. Deny rules cannot keep Bash off the network, and the GT arms have no shell (owner decision 2026-11-10).
- Claude Code updated itself from 2.1.321 to 2.1.322 before the sessions. `session.py` calls the 2.1.322 build by path, checks its version and runs it with `DISABLE_AUTOUPDATER=1`.
- `contracts.json` appears in the GT corpus root only. It renders the four frozen YAML contracts (`materialize_corpus.py --check`) and adds no content.
