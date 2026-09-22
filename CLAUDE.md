# CLAUDE.md — langgraph-demo

LangGraph agent (financial research assistant: EDGAR, market data, web search) running on the **Hermes-style memory layer** (`nm-memory-layer`, installed from GitHub as a regular dependency).

## Memory layer (branch `memory-layer`)

The Hermes-style memory system (learning loop, agent-curated memory, session search, multi-level memory) lives in a **separate repo**: `~/projects/nm-memory-layer` (package `nm_memory_layer`), installed here as an **editable path dependency** via `[tool.uv.sources]` in `pyproject.toml`. Edit memory-layer code there, not here — changes apply immediately without reinstalling.

Current phase: **All five phases complete — session store, prompt memory, nudge, skills, search summarization, context compression.** The OpenViking version (`main.py` pre-rename + `llm_wiki_ingest.py`) was deleted on 2026-09-21; `alt-main.py` became `main.py` and is the single implementation.

### How main.py persists sessions

- `SessionStore` from `nm_memory_layer` writes every completed turn to `./sessions.db` (WAL mode; override with `SESSION_DB_PATH`).
- Resume with `--session-id <id>`; history is rebuilt from the local store including tool-call pairs.
- The agent gets a `session_search` tool for deliberate retrieval of past-session context (replaces OpenViking's per-turn context assembly).
- The agent also gets `memory_manage` for the always-on layer: `PromptMemory` loads `./memories/MEMORY.md` + `USER.md` once per session into the system prompt (3,575-char combined budget; edits take effect next session).
- The agent gets `skill_manage` + `load_skill` for procedural memory: the `./skills/` index (names + descriptions only) is injected once per session; full SKILL.md loads on demand — replacing OpenViking's `<skill>` abstract / `viking_read` flow with zero server dependency.
- After each turn, `maybe_nudge` counts it; every `NUDGE_INTERVAL` turns (default 5, env `NUDGE_INTERVAL`) an internal "memory nudge" LLM call reviews the turn and may write prompt memory (`memory_manage`) or create/patch skills (`skill_manage`) — no user input, and nudge activity is never archived to `sessions.db`.
- `session_search` can optionally condense its FTS5 excerpts through a secondary LLM (OpenRouter) before they enter context: `SEARCH_SUMMARIZER_ENABLED=true` + `OPENROUTER_MODEL` in `.env` turn it on; disabled or failing → raw excerpts (graceful fallback). The CLI banner shows which mode is active; summarized results carry a `[session_search: condensed by ...]` header.
- Before each turn, if `COMPRESSION_ENABLED=true` and the history exceeds `COMPRESSION_TOKEN_THRESHOLD` (default 24000), middle turns are summarized by the OpenRouter model into a `<conversation_summary>` SystemMessage; the first + recent `COMPRESSION_KEEP_RECENT_TURNS` turns stay verbatim; lineage is recorded to the `compressions` table in `sessions.db`. Failure → history untouched.
- `tools.py` still imports/creates OpenViking tool bindings at import (`viking_` prefix); `main.py` filters them out when binding tools. Removing them from `tools.py` + `pyproject.toml` is the remaining cutover cleanup.

### Remaining OpenViking traces

`tools.py` (viking tool bindings) and `.env` `OPENVIKING_*` vars are the only leftovers; both inert for `main.py`.

## Commands

```bash
uv run python main.py                     # run agent with local memory (new session)
uv run python main.py --session-id …      # resume a stored session
uv sync                                   # install deps (incl. editable nm-memory-layer)
uv run pytest tests/ -q                   # integration tests for main.py wiring (no LLM calls)
```

## Roadmap

Phases 2–5 (prompt memory, periodic nudge, skills layer, compression) are implemented in `nm-memory-layer` and wired here; see that repo's CLAUDE.md.

## Memory files and git

`memories/MEMORY.md` and `memories/USER.md` are committed as **empty placeholders**; the agent's locally curated content is hidden from git via `skip-worktree` (see `git ls-files -v | grep ^S`). After a fresh clone, the placeholders are empty — the agent works fine with empty memory (it re-learns via the nudge). If a file gets accidentally overwritten locally, restore curated content from a backup and re-run `git update-index --skip-worktree memories/MEMORY.md memories/USER.md`.