# HISTORY.md — langgraph-demo

Track of significant changes per branch. Dates are implementation dates.

## 2026-10-04 — branch `fastapi` — web UI (server + React), skills registry on R2, MCP toggles

- **FastAPI server + in-process Python wiki engine + React frontend.** `server.py` serves the chat/SSE surface and mounts the wiki engine (`wiki_engine/` — a stdlib-only port of the wiki-os Node engine: fs.watch became a 10 s mtime poll, the fork's bare-wikilink patch preserved, A/B-verified 17/17 against the Node engine) at `/wapi/api/*`; `frontend/` (React + Vite) renders Chat, Wiki, and a settings view. The Node engine is archived at `workspace/wiki-archive/`.
- **Skills registry cutover (Option A).** New sibling package [nm-skills-registry](https://github.com/trgordonb/nm-skills-registry): a 7-primitive object-store core (LocalDirStore / S3ObjectStore via obstore / CachedStore — S3 authority, write-through local mirror, ETag revalidation, offline fallback) + `SkillRegistry` (byte-parity port of `SkillLibrary`: index, resolve ordering, curation messages, frontmatter template) + per-user enable/disable state (enabled-by-default disabled-list, ETag CAS). Authoritative store: Cloudflare R2 bucket `neuralmatrix` (`SKILLS_REGISTRY=s3://neuralmatrix`); `./skills` stays as the materialized working copy so skill scripts run unchanged; `raw/` is bucket-backed via the `nm-skills` CLI (import/pull/push/sync). `nm-memory-layer`'s `SkillLibrary` became a delegating facade (parity: index, listing, 14 resolve/load pairs and 10 curation ops byte-identical vs the git-history implementation; its whole suite passes on the facade). Git stopped tracking `skills/` (tag `skills-in-git-final`); 149 skill objects + 716 `raw/` objects imported to the bucket.
- **Hermes-style toggles, everywhere.** `skill_manage(enable|disable)`, `GET/POST /api/skills*`, and a **gear icon** in the sidebar footer opening the settings view (Skills | MCP switcher). Disabled skills are invisible to index/`load_skill` (not-found semantics), state lives at `state/users/<user>/skills.json` in the bucket, applies next session. Browser-verified: toggle off → Refresh → persisted → toggle back.
- **MCP servers → `mcp_servers.json`** (repo root, git-tracked; see `MCP_TOGGLE_PLAN.md`): per-server `transport`/`command`/`args`/`env`/`keep_tools` + `enabled`, `${VAR}`-interpolated secrets (fail-closed), replacing the hardcoded agent_browser dict and the dormant Finance Toolkit comment block. `_load_mcp_tools` connects each enabled server independently (one bad server = warning + skip) and reports per-server status; `POST /api/mcp/reload` re-assembles the runtime (409 while turns stream). **luxalgo** ([LuxAlgo/luxalgo-mcp-server](https://github.com/LuxAlgo/luxalgo-mcp-server), keyless `npx -y @luxalgo/mcp`) added filtered to its 9 `library_*` + 4 `trackers_*` tools (journal/brokers/propfirms/account filtered out).
- **Library releases**: nm-skills-registry + nm-memory-layer tagged `v0.1.0` and `v0.1.1` (v0.1.1: `CachedStore.get_with_etag` revalidates against a fresh HEAD — a stale index ETag made CAS retries loop forever after an out-of-band write, caught live by the browser toggle test as a 500; and multi-word `keep_tools` suffix matching), langgraph-demo pins the tags.
- **Verification**: 70 python tests (loader/interpolation, FastMCP-stdio wiring incl. broken-server resilience, endpoints, skills toggles, wiki engine), `tsc` + vite build, browser passes for gear → Skills and MCP tabs (toggle → Refresh persistence → Reload runtime: 0 tools when agent_browser disabled, 29 when re-enabled), and a live LangSmith trace (`01a10685`) showing the agent using `library_search` / `library_get_concept` / `library_get_indicator` in a real ORB research turn with a structured slug error handled gracefully.

## 2026-09-27 — branch `main` — browser skills, math-as-images pipeline, wiki-os UI

- `skills/` is now tracked on GitHub (`.gitignore` drops the local-only skills block): `browser-act` and `agent-browser` join the conversion skills; CLAUDE.md + README.md document all nine.
- **browser-act verified end-to-end.** `stealth-extract` pulls Cloudflare-protected pages sessionless (coderprog.com behind CAPTCHA; SSRN abstracts; alphaarchitect articles). Chrome-type automation confirmed free (no billing/lifecycle fields on local browsers). Headed local Chrome clears challenges headless cannot: SSRN 4901967 PDF (45 pp) downloaded by clicking the real Delivery.cfm button; gated `wp-content` images pulled via `media resources download` (sha256-verified).
- **convert-web-article-to-md hardened.** The HTTP-403 fetch error now prints the exact browser-act rescue command; SKILL.md gained "Cloudflare-protected and bot-blocked sites" + "Math rendered as images" sections; troubleshooting table and JS-rendering guidance route through browser-act.
- **`--math-images` pipeline (opt-in).** Detects equations rendered as images, downloads what is fetchable (direct → Wayback, incl. CDX scaled-variant fallback), writes `math-images.json`, and hands off to the agent's vision pass — fidelity rules documented in `references/math-and-code-rules.md` §6 (upscale 3×, faithful notation, prose cross-checks, unity-DC-gain-style sanity checks, never invent).
- **Trend-Following Filters series converted.** Part 10 fully: all 6 equation images transcribed to native `$$` LaTeX by vision (TLWMA verified via the unity-DC-gain identity, TES cross-checked against the IIR form). Part 9 md complete; remaining gated images left as absolute URLs by choice.
- **agent-browser evaluated and wired.** Stock build exposes `navigator.webdriver` — the Cloudflare challenge won't clear even with a human click. Launched headed with `AGENT_BROWSER_ARGS="--disable-blink-features=AutomationControlled"` it clears challenges unattended and in-page `eval` fetches gated assets as base64. Wired into `main.py` as a stdio MCP server (29 `agent_browser_*` tools on a dedicated `nm-agent` session); the Finance Toolkit MCP stays dormant.
- **LangSmith traces** confirmed the agent runs the new pipeline autonomously: alphaarchitect part-9 (403 → browser-act rescue → conversion → Confirmation Gate for the image fetch) and QuantStart OU article (direct conversion: 9 `$$`, 37 inline math, 2 code fences, zero warnings).
- **wiki-os adopted as the wiki's web UI** ([trgordonb/wiki-os](https://github.com/trgordonb/wiki-os) — fork carrying the graph-edge patch). Root-caused the 0-edge graph: backlink targets were indexed as bare note names while page slugs are folder-qualified vault paths. Patch (`resolveBacklinkTargets` + `resolvePageContentLinks` in `wiki-db.ts`, wired through the indexer) resolves targets, refreshes `backlink_count`, rewrites stored `/wiki/` hrefs, and keeps FTS in sync — verified 494 edges / 64 connected nodes, backlink counts populated, pushed to the fork's `main` (`bc4e7fe`).
- **`start.sh`** starts wiki-os (background, health-polled) + the agent together; the agent banner now shows the wiki-os URL (reachability-checked, `WIKI_OS_URL` override). OPERATIONS.md restructured: wiki-os is §6, the Mermaid/vis-network visualization workflow it supersedes was removed, off-GitHub table updated.
- **PixelRAG evaluated** (visual-RAG over rendered tiles): not a fit for the converter (retrieval layer, not conversion; rendered tiles lose to original-asset bytes). Logged as a TODO in CLAUDE.md for a wiki visual-retrieval pilot.
- Local smoke tests: `npm run typecheck` + 34 wiki-os tests + 21 agent wiring tests green; all transient servers/clients cleaned up after verification runs.

## 2026-09-23 — branch `wiki` — hybrid wiki search + first ingest (30 pages)

- Ingest took over from keyword recall only after nm-memory-layer's `nm-memory-layer[wiki-hybrid]` extra was honored here (fastembed + sqlite-vec pulled in). `WikiStore` now runs the full hybrid path when the wiki has been initialized by the skill's own `.wiki-cache/`.
- 10 quant-research clippings ingested (trace 01a0ce7e): 30 wiki pages (10 source, 2 entity, 29->29 concept pages), tag taxonomy in SCHEMA.md, cross-links across the Sepp/Alvarez corpus; graph layer not yet populated.
- `.env.example` gained WIKI_DIR=./wiki; `raw/` clippings stay local-only (folder shell committed).

## 2026-09-22 — branch `memory-layer` — wiki recall layer (llm-wiki)

Seventh memory layer: the local llm-wiki (OKF) knowledge base.

- Pre-flight `<wiki_context>` injection per user turn (telemetry line `wiki ∙ N matching page(s) recalled`), never archived — the prompt prefix stays per-turn this time (OpenViking-style injection), accepted cache cost for always-relevant recall.
- Conditions: only when the wiki exists AND pages rank > 0; `WIKI_DIR` env (default `./llm-wiki`).
- `wiki_search` tool bound alongside the other memory tools when the wiki exists; live-verified the agent citing wiki notes and reading `raw/` sources.

## 2026-09-21 — branch `memory-layer` — Phase 5: context compression with lineage

Final phase of the Hermes-style memory stack.

- `alt-main.py` builds the OpenRouter-backed compressor (`create_openrouter_compressor()`) and runs a pre-flight check before each user turn (in a worker thread): when the history's estimated token size exceeds `COMPRESSION_TOKEN_THRESHOLD`, the middle turns are summarized into a `<conversation_summary>` SystemMessage; turn 1 (the original task) and the last `COMPRESSION_KEEP_RECENT_TURNS` turns stay verbatim; tool-call pairs are never split.
- Lineage (summarized turn range + summary + model + message count) is recorded to the `compressions` table in `sessions.db`; the archive always retains every turn verbatim and searchable via `session_search`.
- Failure semantics: model error/empty output/too-few-turns → original history untouched. The CLI banner shows compressor mode; compression events print a `[context compression]` line.
- `.env` gains `COMPRESSION_ENABLED` (off by default), `COMPRESSION_TOKEN_THRESHOLD` (24000), `COMPRESSION_KEEP_RECENT_TURNS` (2).

## 2026-09-21 — branch `memory-layer` — search summarization via OpenRouter (env-toggled)

- `alt-main.py` builds the optional secondary-LLM summarizer (`create_openrouter_summarizer()`) and passes it to `create_session_search_tool`; the CLI banner shows the active mode (`openrouter/<model>` vs `disabled (raw excerpts)`).
- `.env` gains `SEARCH_SUMMARIZER_ENABLED` (toggle for A/B comparison) and `OPENROUTER_MODEL` (placeholder — must be set to a valid OpenRouter model id for the feature to activate).
- Behavior when enabled: `session_search` fetches ≥8 excerpts, condenses them via one OpenRouter call, and returns a summary with a `[session_search: condensed by ... in <ms>ms from <n> raw excerpts]` header; summarizer failure/timeout → silent fallback to raw excerpts. Latency is also logged per call at INFO.

## 2026-09-21 — branch `memory-layer` — Phase 4: skills layer (procedural memory)

Fourth increment: local skills replace the last OpenViking capability (skill abstracts + `viking_read`) with zero server dependency.

- `alt-main.py`:
  - Binds `skill_manage` + `load_skill` (from `nm_memory_layer`) — total toolset is now: local file/web tools + session_search + memory_manage + skill_manage + load_skill.
  - `./skills/` (the pre-existing edgar / financial-toolkits / tradedesk-dukascopy skills, already agentskills.io-style) is indexed once per session: names + descriptions only, injected as `<skills_index>`; full SKILL.md enters context only via `load_skill` — progressive disclosure keeps token cost flat as skills accumulate.
  - System prompt teaches: matching skill → `load_skill` FIRST, then follow it; curate with `skill_manage`, prefer patch over edit.
  - Nudge can now also create/patch skills (`skill_manage` bound alongside `memory_manage`); it sees the current skills index to avoid duplicates.
- CLI banner shows skill count; `SKILLS_DIR` env override supported (default `./skills`).

### Verified

- 24 new unit tests in nm-memory-layer (CRUD, patch targeting, edit-keeps-frontmatter, traversal guards, index/content separation, tool dispatch); 6 new integration tests here (skill tools bound, index injection without body leakage, skill_manage/load_skill round-trip, nudge creating skills, nudge rejecting non-memory tools).

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
