# CLAUDE.md — langgraph-demo

LangGraph agent (financial research assistant: EDGAR, market data, web search). Two parallel implementations live in this repo:

- `main.py` — original agent using **OpenViking** server as its memory layer (do not modify while `memory-layer` branch is active)
- `alt-main.py` — the **Hermes-style memory** implementation, on branch `memory-layer`

## Memory layer (branch `memory-layer`)

The Hermes-style memory system (learning loop, agent-curated memory, session search, multi-level memory) lives in a **separate repo**: `~/projects/nm-memory-layer` (package `nm_memory_layer`), installed here as an **editable path dependency** via `[tool.uv.sources]` in `pyproject.toml`. Edit memory-layer code there, not here — changes apply immediately without reinstalling.

Current phase: **Phase 1 — SQLite + FTS5 episodic session store** (OpenViking recorder/session archives removed from `alt-main.py`).

### How alt-main.py persists sessions

- `SessionStore` from `nm_memory_layer` writes every completed turn to `./sessions.db` (WAL mode; override with `SESSION_DB_PATH`).
- Resume with `--session-id <id>`; history is rebuilt from the local store including tool-call pairs.
- The agent gets a `session_search` tool for deliberate retrieval of past-session context (replaces OpenViking's per-turn context assembly).
- `tools.py` is shared with `main.py`, so OpenViking tool bindings are still created at import; `alt-main.py` filters them out (`viking_` prefix) when binding tools.

### Remaining OpenViking usage in alt-main.py

None, other than the shared `tools.py` import (filtered). `.env` still carries `OPENVIKING_*` vars for `main.py`.

## Commands

```bash
uv run python alt-main.py                 # run agent with local memory (new session)
uv run python alt-main.py --session-id …  # resume a stored session
uv run python main.py                     # original OpenViking agent
uv sync                                   # install deps (incl. editable nm-memory-layer)
```

## Roadmap

Phases 2–5 (prompt memory, periodic nudge, skills layer, compression) are implemented in `nm-memory-layer` and wired here; see that repo's CLAUDE.md.
