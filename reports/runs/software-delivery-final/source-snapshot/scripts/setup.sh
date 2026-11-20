#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .runtime runtime
if [[ ! -x .runtime/node/bin/node ]] && ! node -e 'process.exit(Number(process.versions.node.split(".")[0])>=22?0:1)' 2>/dev/null; then
  curl -fsSL https://nodejs.org/dist/v22.22.0/node-v22.22.0-linux-x64.tar.xz -o /tmp/suhail-node.tar.xz
  tar -xJf /tmp/suhail-node.tar.xz -C .runtime
  mv .runtime/node-v22.22.0-linux-x64 .runtime/node
fi
export PATH="$PWD/.runtime/node/bin:$PATH"
[[ -d .venv ]] || python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python scripts/runtime_config.py
npm --prefix apps/web ci --no-audit --no-fund
.venv/bin/python -m playwright install chromium
echo 'Setup complete. Run make build and make up.'
