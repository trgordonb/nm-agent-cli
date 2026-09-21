# HISTORY.md — langgraph-demo

Track of significant changes per branch. Dates are implementation dates.

## 2026-09-21 — branch `memory-layer` — Phase 3: periodic nudge (learning loop)

Third increment: the agent now curates its own memory without user input.

- `alt-main.py`:
  - `NudgePolicy` (from `nm_memory_layer`, interval from `NUDGE_INTERVAL` env, default 5) counts completed turns per session.
  - `run_memory_nudge`: internal LLM call after every Nth turn — the turn is flattened to plain text and reviewed by the main model with ONLY `memory_manage` bound (max 3 tool-loop iterations). Writes go to MEMORY.md/USER.md and take effect next session; nudge activity is never archived to `sessions.db`.
  - `maybe_nudge` handles policy bookkeeping; run_cli prints a one-line `[memory nudge] <summary>` when it fires; failures are logged, never fatal.
- The current prompt-memory block is still loaded once per session — nudge writes do NOT hot-reload the system prompt (Hermes next-session rule preserved).

### Verified

- Trigger logic (silent before interval, fires at interval, resets after) unit-tested in nm-memory-layer; integration tests here use a fake nudge model: nudge writes memory at interval, stays silent when nothing clears the bar, never touches the session archive, and interval is configurable.

## 2026-09-21 — branch `memory-layer` — Phase 2: always-on prompt memory

Second increment of the Hermes-style memory cutover, built in `nm-memory-layer` and consumed here.

- `alt-main.py`:
  - Binds the new `memory_manage` tool alongside `session_search` (both from `nm_memory_layer`).
  - `PromptMemory` loads `./memories/MEMORY.md` + `USER.md` **once per session** and injects the `<agent_memory>` block into the system prompt — stable prefix for prompt caching, and per the Hermes rule edits take effect from the next session.
  - System prompt now teaches the two-layer boundary: permanent knowledge → `memory_manage`; topic-specific history → `session_search`.
  - CLI banner shows memory budget usage (`N/3575 chars`).
- `memories/` now holds the always-on files (`MEMORY.md`, `USER.md` — both empty at start; `AGENTS.md` is unrelated and untouched).

### Verified

- `memory_manage` add/replace/remove round-trips through the bound tool; budget rejection returns a non-fatal "Rejected:" message (deliberately not "Error:" — `should_continue` ends the turn on "Error:" results); empty memory → no prompt block; session-store behavior unchanged.

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
