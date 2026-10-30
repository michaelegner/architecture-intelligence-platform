#!/usr/bin/env bash
set -euo pipefail
cd "$VQ_RUN_HOME/src"
while read -r repo sha; do
  git clone -q "https://github.com/Sokol111/$repo" "$repo"
  git -C "$repo" checkout -q "$sha"
  head=$(git -C "$repo" rev-parse HEAD)
  [[ "$head" == "$sha" ]] && echo "$repo $head ok" || { echo "$repo $head MISMATCH (want $sha)"; exit 1; }
done < "$VQ_RUN_HOME/package/ops/freeze.txt"
