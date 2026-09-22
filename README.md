# NM-Agent-CLI

https://github.com/trgordonb/NM-Agent-CLI

A LangGraph financial-research agent that runs on the **Hermes-style memory layer** ([nm-memory-layer](https://github.com/trgordonb/nm-memory-layer)) — a self-improving agent whose learning loop is the memory system itself, not model weights.

The agent: EDGAR filings (EdgarTools), market-data pipelines (Dukascopy tick data via the `tradedesk-dukascopy` toolchain), and web research (Jina), orchestrated by a LangGraph tool-calling loop.

## Memory architecture

| Layer | Mechanism |
|---|---|
| Episodic | Every completed turn archived to `sessions.db` (SQLite/WAL, FTS5); the agent deliberately searches it via the `session_search` tool |
| Always-on prompt memory | `memories/MEMORY.md` + `USER.md` (3,575-char combined budget) injected once per session; edits take effect next session |
| Agent-curated memory | A `memory nudge` fires every `NUDGE_INTERVAL` completed turns: the agent reviews the turn and writes prompt memory or patches skills itself |
| Procedural | `skills/` in agentskills.io format; only names + descriptions load per session — full `SKILL.md` on demand via `load_skill` |
| Search summarization | FTS5 excerpts condensed by a secondary LLM (OpenRouter) before entering context — `[session_search: condensed by ...]` |
| Context compression | Before the token threshold, middle turns are summarized into a `<conversation_summary>` block; turns stay fully archived with lineage in the `compressions` table |

All memory code lives in the [nm-memory-layer](https://github.com/trgordonb/nm-memory-layer) repo — see its README (and its `CLAUDE.md` for the full API reference). This repo is the consumer.

Copy `.env.example` to `.env` and fill in your keys.

## Quick start

```bash
uv sync                # installs deps incl. nm-memory-layer from GitHub
uv run pytest tests/ -q  # integration tests for main.py wiring (no LLM calls)
uv run python main.py                   # run agent (new session)
uv run python main.py --session-id <id> # resume a stored session
```

Env config lives in `.env` (not committed): `OPENAI_API_KEY`/`OPENAI_BASE_URL` (primary model), `JINA_API_KEY` (search/fetch), `FINANCIAL_MODELING_PREP_API_KEY` (Finance Toolkit MCP), plus the optional OpenRouter knobs (`SEARCH_SUMMARIZER_ENABLED`, `COMPRESSION_ENABLED`, `OPENROUTER_MODEL`).

## Runtime artifacts

- `sessions.db` — verbatim turn archive (WAL); resumable via `--session-id`; exportable via `nm_memory_layer.SessionStore.export_to_jsonl`
- `memories/` — the always-on memory files the agent curates (`MEMORY.md`, `USER.md`)
- `skills/` — agent-loadable skills; the agent patches them itself when a workflow proves reusable

## Docs

- `CLAUDE.md` — repo working notes for agents (wiring, env, remaining OpenViking traces)
- `HISTORY.md` — per-phase changelog of the memory-layer cutover
- Memory layer internals: https://github.com/trgordonb/nm-memory-layer (`CLAUDE.md` there is the full API reference)
- Engine docs: https://hermes-agent.nousresearch.com/docs (the architecture this repo mirrors)
