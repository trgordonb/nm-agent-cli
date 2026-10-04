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
- Wiki recall: when `WIKI_DIR` (default `./wiki`) points at an llm-wiki-v3 wiki with pages, each user turn pre-flight matches the request against wiki sections (hybrid: sqlite-vec KNN + lexical RRF via `nm-memory-layer[wiki-hybrid]` deps) and injects a `<wiki_context>` block into that turn's system prompt (never archived); `wiki_search` is bound for deeper retrieval.
- Before each turn, if `COMPRESSION_ENABLED=true` and the history exceeds `COMPRESSION_TOKEN_THRESHOLD` (default 24000), middle turns are summarized by the OpenRouter model into a `<conversation_summary>` SystemMessage; the first + recent `COMPRESSION_KEEP_RECENT_TURNS` turns stay verbatim; lineage is recorded to the `compressions` table in `sessions.db`. Failure → history untouched.
- `tools.py` still imports/creates OpenViking tool bindings at import (`viking_` prefix); `main.py` filters them out when binding tools. Removing them from `tools.py` + `pyproject.toml` is the remaining cutover cleanup.

### Remaining OpenViking traces

`tools.py` (viking tool bindings) and `.env` `OPENVIKING_*` vars are the only leftovers; both inert for `main.py`.

## Skills

`skills/` is a **local mirror of the skills registry** (`nm-skills-registry`, sibling repo) — the authoritative store is S3-compatible (Cloudflare R2, bucket `neuralmatrix`, prefix `skills/`), configured via `.env` `SKILLS_REGISTRY=s3://neuralmatrix` + `R2_*` creds. The index (names + descriptions) auto-injects per session; `load_skill` pulls the full SKILL.md; the agent curates skills itself via `skill_manage` (create/patch/edit/delete/write_file/remove_file/**enable**/**disable**) + memory nudges. **Hermes-style toggles:** `skill_manage(enable|disable)` or `POST /api/skills/{name}/enabled {"enabled": bool}` — disabled skills vanish from the index/`load_skill` (invisible = not found) but stay listable via `list_all()` / `GET /api/skills` / `nm-skills list`; state lives at `state/users/<user>/skills.json` in the bucket, enabled-by-default, and takes full effect **next session**. Mirror is write-through + offline-tolerant (last-known content served if R2 is unreachable). CLI: `uv run nm-skills {list,enable,disable,import,pull,push,sync,doctor}`. `raw/` is also bucket-backed (prefix `raw/`, explicit `nm-skills import|sync raw` — no auto-sync). Plan + decisions: `SKILLS_REGISTRY_PLAN.md`; git stopped tracking `skills/` at tag `skills-in-git-final`.

- **browser-act** — stealth browser automation + anti-bot extraction: `stealth-extract <url> --content-type html|markdown` pulls CF-protected pages sessionless; headed local-Chrome sessions download gated files (`media resources download`); captcha ladder ends in `remote-assist`. Load the skill before ANY browser-act CLI command; browser create/delete are Confirmation-Gated (present plan → stop → wait → execute). Prior approvals never carry over.
- **agent-browser** — local CDP automation (snapshots with `@eN` refs, `eval --stdin`, sessions, HAR); also bound as a stdio MCP server → 29 `agent_browser_*` tools on session `nm-agent`. Bot-walled sites: stock build exposes `navigator.webdriver` — launch headed with `AGENT_BROWSER_ARGS="--disable-blink-features=AutomationControlled"`, then in-page `fetch` retrieves gated assets (base64 out, decode twice).
- **convert-web-article-to-md** — articles → agent-readable md (math/code recovery, provenance front matter, figures in `media/`). Cloudflare 403s: the fetch error prints the exact browser-act rescue command. `--math-images` (opt-in): detects equation images → direct/Wayback download (incl. CDX scaled-variant fallback) → `math-images.json` manifest → agent vision transcription per `references/math-and-code-rules.md` §6 (upscale 3×, faithful notation, sanity checks, never invent).
- **convert-arxiv-to-md** / **convert-pdf-to-md** — routing siblings: arXiv papers go to the arxiv skill (LaTeX source beats HTML), local PDFs to the pdf skill; web URLs stay here.
- **llm-wiki** — vault bootstrap, ingest, lint, and graph extraction for `wiki/` (see OPERATIONS.md §2–§5, §8).
- **edgar** (SEC filings via EdgarTools), **financial-toolkits** (FMP-backed analytics), **tradedesk-dukascopy** (tick-data pipelines) — the original research toolchain.

