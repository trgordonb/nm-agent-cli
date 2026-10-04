# Feasibility Study — Upgrading nm-memory-layer to RuVector + AgentDB

**Date:** 2026-10-04 · **Status:** Study only (no code changes) · **Verdict: feasible, staged adoption recommended — do not replace SQLite outright; the bottleneck for self-learning is the missing reward signal, not the store.**

---

## 1. Executive summary

The current memory layer (`nm-memory-layer` v0.1.1, 2,310 LOC, separate repo `~/projects/nm-memory-layer`) is a Hermes-style, local-first Python stack: SQLite/WAL + FTS5 episodic store, sqlite-vec (384-d bge-small via fastembed) hybrid retrieval with RRF k=60 fusion, agent-curated prompt memory, a 5-turn nudge curation loop, S3-backed skills, and a manually-ingested OKF wiki. Its known gaps map almost one-to-one onto what AgentDB advertises: no delete/TTL, no decay, no dedup machinery, **no feedback/reward signal**, single-user scoping.

[RuVector](https://github.com/ruvnet/ruvector) (Rust engine, MIT, 4.5k stars, active) and [AgentDB](https://github.com/ruvnet/agentdb) (TypeScript layer on the RuVector engine, MIT/Apache-2.0, pre-1.0) add exactly those mechanics: `recordFeedback()` → Thompson-Sampling bandit + InfoNCE/LoRA + EWC++ consolidation, Reflexion episodes, skill composition, causal graphs, TTL pruning, single-file `.rvf` cognitive container with a cryptographic witness chain, and BM25+dense hybrid retrieval that is architecturally the same design as our current FTS5+KNN+RRF.

**The integration problem is real:** there are **no Python bindings** for either project (PyPI: `ruvector` 404, `ruvector-core` 404; the PyPI package named `agentdb` is an unrelated "Team Dotagent" project — do not install it). AgentDB is npm-only (library + CLI + MCP server). This is a Python repo; the realistic bridges are (A) the **MCP server** the repo already knows how to load, or (B) a small **Node sidecar** behind the existing `SessionStore` facade. Both are viable; B is the one that actually upgrades the storage layer.

**Recommendation:** adopt in three gates — (1) a zero-code MCP pilot, (2) a sidecar with dual-write shadow + A/B retrieval eval, (3) cutover of episodic search + wiring of the feedback loop. Keep `nm-skills-registry`, prompt memory files, and the wiki vault as-is. Gate 2 must include a local durability test of the `.rvf` container and a local reproduction of their retrieval-quality claims before any cutover.

---

## 2. Current state (verified from code)

Memory layer = pinned git dep `nm-memory-layer` v0.1.1 (`pyproject.toml:24`), consumed by `main.py`/`server.py` here. Four tiers plus wiki:

| Tier | Implementation | Key facts |
|---|---|---|
| Episodic | `SessionStore` (`store.py`, 728 LOC) | SQLite WAL + FTS5 (`sessions.db`), hybrid FTS5 + sqlite-vec KNN fused by RRF k=60 (`store.py:269-406`), incremental 384-d bge-small embedding via watermark (`store.py:428-505`), optional OpenRouter condensation |
| Prompt memory | `PromptMemory` (`prompt_memory.py`) | `memories/MEMORY.md` + `USER.md`, hard 3,575-char budget, LLM-curated via `memory_manage` |
| Learning loop | `NudgePolicy` (`nudge.py`) | Every 5 turns an LLM reviews the transcript and may write memory/skills; nudge activity never archived |
| Procedural | `SkillLibrary` → `nm-skills-registry` | S3/R2-backed, per-user toggles — **separate package, out of scope for this upgrade** |
| Wiki | `WikiStore` (`wiki.py`) | OKF vault + prebuilt embeddings + typed KG (1-hop walk); ingest is deliberately manual |

**Scale today:** 945 message rows, 13 sessions, 935 vectors, 9.1 MB DB — migration volume is trivial.

**Verified gaps relevant to this study** (all in the package): no delete/TTL for the episodic archive, no decay/strength scoring, dedup is prompt-instructional only, no per-user scoping of sessions/prompt memory, and — central to the self-learning ambition — **nothing anywhere records a reward signal**: `session_search` hits are not tracked for use, skill outcomes are not scored, and the export-to-JSONL hook (`store.py:559-628`, "offline self-evolution substrate") has no consumer.

---

## 3. The target projects (verified from npm registry, GitHub API, and READMEs, 2026-10-04)

### 3.1 AgentDB — the cognitive layer

npm `agentdb`, MIT OR Apache-2.0, TypeScript. Three surfaces: **npm library** (`SelfLearningRvfBackend`, `AgentDB` classes), **CLI** (`npx agentdb`), **MCP server** (41 tools). Runs on Node ≥18 (repo has Node v24.13.0), browser WASM, and Docker.

- **Storage:** single-file `.rvf` "Cognitive Container" — vectors, indexes, learning state, metadata, SHAKE-256 witness chain; copy-on-write branching (`rvf derive`); legacy `.db` (SQLite) mode with a migration CLI. Four backends auto-selected: RuVector (Rust/NAPI) > RVF > HNSWLib > **sql.js (WASM, default, zero native deps)**; `better-sqlite3` optional.
- **Retrieval:** HNSW + **BM25/dense hybrid with RRF** — same fusion architecture as our current `SessionStore.search`. Metadata filtering, multi-query batch, MMR diversity rank, TTL+quality pruning (`agentdb_prune`).
- **Cognitive patterns:** episodic Reflexion (task/action/critique/outcome), skill library with bandit-composed chaining, causal edges + Cypher-like queries, hierarchical working/short/long memory, 9 RL algorithms, `agentdb_consolidate` (NightlyLearner pipeline).
- **Self-learning mechanics:** `recordFeedback(id, reward)` after every search; contrastive trainer (InfoNCE + hard negatives) updates a lightweight LoRA adapter (<1 ms); EWC++ guards against forgetting; bandit picks ranking/RL-algorithm/compression-tier arms.

### 3.2 RuVector — the engine

Rust monorepo (crates.io `ruvector-core`), npm `ruvector` (Node API `VectorDB`/`OnnxEmbedder`), WASM, plus `ruvector-server` (Axum REST) and `ruvector-postgres`. MIT. **Healthy:** 4,535 stars, pushed 2026-10-03 (yesterday), npm modified 2026-09-23. Memory-class map (working/episodic/semantic/procedural/causal/learning/auditable) matches AgentDB's; learning surfaces are SONA MicroLoRA + EWC++ + GNN rerank + Darwin optimization.

**Its own "known boundaries" matter more than its capability map** and several are disqualifying for direct engine use here: `ruvllm::AgenticMemory` has **no save/load** and its consolidation method **currently returns no changes**; agent-memory compaction is not wired into the default persistence path; GNN rerank/Darwin are "research surfaces, not automatic behavior in `VectorDB::search`"; replication is not production-grade; opening a persisted HNSW DB rebuilds the index by enumeration (irrelevant at 935 vectors, relevant at millions). Learning happens only from recorded outcomes — the docs are explicit that reads alone mutate nothing.

### 3.3 Maturity assessment

| Signal | agentdb | ruvector |
|---|---|---|
| GitHub stars | 89 | 4,535 |
| Last activity | **2026-07-30 (npm + git, ~2 months stale)** | 2026-10-03 (daily) |
| npm latest | **3.0.0-alpha.20** (dist-tag `latest` points at the alpha line) | 0.3.3 (pre-1.0) |
| Release churn | **119 releases in ~9 months**; docs show a mid-flight v2 `.db` → v3 `.rvf` format migration | Fast but versioned |
| Python bindings | none | none |
| License | MIT OR Apache-2.0 | MIT |
| Ecosystem | Single-maintainer suite (agentic-flow, ruflo consume it) | Same maintainer; broader community |

Vendor performance/quality claims (+36% search quality, recall 54%→90% over 500 feedback cycles, "150× faster than SQLite", GNN attention +12.4%) are **self-published benchmarks against weak baselines** (the 150× figure compares HNSW to a naive cosine loop, not to sqlite-vec). Treat as hypotheses to reproduce locally, not facts.

### 3.4 Name-collision warning (verified 2026-10-04)

There are **two unrelated projects both called "AgentDB"** in the same niche ("single-file embedded database for AI agents"):

1. **ruvnet/agentdb** — the one studied here: npm/TypeScript on the RuVector Rust engine, MIT, Oct 2025. This is the project with the Reflexion/skill/bandit/NightlyLearner self-learning stack.
2. **`datacules-agentdb`** (PyPI + crates.io, module name `agentdb`, GitHub `hvrcharon1/agentdb`, "Datacules LLC") — an independent Rust project with real PyO3 Python wheels (v0.5.0, July 2026; installs as `import agentdb`, compiled `_agentdb.*.so`). Unaffiliated with ruvnet, Unlicense, 2 GitHub stars, no mentions of ruvnet/ruvector in its README. Its API is SQL/vector-collections/FTS/hybrid/graph/workflows (`AgentDB.open(":memory:")`, `db.execute`, `db.vectors.collection(...).upsert/search`) — **no `store_episode`, no `record_feedback`, no learning loop**.

Search engines and AI answer engines fuse the two (AI-generated SEO pages like deepwiki/ayautomate/mcpmarket compound it). Web-search claims of "ruvector Python bindings" or "`datacules-agentdb` is AgentDB's Python package" are wrong: PyPI `ruvector` does not exist (404, re-verified 2026-10-04) and the RuVector workspace (197 crates) contains no PyO3/Maturin Python binding — the FFI crates (`ruvector-kge-ffi`, `ruvector-router-ffi`, `ruvector-typesafe-ffi`) are not Python.

---

## 4. Capability mapping: what would actually change

| Current (nm-memory-layer) | AgentDB/RuVector equivalent | Call |
|---|---|---|
| `SessionStore` episodic archive + FTS5+vec+RRF search | Pattern store + hierarchical memory + hybrid BM25/dense RRF + metadata filters | **Replace** (after shadow eval) — same architecture, adds feedback ranking, TTL prune, per-user metadata scoping |
| No delete/TTL/decay | `agentdb_prune` (TTL + quality), bandit arm decay, temporal-coherence crate | **Pure win** — closes verified gaps |
| No reward signal | `recordFeedback` + InfoNCE/LoRA + EWC++ + NightlyLearner | **Pure win** — but *we* must define the rewards (§6) |
| `NudgePolicy` LLM curation | `agentdb_reflexion_store`/`recall`, `critique_summary`, `success_strategies`, `agentdb_consolidate` | **Complement** — nudge becomes the writer of structured reflexion episodes; consolidation becomes a scheduled job |
| `SkillLibrary` / nm-skills-registry (S3) | `agentdb_skill_*` (in-container skill library) | **Keep the registry** (cross-repo, S3-backed, per-user). Optionally *mirror* the index into agentdb for bandit-composed skill chaining |
| `PromptMemory` (MEMORY.md/USER.md budget) | Hierarchical working/short/long tiers | **Keep files** — human-editable, git skip-worktree trick, prompt-cache-friendly; agentdb tiers add nothing for a 3.5 KB budget |
| `WikiStore` (OKF vault + typed KG) | Causal graph / Cypher | **Keep** — the vault's manual-ingest discipline is a feature; agentdb's graph is for agent-written causal edges between *experiences*, not curated docs |
| Compression + search summarizer (OpenRouter) | n/a | Unchanged (LLM-layer, orthogonal) |
| `sessions.db` (SQLite/WAL) | `.rvf` single file | File-level backup stays as simple as today (copy one file); COW branching is a bonus for A/B memory experiments |

---

## 5. Integration options for a Python consumer

| Option | Mechanism | Effort | Gets self-learning? | Notes |
|---|---|---|---|---|
| **A. MCP server only** | `npx agentdb mcp start` in `mcp_servers.json` (loader already exists: per-server transport/enabled/`keep_tools`, `${VAR}` interpolation, reload endpoint) | ~1 day | Indirect (agent-driven) | Zero package changes. 41 tools is surface bloat — restrict via `keep_tools` to reflexion + skill + pattern-search families. Does NOT replace programmatic recall (pre-flight `wiki_context`, prompt-memory injection stay in Python). Best as the pilot. |
| **B. Node sidecar + Python adapter** | ~200–400 LOC Fastify/Express service wrapping `SelfLearningRvfBackend`; thin Python client inside `nm_memory_layer` behind the `SessionStore`/`search()` facade; supervised by `start.sh` | ~1–2 weeks | **Yes, fully** — `record_turn`→insert, `search`→hybrid query, nudge→reflexion + `recordFeedback`, cron→`consolidate` | The real upgrade path. Node v24 present. IPC latency (~1–5 ms local HTTP) is irrelevant vs LLM calls. Keep fastembed in Python, pass 384-d `Float32Array` vectors over the bridge (bge-small dims = MiniLM dims = 384, so nothing to re-embed). |
| **C. ruvector-server (Rust REST)** | Axum sidecar compiled from `crates/ruvector-server` | High | **No** — vector CRUD/search only; all cognitive/learning surfaces live in the TS layer; auth still "planned" | Also: no Rust toolchain on this box. Dominated by B. |
| **D. Status quo + targeted patches** | Add TTL/decay/dedup + a feedback table in SQLite inside `nm-memory-layer` | ~1 week | Mechanically, but hand-rolled | The honest fallback if AgentDB's maturity gates fail; keeps zero new runtimes. |

Not viable: PyO3 bindings (ruvnet publishes none; writing our own contradicts the point), the PyPI `agentdb` package (unrelated project), subprocess-per-call CLI usage (no persistent learning state, process spawn per query).

---

## 6. The self-learning future: what actually has to be built

AgentDB supplies the learning *machinery*; the missing piece here is the **signal**. Today nothing observes whether a recalled memory or a skill succeeded. Required design work (mostly in this repo + nudge, not in the DB):

1. **Implicit retrieval feedback (cheap, automatic):** log which `session_search`/pattern hits were cited or followed by tool calls in the turn → `recordFeedback(hit_id, 1.0/0.2)` post-turn. Zero LLM cost.
2. **Reflexion episodes from the nudge loop (natural fit):** the nudge already reviews each transcript with memory/skill tools bound. Extend its output contract to also write a Reflexion episode (task → approach → outcome → critique) and, on error-recovery episodes, a causal edge. The nudge's "silence is valid" rule becomes an episode with zero reward — exactly what the bandit needs to learn what *not* to store.
3. **Skill outcome rewards:** skill-manage already tracks create/patch/enable events; add an outcome stamp (worked/failed/partial) at nudge time → feeds bandit-based skill composition.
4. **Consolidation as a scheduled job:** NightlyLearner (`agentdb_consolidate`) on a cron — this repo already runs scheduled work comfortably.
5. **Eval harness:** the A/B `retrievers` field on `SessionSearchHit` (lexical vs embedding attribution) is already in place — extend it to compare current RRF ranking vs agentdb feedback-trained ranking on real sessions. The 935-vector corpus is too small for the +36% claim to matter yet; design the eval so it scales.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Maturity: alpha-as-latest, 119 releases in 9 months, 2 months stale, 89 stars, format migration (v2 `.db` → v3 `.rvf`) mid-flight** | High | Pin exact npm versions; wrap everything behind the `SessionStore` facade so the backend is swappable; keep the SQLite path shippable (dual-write during eval); keep JSONL as the re-import substrate (export already exists, `agentdb_import` accepts JSON) |
| Durability of the default sql.js (WASM) backend — in-memory with file persistence; flush semantics on crash unverified | High | Gate 2 requires a kill -9 durability test; force the `better-sqlite3` native backend (Node 24, one optional dep) or RuVector NAPI backend; document `.rvf` backup cadence |
| New runtime dependency (Node) in a pure-Python deploy | Medium | Sidecar is optional at runtime (fall back to SQLite when absent — same graceful-degradation pattern the repo already uses for wiki-hybrid/fastembed); health-report it in `/api/health` |
| Vendor benchmarks don't reproduce locally | Medium | Reproduce `npm run bench` + our own A/B retrieval eval before cutover; no cutover on unverified numbers |
| Single-maintainer ecosystem | Medium | MIT license + JSONL portability + swappable facade = exit cost is low; timebox the bet |
| 41-tool MCP surface bloat / tool-call misfire | Low | `keep_tools` allowlist in `mcp_servers.json` |
| HNSW cold-start rebuild (ruvector known boundary) | None today | 935 vectors; revisit at ~1M |

---

## 8. Recommended plan (three gates)

**Gate 1 — MCP pilot (≈1 day, zero package changes).** Add `agentdb` to `mcp_servers.json` with `keep_tools` restricted to `agentdb_reflexion_*`, `agentdb_pattern_search`, `agentdb_skill_*`, `agentdb_consolidate`, `agentdb_prune`. Run real sessions for a week; observe whether the agent actually uses cognitive-memory tools and whether reflexion episodes capture what the nudge already captures. Cheap signal on UX fit.

**Gate 2 — Sidecar shadow (≈1–2 weeks).** Build the Node sidecar + Python adapter; dual-write every `record_turn`; run `SessionStore.search` and agentdb search side-by-side on live queries; log both hit sets (reuse the `retrievers` attribution field). Verify: `.rvf` durability under kill -9, Node-process supervision/restart, benchmark reproduction. **Exit criteria:** retrieval quality ≥ current hybrid on our corpus, durability test passed, sidecar survives 48 h of normal use.

**Gate 3 — Cutover + learning loop (≈2–4 weeks of iteration).** Swap episodic search to agentdb; wire post-turn `recordFeedback` from hit-usage logs; extend the nudge to write reflexion episodes + outcome stamps; nightly `consolidate` cron; add TTL pruning (replacing the "no delete" gap). Keep `sessions.db` as an append-only audit/archive (or retire it by re-export). Skills registry, prompt memory, wiki untouched.

Fallback at any gate: Option D patches to SQLite — all gates are reversible by design.

---

## 9. Open questions to resolve in Gate 1/2

1. sql.js flush/fsync semantics and whether `better-sqlite3` or the RuVector NAPI backend can be forced cleanly on Node 24.
2. Does the v3 `.rvf` format have a stable spec/docs, or is it still moving? (119 releases suggests the latter.)
3. Actual latency of `recordFeedback` + learning tick on our hardware (claimed <1 ms; verify).
4. Multi-tenancy: current episodic store is single-user; agentdb metadata filters + namespaces look sufficient but need a schema decision (`user` metadata field vs separate collections) *before* migration, not after.
5. MCP tool reliability of `npx agentdb` (npm fetch at every boot vs pinned local install — ruvector's own docs warn against `@latest`-per-invocation hooks; same caution applies).
