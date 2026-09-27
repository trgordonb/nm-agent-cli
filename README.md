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

## Skills

`skills/` ships with the repo in agentskills.io format: names + descriptions are indexed per session, full `SKILL.md` loads on demand via `load_skill`, and the agent patches skills itself when a workflow proves reusable.

| Skill | What it does |
|---|---|
| `browser-act` | Stealth browser automation + anti-bot extraction: `stealth-extract` pulls Cloudflare-protected pages without opening a session, headed local-Chrome sessions download gated files, with CAPTCHA assistance and remote human handoff ([browser-act](https://github.com/browser-act/skills)) |
| `agent-browser` | Fast local Chrome automation via CDP: accessibility-tree snapshots with `@eN` refs, JS eval, session persistence, HAR capture ([npm: agent-browser](https://www.npmjs.com/package/agent-browser)) — also exposed to the agent as a 29-tool MCP server |
| `convert-web-article-to-md` | Web articles → agent-readable Markdown: native `$`/`$$` LaTeX, language-tagged code fences, downloaded figures, provenance front matter. Cloudflare-blocked fetches route through browser-act; `--math-images` transcribes equations rendered as images (Wayback + vision pass) |
| `convert-arxiv-to-md` | arXiv papers → Markdown from the LaTeX source via pandoc: real tables, native math, figures, references |
| `convert-pdf-to-md` | Local PDF documents → Markdown for analysis, search, and extraction |
| `llm-wiki` | Bootstrap / ingest / lint / graph pipeline for the OKF knowledge vault in `wiki/` (sources, entities, concepts, synthesis, typed graph layer) |
| `edgar` | SEC EDGAR filings in Python via EdgarTools (10-K, 10-Q, 8-K, 13F, Form 4, insider trading) |
| `financial-toolkits` | FinanceToolkit locally in Python: 200+ ratios, indicators, models, and economic indicators (FMP-backed) |
| `tradedesk-dukascopy` | Dukascopy tick-data fetch pipelines for backtests (forex, indices, stocks; ticker naming differs from yfinance) |

The two browser skills are complementary: **browser-act** handles bot-walled targets (stealth fingerprints, proxies, confirmation-gated cloud resources), **agent-browser** is the fast local workhorse — on Cloudflare-walled sites launch it headed with `AGENT_BROWSER_ARGS="--disable-blink-features=AutomationControlled"`.

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
- `skills/` — agent-loadable skills, tracked on GitHub; the agent patches them itself when a workflow proves reusable

## Docs

- `CLAUDE.md` — repo working notes for agents (wiring, env, remaining OpenViking traces)
- `HISTORY.md` — per-phase changelog of the memory-layer cutover
- Memory layer internals: https://github.com/trgordonb/nm-memory-layer (`CLAUDE.md` there is the full API reference)
- Engine docs: https://hermes-agent.nousresearch.com/docs (the architecture this repo mirrors)