## MCP servers

Configured in **`mcp_servers.json`** (repo root, git-tracked — see `MCP_TOGGLE_PLAN.md`): per-server `transport`/`command`/`args`/`env`/`url`/`headers`, `enabled` flag, optional `keep_tools`. Secrets are `${VAR}`-interpolated from the environment at load (fail-closed on unresolved). `_load_mcp_tools()` (`main.py`) connects each enabled server independently (one bad server = warning + skip) and reports per-server status into the runtime (`mcp_report`). Toggles: web UI **gear icon** (sidebar footer) → Settings → Skills | MCP, or `GET/POST /api/mcp*` — edits the JSON atomically and apply after **Reload runtime** (`POST /api/mcp/reload`, 409 while turns stream) on the server, or at the next CLI session. `finance_toolkit` (FMP-backed) is configured but disabled.

## Commands

```bash
uv run python main.py                     # run agent with local memory (new session)
uv run python main.py --session-id …      # resume a stored session
uv sync                                   # install deps (incl. editable nm-memory-layer)
uv run pytest tests/ -q                   # integration tests for main.py wiring (no LLM calls)
```

## Roadmap

Phases 2–5 (prompt memory, periodic nudge, skills layer, compression) are implemented in `nm-memory-layer` and wired here; see that repo's CLAUDE.md.

## TODO

