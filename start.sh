#!/usr/bin/env bash
# Start the wiki-os web UI (serving ./wiki) alongside the NM-Agent-CLI agent.
#
#   ./start.sh              # wiki-os in background + agent in foreground
#   ./start.sh wiki         # only start/refresh the wiki-os server, then exit
#
# The wiki-os server keeps running after the agent exits; stop it with:
#   pkill -f "dist-server/server/server.js"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WIKI_OS_DIR="$ROOT/wiki-os"
WIKI_ROOT="${WIKI_ROOT:-$ROOT/wiki}"
WIKI_OS_PORT="${WIKI_OS_PORT:-5211}"
export WIKI_OS_URL="http://localhost:$WIKI_OS_PORT"

wiki_up() { curl -s -o /dev/null --max-time 2 "$WIKI_OS_URL"; }

start_wiki_os() {
  if wiki_up; then
    echo "wiki-os already running at $WIKI_OS_URL"
    return 0
  fi

  if [ ! -d "$WIKI_OS_DIR" ]; then
    echo "wiki-os not found at $WIKI_OS_DIR — starting agent without the wiki UI" >&2
    return 0
  fi

  echo "Starting wiki-os at $WIKI_OS_URL (vault: $WIKI_ROOT) …"
  (
    cd "$WIKI_OS_DIR"
    WIKI_ROOT="$WIKI_ROOT" PORT="$WIKI_OS_PORT" nohup npm start >>"$WIKI_OS_DIR/wiki-os.log" 2>&1 &
  )

  for _ in $(seq 1 60); do
    if wiki_up; then
      break
    fi
    sleep 1
  done

  if wiki_up; then
    echo "wiki-os ready: $WIKI_OS_URL"
  else
    echo "warning: wiki-os did not come up — see $WIKI_OS_DIR/wiki-os.log" >&2
  fi
}

start_wiki_os

if [ "${1:-}" = "wiki" ]; then
  echo "wiki-os left running in the background (log: $WIKI_OS_DIR/wiki-os.log)"
  exit 0
fi

echo "stop the wiki-os later with: pkill -f 'dist-server/server/server.js'"
cd "$ROOT"
exec uv run python main.py
