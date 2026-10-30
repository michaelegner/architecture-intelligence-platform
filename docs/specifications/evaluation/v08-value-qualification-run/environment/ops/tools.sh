#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$VQ_RUN_HOME/package/ops/dl"; cd "$VQ_RUN_HOME/package/ops/dl"
curl -fsSLO https://github.com/k3d-io/k3d/releases/download/v5.9.0/k3d-linux-amd64
curl -fsSL https://github.com/k3d-io/k3d/releases/download/v5.9.0/checksums.txt -o k3d-checksums.txt
grep ' _dist/k3d-linux-amd64$' k3d-checksums.txt | sed 's#_dist/##' | sha256sum -c -
curl -fsSLO https://github.com/tilt-dev/tilt/releases/download/v0.37.8/tilt.0.37.8.linux.x86_64.tar.gz
curl -fsSL https://github.com/tilt-dev/tilt/releases/download/v0.37.8/checksums.txt -o tilt-checksums.txt
grep ' tilt.0.37.8.linux.x86_64.tar.gz$' tilt-checksums.txt | sha256sum -c -
curl -fsSLO https://get.helm.sh/helm-v3.22.0-linux-amd64.tar.gz
curl -fsSLO https://get.helm.sh/helm-v3.22.0-linux-amd64.tar.gz.sha256sum
sha256sum -c helm-v3.22.0-linux-amd64.tar.gz.sha256sum
install -m 755 k3d-linux-amd64 "$VQ_RUN_HOME/bin/k3d"
tar -xzf tilt.0.37.8.linux.x86_64.tar.gz -C "$VQ_RUN_HOME/bin" tilt
tar -xzf helm-v3.22.0-linux-amd64.tar.gz --strip-components=1 -C "$VQ_RUN_HOME/bin" linux-amd64/helm
