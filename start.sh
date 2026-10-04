#!/usr/bin/env bash
# Start the NM-Agent-CLI agent. The wiki (React "Wiki" tab) is served by the
# in-process Python engine inside server.py (wiki_engine/) — no separate
# service to boot. The web UI itself:
#   uv run python server.py        # FastAPI on :8000 (agent + /wapi wiki engine)
#   cd frontend && npm run dev     # Vite dev server on :5173
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WIKI_ROOT="${WIKI_ROOT:-$ROOT/wiki}"

if [ "${1:-}" = "wiki" ]; then
  echo "The wiki engine is in-process now (wiki_engine/ inside server.py) — nothing to boot."
  echo "Web UI: uv run python server.py  +  cd frontend && npm run dev"
  exit 0
fi

cd "$ROOT"
exec uv run python main.py
