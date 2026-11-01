#!/usr/bin/env bash
# Blind bindingPicture run (README §2-§4): one claude -p session.   run.sh P-|P+
set -euo pipefail
ARM="${1:?P- or P+}"; case "$ARM" in P-|P+) ;; *) echo "bad arm" >&2; exit 2 ;; esac
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RH="$HOME/toolseed-blind"; SD="$RH/sessions/$ARM"; WS="$SD/workspace"; CFG="$SD/claude"
CLAUDE="$HOME/.local/bin/claude"; NODE_BIN="$(dirname "$(command -v node)")"
[[ -d "$RH/src" ]] || { echo "no clones" >&2; exit 2; }
[[ ! -e "$SD" ]] || { echo "$SD exists" >&2; exit 2; }
mkdir -p "$WS" "$CFG"
cp -a "$RH/src" "$WS/src"
install -m 600 "$HOME/.claude/.credentials.json" "$CFG/.credentials.json"
[[ "$ARM" == P+ ]] && printf '%s\n' '{"mcpServers":{"aip":{"type":"http","url":"https://mcp.daip.io/mcp"}}}' >"$WS/.mcp.json"

python3 - "$ARM" "$HOME" "$WS" "$RH/sessions" "$(id -u)" >"$CFG/settings.json" <<'EOF'
import json, sys
arm, home, ws, sessions, uid = sys.argv[1:]
allow = ["Read", "Glob", "Grep", f"Edit(/{ws}/**)", f"Write(/{ws}/**)"] + [f"Bash({c}:*)" for c in (
    "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq", "diff", "mkdir", "node",
    "git log", "git show", "git status", "git rev-parse", "git -C")]
deny = [f"Read(/{home}/code/**)", f"Read(/{home}/.claude/**)", f"Read(/{home}/.claude.json)",
        f"Read(//tmp/claude-{uid}/**)", f"Read(/{sessions}/{'P-' if arm == 'P+' else 'P+'}/**)",
        "WebFetch", "WebSearch", "Artifact", "Bash(curl:*)", "Bash(wget:*)", "Bash(gh:*)"]
if arm == "P+":
    allow.append("mcp__aip")
else:
    deny.append("mcp__aip")
print(json.dumps({"permissions": {"defaultMode": "dontAsk", "allow": allow, "deny": deny},
                  "enableAllProjectMcpServers": arm == "P+", "autoMemoryEnabled": False}, indent=2))
EOF

{ cat "$HERE/../prompt.md"; printf '\n'; sed -n '/^SUPPLIED QUESTION AND BOUNDARY/,/^```/p' "$HERE/README.md" | sed '$d'; } >"$SD/input.txt"
date -u +%FT%TZ >"$SD/started.txt"
(cd "$WS" && env -i "HOME=$HOME" "PATH=$NODE_BIN:/usr/local/bin:/usr/bin:/bin" \
  CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 ENABLE_CLAUDEAI_MCP_SERVERS=false "CLAUDE_CONFIG_DIR=$CFG" \
  "$CLAUDE" -p "$(cat "$SD/input.txt")" --model claude-opus-5-5 --output-format stream-json --verbose) \
  >"$SD/stream.jsonl" 2>"$SD/stream.err" || true
date -u +%FT%TZ >"$SD/ended.txt"
mkdir -p "$SD/transcripts" && cp -a "$CFG/projects/." "$SD/transcripts/" 2>/dev/null || true
echo "$ARM done: $(tail -c 300 "$SD/stream.jsonl")"