- [ ] **PixelRAG pilot for wiki visual retrieval** (evaluated 2026-09-27; [repo](https://github.com/StarTrail-org/PixelRAG), 10.1k stars, active). Renders documents (pages/PDFs) as screenshot tiles, embeds with Qwen3-VL, retrieves over images — charts/tables/appendix figures stay queryable. **NOT for `convert-web-article-to-md`**: it is a retrieval/reading layer, not a conversion layer, and its page-render screenshots are lower fidelity than the original assets the skill fetches (see 2026-09-27 session lessons: original-asset bytes beat page renders; element screenshots hit lazy-load placeholders; pix2tex OCR unusable on rendered math — vision-LLM transcription is the working path). **Fit:** index converted articles (`workspace/`, wiki) so the wiki can answer chart/table questions. **Pilot:** `uv tool install pixelrag` (light) → `pip install 'pixelrag[embed,serve]'` (PyTorch + FAISS — heavy; wants GPU/MPS, unverified on this box) → index a handful of converted articles → ask chart questions → judge answer quality. **Caveats:** verify license type before dependency commit; hosted API (api.pixelrag.ai) is Wikipedia-only, so our docs require self-hosting.

### Wiki: in-process Python engine (wiki_engine/) — replaced the wiki-os Node engine, 2026-10-03

**Current state.** The wiki (React "Wiki" tab) is served end-to-end by `wiki_engine/`, a faithful Python port of the wiki-os Node engine (Ansub/wiki-os fork `trgordonb/wiki-os`, MIT), mounted in-process in `server.py` at `/wapi/api/*` — the same paths the frontend has always consumed, so the React side never changed. The Node engine and its folder are **gone**: archived (sans node_modules) at `workspace/wiki-archive/wiki-os-node-engine-20261003.tar.gz`, fork still on GitHub. `start.sh` boots only the CLI agent and just exports `WIKI_ROOT` (default `<repo>/wiki`).

**Engine layout** (all stdlib — sqlite3 FTS5, threading, re; zero new deps):
- `config.py` — UI config (= upstream defaults; optional `~/.wiki-os-py/ui-config.json` override), topic key/label/color/emoji helpers, path resolution (`WIKI_ROOT`, DB at `~/.wiki-os-py/indexes/<sha1(wikiRoot)>.sqlite`, person overrides at `~/.wiki-os-py/config.json`).
- `markdown.py` / `classification.py` / `db.py` / `indexer.py` / `queries.py` — line-exact ports of the TS modules: hand-rolled frontmatter, `[[wikilink]]`→`/wiki/` transform, headings, category derivation (frontmatter → folders → frequency heuristics), person detection (explicit/hybrid), FTS5 search (`"term"*` AND, bm25 candidate pool of 80 + deterministic JS-style rescoring: +10 title, +1/occurrence), backlink/graph extraction, stats/home aggregation.
- `runtime.py` — engine singleton: integrity check + quarantine-and-rebuild, revision counter + derived-data cache, mtime reconcile. **Simplification vs upstream**: the fs.watch/debounce/backoff machinery (~700 LOC) became a background mtime-poll thread (`WIKI_ENGINE_POLL_SECS`, default 10 s) + `POST /wapi/api/admin/reindex` for forced rebuilds.
- `routes.py` — APIRouter: `GET config, home, stats, graph, search?q, wiki/{slug}, health`, `POST admin/reindex` (optional `WIKIOS_ADMIN_TOKEN`), `POST setup/person-override` (409 SETUP_REQUIRED when the vault is missing — the frontend hides "Mark as person" on 409). Setup/folder-picker/browser-launch surfaces intentionally not ported.

**The fork's patch is preserved**: bare-wikilink targets (`[[overfitting]]`) resolve to folder-qualified slugs (`concepts/overfitting`) in both the backlinks table and rendered content hrefs (exact-path match beats same-stem-in-subfolder; unresolvable links keep their bare slug and produce no edge). Covered by tests.

**Verification** (2026-10-03): 20 engine tests (`tests/test_wiki_engine.py`: temp vault, shapes, patch behavior, reconcile on edit/delete, overrides persistence, 409/404, slug encoding) + **A/B parity against the live Node engine — all 17 checks identical** (config, stats, 4 search queries with exact scores, graph nodes/edges/fields, 4 pages, home lists; mtime floats compared with a 1 ms epsilon since libuv and Python round the same timestamp to different last-ulp values — `st_mtime*1000` matches Node bit-for-bit on most files). Browser regression of every wiki-tab view passed.

**Gotchas / notes**:
- `state` paths are read lazily from env (`WIKI_ENGINE_STATE_DIR`) — never bake them at import time (an import-time constant leaked test overrides into the real state dir once).
- `normalize_topic_key`/`format_topic_label` must keep the TS semantics exactly (`.lower()`, single leading-`#` strip, no final trim) — they feed alias lookups and dedupe; a drift shows up as wrong "Most Connected"/category labels.
- mtime compare tolerance is 0.5 ms on `mtime*1000` floats, matching upstream.
- Upstream `Ansub/wiki-os` (last touched April 2026) remains the reference if we ever want a feature from it; the archive has the full pre-port source.
- The wiki tab frontend details (Tailwind-without-preflight, scoped `.wikios` CSS, sub-view state, homepage sections) — see git history for the Option C write-up (steps 1–4, 2026-10-02/03); the React side of that work is unchanged.

## Memory files and git

`memories/MEMORY.md` and `memories/USER.md` are committed as **empty placeholders**; the agent's locally curated content is hidden from git via `skip-worktree` (see `git ls-files -v | grep ^S`). After a fresh clone, the placeholders are empty — the agent works fine with empty memory (it re-learns via the nudge). If a file gets accidentally overwritten locally, restore curated content from a backup and re-run `git update-index --skip-worktree memories/MEMORY.md memories/USER.md`.