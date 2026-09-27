# OPERATIONS.md — NM-Agent-CLI

Operational guide for running the agent fresh from a clone: shell/LLM configuration, then the wiki bootstrap → ingest → lint → visualize loop.

---

## 1. Configure `.env` (required keys only)

Copy `.env.example` to `.env` and fill in:

| Key | What it gates |
|---|---|
| `OPENAI_API_KEY` | Primary LLM (agent turns, skill loading, tool calls) — billed at your OpenAI-compatible provider (default: z.ai, `OPENAI_BASE_URL=https://api.z.ai/api/paas/v4/`) |
| `OPENAI_BASE_URL` | Primary provider endpoint (adjust only if not using z.ai) |
| `OPENROUTER_API_KEY` | The secondary-LLM features: `session_search` result condensation + wiki context compression |
| `OPENROUTER_MODEL` | Which summarizer/compressor model to use on OpenRouter — pick a **non-gated** one (e.g. `inclusionai/ling-3.0-flash-vl:free`); gated-by-harness `:free` variants return 403 on plain API calls |
| `LANGSMITH_API_KEY` | Optional — trace export (`langsmith trace get …`) for post-run debugging |
| `LANGCHAIN_API_KEY` | Whether all LLM calls emit visible trace lines in the console while the session runs |

