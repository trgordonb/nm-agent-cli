# NM-Agent-CLI

https://github.com/trgordonb/NM-Agent-CLI

<img src="frontend/public/logo-mark.png" height="30" align="top" alt="Neural Matrix Agent"> [![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org) [![LangGraph](https://img.shields.io/badge/LangGraph-agent%20loop-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/) [![FastAPI](https://img.shields.io/badge/FastAPI-agent%20%2B%20wiki%20API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com) [![Web UI](https://img.shields.io/badge/web%20UI-React%20%2B%20Vite-61DAFB?logo=react&logoColor=black)](frontend) [![memory layer](https://img.shields.io/badge/nm--memory--layer-v0.1.6-8A2BE2)](https://github.com/trgordonb/nm-memory-layer)

A LangGraph financial-research agent that runs on the **Hermes-style memory layer** ([nm-memory-layer](https://github.com/trgordonb/nm-memory-layer)) — a self-improving agent whose learning loop is the memory system itself, not model weights.

The agent: EDGAR filings (EdgarTools), market-data pipelines (Dukascopy tick data via the `tradedesk-dukascopy` toolchain), and web research (Jina), orchestrated by a LangGraph tool-calling loop.

## Memory architecture

| Layer | Mechanism |
|---|---|
| Episodic | Every completed turn archived to `sessions.db` (SQLite/WAL, FTS5); the agent deliberately searches it via the `session_search` tool |
| Always-on prompt memory | `memories/MEMORY.md` + `USER.md` (3,575-char combined budget) injected once per session; edits take effect next session |
| Agent-curated memory | A `memory nudge` fires every `NUDGE_INTERVAL` completed turns: the agent reviews the turn and writes prompt memory or patches skills itself |
| Procedural | Skills in agentskills.io format, stored in an S3-backed registry ([nm-skills-registry](https://github.com/trgordonb/nm-skills-registry), R2) with per-user enable/disable; only names + descriptions load per session — full `SKILL.md` on demand via `load_skill`; the agent curates skills itself via `skill_manage` (create/patch/edit/delete/**enable**/**disable**) |
| Search summarization | FTS5 excerpts condensed by a secondary LLM (OpenRouter) before entering context — `[session_search: condensed by ...]` |
| Context compression | Before the token threshold, middle turns are summarized into a `<conversation_summary>` block; turns stay fully archived with lineage in the `compressions` table |

All memory code lives in the [nm-memory-layer](https://github.com/trgordonb/nm-memory-layer) repo — see its README (and its `CLAUDE.md` for the full API reference). This repo is the consumer.

Copy `.env.example` to `.env` and fill in your keys.

## Skills

Skills live in an **S3-backed registry** ([nm-skills-registry](https://github.com/trgordonb/nm-skills-registry), `SKILLS_REGISTRY=s3://neuralmatrix` on Cloudflare R2). `skills/` in the repo is a write-through local mirror — same layout, same script paths — so everything below runs unchanged. The agent curates skills itself via `skill_manage` (create/patch/edit/delete/write_file/remove_file/enable/disable); Hermes-style **enable/disable** toggles are available in the web UI (gear icon → Skills), over REST, or via the `nm-skills` CLI, and apply to new sessions.

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
uv sync                # installs deps incl. nm-memory-layer + nm-skills-registry from GitHub
uv run pytest tests/ -q  # integration tests for main.py wiring (no LLM calls)
uv run python main.py                   # run agent (new session)
uv run python main.py --session-id <id> # resume a stored session

# Web UI (chat + wiki + skills/MCP settings):
uv run python server.py   # FastAPI on :8000 (agent + in-process wiki engine at /wapi)
cd frontend && npm install && npm run dev   # Vite dev server on :5173
```

Env config lives in `.env` (not committed): `OPENAI_API_KEY`/`OPENAI_BASE_URL` (primary model), `JINA_API_KEY` (search/fetch), `FINANCIAL_MODELING_PREP_API_KEY` (Finance Toolkit MCP), `SKILLS_REGISTRY` + `R2_*` (skills registry bucket), plus the optional OpenRouter knobs (`SEARCH_SUMMARIZER_ENABLED`, `COMPRESSION_ENABLED`, `OPENROUTER_MODEL`).

MCP servers are configured in **`mcp_servers.json`** (git-tracked): per-server transport/command, `enabled` flag, `keep_tools` filter; secrets are `${VAR}`-interpolated from the environment. Toggle in the web UI (gear icon → MCP) or via `POST /api/mcp/{name}/enabled` + `POST /api/mcp/reload`.

## Runtime artifacts

- `sessions.db` — verbatim turn archive (WAL); resumable via `--session-id`; exportable via `nm_memory_layer.SessionStore.export_to_jsonl`
- `memories/` — the always-on memory files the agent curates (`MEMORY.md`, `USER.md`)
- `skills/` — local mirror of the skills registry (authoritative copy in the R2 bucket; the agent patches skills itself via `skill_manage`)
- `mcp_servers.json` — MCP server registry (git-tracked; toggles rewrite it atomically)

## Docs

- `CLAUDE.md` — repo working notes for agents (wiring, env, remaining OpenViking traces)
- `HISTORY.md` — per-phase changelog
- `OPERATIONS.md` — wiki + registry operations manual
- `SKILLS_REGISTRY_PLAN.md`, `MCP_TOGGLE_PLAN.md` — design docs for the registry and MCP toggles
- Memory layer internals: https://github.com/trgordonb/nm-memory-layer (`CLAUDE.md` there is the full API reference)
- Engine docs: https://hermes-agent.nousresearch.com/docs (the architecture this repo mirrors)
