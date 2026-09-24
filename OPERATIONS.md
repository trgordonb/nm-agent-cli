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

## 3. Keep the wiki healthy — lint

```bash
uv run --script skills/llm-wiki/scripts/wiki_lint.py wiki/
```

Flags missing `[[wikilinks]]` in the index, orphan pages (nothing references them), duplicate-defined pages (identical concept in two folders), general format breakages. Run it after each ingest batch to keep the wiki cheap to navigate; concepts should stay **one idea per page** (skill convention), as extracted earlier — checkout and editing is done in a plain editor or Obsidian.

---

## 4. Graph layer — `graph.relationships` frontmatter

If the user authored typed edges (e.g. `authored`, `works_on`, `depends_on`) in a page's `graph.relationships[]` frontmatter, run:

```bash
uv run --script skills/llm-wiki/scripts/wiki_graph_lint.py wiki/      # validate typed metadata + alias collisions
uv run --script skills/llm-wiki/scripts/wiki_graph_extract.py wiki/   # rebuild nodes.jsonl, edges.jsonl, graph.sqlite, graph.graphml
```

Then merge into `wiki/graph/nodes.jsonl` and `edges.jsonl`, generate the matching `wiki/graph/graph.sqlite` and `graph.graphml`, append a `graph:` line to `wiki/log.md`: `## [YYYY-MM-DD] graph | Built graph layer: authored typed edges on 7 pages, linted, extracted (49 nodes, 421 edges)`.

---

## 5. Visualize the wiki graph

```bash
uv run --script skills/llm-wiki/scripts/wiki_graph_query.py wiki/ neighbors --node concept:mean-reversion
```

```bash
uv run --script skills/llm-wiki/scripts/wiki_graph_visualize.py wiki/ --node-limit 0
```

Produces two outputs under `wiki/graph/`:
- `graph-overview.mmd` — Mermaid flowchart (renders **only** inside a fenced code block in a `.md` file in Obsidian / GitHub / typora; the `.mmd` is a Mermaid-CLI / GitHub integrations artifact)
- `index.html` — self-contained interactive page (vis-network via CDN): drag physics, predicate-labeled edges, live title filter, click = typed-edge provenance

Both stay in `wiki/graph/` (local-only by default; push if you want a hosted copy).

Additional visual check — raise the top-N result cap with `--node-limit 0` to fill the Mermaid not-truncated (full graph when large wikis). The re-generation default is `node_limit=0` (0 = full graph): the agent will start with that and cut back if the outer page renders too long.

---

## 6. Loop it back to the agent

The graph.sqlite path for hybrid sampling (`wiki/.wiki-cache/`) is the operative cache used in `wiki_search` and `build_context`. Any pre-flight retrieval starts by loading `wiki/index.md`, then candidates listed in `index.md` — always check freshness against `wiki/log.md`; if an ingest or graph run happened, the agent runs `wiki_graph_extract.py` before querying.

---

## What stays off GitHub

| Folder / file | Created | Why it is kept |
|---|---|---|
| `wiki/` — contents only (`index.md`, `SCHEMA.md`, `log.md`, `sources/`, `entities/`, `concepts/`, `synthesis/`, `graph/`, `.wiki-cache/`) | Agent bootstrap | Every clone bootstraps its own from your own material; only folder shells match upstream |
| `raw/`, `skills/`, `memories/` contents | Skeleton tracked (.gitkeep + empty placeholder) | Same local-only reason |
| `wiki/.obsidian/` | Obsidian vault open | Local config folder |
| agent.log, sessions.db | Runtime | Large/volatile diagnostics |

Clone the repo → `uv lock --upgrade-package nm-memory-layer` → `uv sync` → `cp .env.example .env`, edit as above, then run `uv run python main.py` to bootstrap your own wiki. All artifacts are regenerated locally; nothing you add to the wiki folder needs to leave the machine.
