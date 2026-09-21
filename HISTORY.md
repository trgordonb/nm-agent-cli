# HISTORY.md — langgraph-demo

Track of significant changes per branch. Dates are implementation dates.

## 2026-09-21 — branch `memory-layer` — Phase 1: local SQLite/FTS5 session store

Goal: replace the OpenViking server-based memory layer with a Hermes-Agent-style memory architecture, built step by step. The memory layer was then extracted to the standalone repo `~/projects/nm-memory-layer` (package `nm_memory_layer`) and is imported here as an editable path dependency.

### Changes

- Added `nm-memory-layer` as editable dependency in `pyproject.toml` (`tool.uv.sources` → `../nm-memory-layer`).
- `alt-main.py` became the Hermes-style implementation (main.py untouched):
  - Removed all OpenViking session persistence: `OpenVikingSessionRecorder` record/flush flow, `OpenVikingChatMessageHistory`, `_load_archived_history`, `_commit_on_exit`, and the per-turn `aassemble_openviking_context` retrieval block (~400 lines), including the `--bench-context`/`--bench-runs` CLI flags.
  - `AgentState` no longer carries `openviking_context`; the system prompt was rewritten (session-memory guidance replaces the viking skill workflow).
  - Turn-end persistence now calls `store.record_turn(session_id, new_messages)`; resume via `store.load_session()`; store closed on CLI exit.
  - Tool binding filters out `viking_*` tools (shared `tools.py` still imports them for `main.py`) and adds the `session_search` tool from `nm_memory_layer`.
  - Session DB: `./sessions.db` (WAL), override with `SESSION_DB_PATH`.
- `.gitignore`: added `sessions.db` / `sessions.db-*`.
- `state_store.py` was created during this phase and subsequently deleted after extraction to `nm-memory-layer`.

### Verified

- Graph compiles and binds `session_search`; record → reload round-trip reconstructs AIMessage/ToolMessage pairs; FTS5 search with AND → OR → LIKE fallback works; invalid-syntax and empty queries handled.

### Next

Phase 2 (prompt memory: `MEMORY.md` / `USER.md` with 3,575-char budget), then periodic nudge, skills layer, compression — implemented in `nm-memory-layer`.