Everything else (`JINA_API_KEY`, `FINANCIAL_MODELING_PREP_API_KEY`, `EDGAR_IDENTITY`, `TAVILY_API_KEY`, …

Flag-like overrides:
- `SEARCH_SUMMARIZER_ENABLED=false` → raw excerpts (lexical only)
- `COMPRESSION_ENABLED=false` → always-on memory compression disabled
- `NUDGE_INTERVAL=5` — turns between periodic nudge runs

Skill-related keys (optional, at your discretion): `JINA_API_KEY` for web search/reader, `FINANCIAL_MODELING_PREP_API_KEY` for the FinanceToolkit MCP server, `EDGAR_IDENTITY` to register with SEC, `TAVILY_API_KEY` as a backup search source.

---

## 2. Bootstrap the wiki

```bash
uv sync                                        # installs nm-memory-layer + skill deps from GitHub
uv run --script skills/llm-wiki/scripts/init_wiki.py wiki/    # bootstraps wiki/, retrieval setup verified
```

Bootstrap creates:
- `wiki/index.md` — routed catalog (`sources/`, `entities/`, `concepts/`, `synthesis/`)
- `wiki/SCHEMA.md` — tag taxonomy; has LLM guides and category notes
- `wiki/log.md` — the append-only operation log; the graph layer uses it to decide freshness
- `wiki/.wiki-cache/` — local embedding cache + `fastembed` model files at `~/.cache/llm-wiki/fastembed`
- Templates for pages/experience/patterns + `graph/ontology.yaml` starter

The agent sees this automatically when `WIKI_DIR=./wiki` is set in `.env`.

---

## 3. Ingest workflow (one time, or as sources appear)

```bash
# 1) Restore or create source docs under raw/
#    (Optionally copy your existing clippings over; they never leave your machine)

uv run --script skills/llm-wiki/scripts/wiki_search.py "query terms" --top 10 --cache --json

# run the ingest from within agent session:
#   "ingest the documents in raw/ into the wiki (trace each fork via .wiki-cache/)"
```

The agent uses the `llm-wiki` skill to:

- Create `wiki/sources/<slug>.md` per raw document (title, authors, URL, takeaways).
- File links into `wiki/concepts/*.md`, `wiki/entities/*.md`, `wiki/notes/*.md` via `[[wikilinks]]`.
- Append a batch entry to `wiki/log.md`: `## [YYYY-MM-DD] ingest | batch description` with pages added.

**Tunables**:
- `wiki.log.md` must reflect page/link edits per batch — it is the freshness signal for graph.sqlite.
- `WIKI_DIR` in `.env` — defaults to `./wiki/`; used by nm-memory-layer for pre-flight recall.

---

## 4. Keep the wiki healthy — lint

```bash
uv run --script skills/llm-wiki/scripts/wiki_lint.py wiki/
```

Flags missing `[[wikilinks]]` in the index, orphan pages (nothing references them), duplicate-defined pages (identical concept in two folders), general format breakages. Run it after each ingest batch to keep the wiki cheap to navigate; concepts should stay **one idea per page** (skill convention), as extracted earlier — checkout and editing is done in a plain editor or Obsidian.

---

## 5. Graph layer — `graph.relationships` frontmatter

If the user authored typed edges (e.g. `authored`, `works_on`, `depends_on`) in a page's `graph.relationships[]` frontmatter, run:

```bash
uv run --script skills/llm-wiki/scripts/wiki_graph_lint.py wiki/      # validate typed metadata + alias collisions
uv run --script skills/llm-wiki/scripts/wiki_graph_extract.py wiki/   # rebuild nodes.jsonl, edges.jsonl, graph.sqlite, graph.graphml
```

Then merge into `wiki/graph/nodes.jsonl` and `edges.jsonl`, generate the matching `wiki/graph/graph.sqlite` and `graph.graphml`, append a `graph:` line to `wiki/log.md`: `## [YYYY-MM-DD] graph | Built graph layer: authored typed edges on 7 pages, linted, extracted (49 nodes, 421 edges)`.

---

## 6. Browse the wiki live — wiki-os

wiki-os (`wiki-os/` in the repo root, cloned from **[trgordonb/wiki-os](https://github.com/trgordonb/wiki-os)** — a fork of [Ansub/wiki-os](https://github.com/Ansub/wiki-os)) renders the vault as a local web app: article pages with working `[[wikilinks]]`, full-text search, an interactive link-graph view, and an auto-reindex file watcher. It reads the vault read-only — edits still happen in Obsidian or an editor.

**Clone the fork, not upstream:** the fork's `main` carries the graph-edge patch (resolves bare `[[wikilink]]` targets to folder-qualified page slugs — `overfitting` → `concepts/overfitting` — and refreshes backlink counts). Upstream `Ansub/wiki-os` does not: a vault with subfolder pages would render a graph of orphan nodes and dead wikilinks.

One-time setup:

```bash
git clone https://github.com/trgordonb/wiki-os.git wiki-os
cd wiki-os && npm install && npm run build
```

```bash
./start.sh          # wiki-os in background + agent in foreground (URL shown in the agent banner)
./start.sh wiki     # only the wiki-os web UI, then exit
```

- URL: `http://localhost:5211` (override with `WIKI_OS_PORT`; vault override with `WIKI_ROOT`, default `./wiki`)
- The server survives agent exits; stop it with `pkill -f "dist-server/server/server[.]js"`; logs at `wiki-os/wiki-os.log`
- Index lives in `~/.wiki-os/` — safe to delete, it rebuilds on next start
- To pull future fixes: `cd wiki-os && git pull && npm install && npm run build`

---

## 7. Loop it back to the agent

The graph.sqlite path for hybrid sampling (`wiki/.wiki-cache/`) is the operative cache used in `wiki_search` and `build_context`. Any pre-flight retrieval starts by loading `wiki/index.md`, then candidates listed in `index.md` — always check freshness against `wiki/log.md`; if an ingest or graph run happened, the agent runs `wiki_graph_extract.py` before querying.

---

## What stays off GitHub

| Folder / file | Created | Why it is kept |
|---|---|---|
| `wiki/` — contents only (`index.md`, `SCHEMA.md`, `log.md`, `sources/`, `entities/`, `concepts/`, `synthesis/`, `graph/`, `.wiki-cache/`) | Agent bootstrap | Every clone bootstraps its own from your own material; only folder shells match upstream |
| `raw/`, `skills/`, `memories/` contents | Skeleton tracked (.gitkeep + empty placeholder) | Same local-only reason |
| `wiki/.obsidian/` | Obsidian vault open | Local config folder |
| `wiki-os/` | Cloned [web UI](https://github.com/trgordonb/wiki-os) for the wiki | Separate repo (own fork — carries the graph-edge patch, see §6). Its index lives in `~/.wiki-os/` |
| agent.log, sessions.db | Runtime | Large/volatile diagnostics |

Clone the repo → `uv lock --upgrade-package nm-memory-layer` → `uv sync` → `cp .env.example .env`, edit as above, then run `uv run python main.py` to bootstrap your own wiki. All artifacts are regenerated locally; nothing you add to the wiki folder needs to leave the machine.
