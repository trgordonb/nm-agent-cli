# Gate 1 Implementation Plan — AgentDB MCP Pilot

**Date:** 2026-10-04 · **Context:** Gate 1 of `RUVECTOR_AGENTDB_FEASIBILITY.md` · **Scope:** config + install only — **zero changes** to `main.py`, `nm-memory-layer`, or the system prompt.

**Goal in one sentence:** put AgentDB's cognitive-memory tools (Reflexion episodes, skill library, ReasoningBank patterns, reward/learning loop) in front of the running agent through the existing `mcp_servers.json` loader, run normal work for 1–2 weeks, and measure whether the agent actually uses them and whether they capture anything the nudge loop misses — before committing to the Gate-2 sidecar.

---

## 1. Verified facts (live smoke test on this box, 2026-10-04)

Everything below was verified by installing `agentdb@3.0.0-alpha.20` locally and speaking stdio JSON-RPC to `agentdb mcp start` — not taken from the README. Several README claims are wrong for this alpha; the plan is built on the verified numbers.

| # | Fact | Evidence |
|---|---|---|
| 1 | MCP server is stdio, starts clean, shuts down clean | initialize → notifications/initialized → tools/list → tools/call all worked; stderr shows clean "Shutting down AgentDB MCP Server" |
| 2 | **35 tools, not 41**; names are mixed: 12 `agentdb_*` + 23 bare (`reflexion_store`, `skill_create`, `learning_*`, `causal_*`, …) | `tools/list` output, full list in Appendix A |
| 3 | Tool names reach the agent **un-prefixed** | `langchain-mcp-adapters` 0.3.2 `MultiServerMCPClient(tool_name_prefix=False)` default (`client.py:61`); server name in config does not appear in tool names |
| 4 | The MCP server honors `AGENTDB_PATH` (default `./agentdb.db`); **the CLI ignores it** (always `./agentdb.db`) | `agentdb-mcp-server.js:197` vs live `agentdb status` with the var set |
| 5 | On this box the store is the **v2.0.0 SQLite layout** (not the v3 `.rvf` container from the marketing), backend **ruvector-WASM**, embeddings **Xenova/all-MiniLM-L6-v2** (384-d) via transformers.js, durable layer **native better-sqlite3** | `agentdb init` + `agentdb status` output |
| 6 | This npm config blocks postinstall scripts; agentdb still works — prebuilt `better-sqlite3` binary loads, vector/attention engines fall back to WASM | npm `allow-scripts` warnings + working round-trip |
| 7 | **Fresh-store schema bootstrap is flaky**: startup `initializeSchema` does not reliably create tables; the `agentdb_init` MCP tool itself has a SQL bug (`no such column: "table"`) but *partially* creates the schema (file grew, `episodes` table came into existence) | live tools/call sequence: `reflexion_store` on fresh store → `no such table: episodes`; after `agentdb_init` → `NOT NULL constraint failed: episodes.session_id` (table exists, args wrong) |
| 8 | **Tool arg schemas differ from the docs** (`session_id` not `sessionId`, `task` not `query`; `agentdb_pattern_store` requires `taskType`/`approach`/`successRate`) | `tools/list` inputSchemas, Appendix A. Not a pilot-blocker: the LLM sees the real schemas at runtime |
| 9 | Install is **~1 GB node_modules** (onnxruntime, sql.js, ruvector packages, MCP SDK…) and took ~2 min on this box | `du -sh node_modules` in smoke dir |
| 10 | Upstream is dormant: alpha.20 published 2026-07-30, no release since | npm registry `time.modified` |

Environment: Node v24.13.0, linux x64 glibc, no Rust toolchain (irrelevant for this gate).

---

## 2. Install: pinned local vendor dir (not `npx @latest`)

The loader (`main.py:187-222`) has **no connect timeout** — a slow stdio spawn blocks runtime assembly on every session. `npx -y agentdb@…` risks a multi-minute cold resolve on first boot after a cache clear. RuVector's own security note says the same: pin locally, never fetch `@latest` per invocation.

```bash
mkdir -p vendor/agentdb && cd vendor/agentdb
npm init -y >/dev/null
npm install --save-exact agentdb@3.0.0-alpha.20 --no-audit --no-fund
# ~1 GB in vendor/agentdb/node_modules — verify the CLI runs:
./node_modules/.bin/agentdb --version     # → agentdb v3.0.0-alpha.20
```

- Commit only `vendor/agentdb/package.json` (+ package-lock.json); **gitignore `vendor/agentdb/node_modules/`** (add to `.gitignore`; `state/` is already ignored, line 46). Document `npm ci --prefix vendor/agentdb` as the restore step.
- `package.json` explicitly records `"agentdb": "3.0.0-alpha.20"` — the pin survives cache clears and machine moves.
- Note the npm scripts policy on this box (postinstall blocked): keep it blocked. Verified working in that mode (fact #6). If a future re-pin ever needs scripts (`npm approve-scripts`), re-run the §5 checklist after.

**Data directory** (before enabling):

```bash
mkdir -p state/agentdb     # gitignored; backup = copy the single .db file
```

---

## 3. Config: exact `mcp_servers.json` entry

Add one server. Schema verified against `mcp_config.py` (`transport` ∈ allowed set, `env` values `${VAR}`-interpolated, `keep_tools` matched on exact name or `_<tool>` suffix of the *bound* name — which per fact #3 is the raw MCP name).

```json
"agentdb": {
  "transport": "stdio",
  "command": "./vendor/agentdb/node_modules/.bin/agentdb",
  "args": ["mcp", "start"],
  "env": {
    "AGENTDB_PATH": "state/agentdb/agentdb.db"
  },
  "keep_tools": [
    "agentdb_init",
    "agentdb_stats",
    "agentdb_pattern_store",
    "agentdb_pattern_search",
    "reflexion_store",
    "reflexion_retrieve",
    "skill_create",
    "skill_search",
    "reward_signal",
    "learning_feedback",
    "learning_start_session",
    "learning_end_session",
    "learning_metrics",
    "consolidate_now"
  ],
  "enabled": true,
  "description": "AgentDB pilot (alpha.20, pinned vendor install): Reflexion episodes + skill library + ReasoningBank + learning loop; SQLite store at state/agentdb (Gate 1 of RUVECTOR_AGENTDB_FEASIBILITY.md)"
}
```

Notes on the entry:

- `command` is relative to the process cwd — valid because both entry points run from the repo root (`start.sh`, `uv run python main.py`, `uv run python server.py`). Same assumption `npx @luxalgo/mcp` already makes.
- `AGENTDB_PATH` is read by the MCP server (fact #4) and lands the store in gitignored `state/agentdb/`. Do not rely on the CLI-side path behavior; all bootstrap in §5 goes through the MCP surface.
- The name `agentdb` is only a config key (report rows, toggles); it does not prefix tool names (fact #3).

### Tool allowlist rationale — 14 kept of 35

| Kept | Why |
|---|---|
| `agentdb_init` | Idempotent bootstrap (`CREATE TABLE IF NOT EXISTS`); required per fact #7 |
| `agentdb_stats` | The pilot's observability surface (episode/skill/pattern/learning counters) |
| `agentdb_pattern_store` / `agentdb_pattern_search` | ReasoningBank write/read — the "what approach worked for this kind of task" memory |
| `reflexion_store` / `reflexion_retrieve` | Episodic Reflexion (task/reward/success/critique) — the direct comparable to the nudge's outputs |
| `skill_create` / `skill_search` | In-container procedural memory; **deliberately separate** from `nm-skills-registry` (S3) — pilot does not touch that package |
| `reward_signal` | Rich reward shaping (success, efficiency, quality, latency) — seeds the feedback-signal design question for Gate 2 |
| `learning_feedback` | Per-state/action RL feedback within a learning session |
| `learning_start_session` / `learning_end_session` | `learning_feedback` requires an open session; without these the loop tools are dead weight |
| `learning_metrics` | Read-only learning telemetry |
| `consolidate_now` | Manual trigger of the consolidation pipeline — the NightlyLearner preview |

Excluded (21): **destructive** — `agentdb_delete`, `agentdb_delete_batch`, `agentdb_clear_cache` (the agent must not be able to erase memory in a pilot); **bulk/dupes** — `agentdb_insert`, `agentdb_insert_batch`, `agentdb_pattern_store_batch`, `reflexion_store_batch`, `db_stats` (overlaps `agentdb_stats`), `experience_record` (overlaps `reflexion_store`); **experimental/unproven** — `causal_add_edge`, `causal_query`, `causal_traverse`, `recall_with_certificate`, `learning_train`, `learning_transfer`, `learner_discover`, `learning_predict`, `learning_explain` (keep the surface tight; add back only if the pilot shows a need).

---

## 4. Enabling and applying

1. Install vendor dir + create `state/agentdb/` (§2).
2. Add the JSON entry (§3) with `"enabled": true`.
3. **CLI sessions:** nothing else — `_load_mcp_tools()` runs at `assemble_agent_runtime()` per session; the CLI banner/report will show the server row.
4. **Web server:** the running process needs `POST /api/mcp/reload` (409s while turns stream), or restart via `start.sh`. The frontend gear → Settings → MCP will show the toggle like any other server.
5. Sanity row in the report: `mcp_report` should show `agentdb / connected=true / tool_count=14`. `tool_count≠14` means `keep_tools` drifted from the actual tool list (fact #2 says upstream renames tools between alphas — re-check Appendix A after any re-pin).

---

## 5. Bootstrap & verification checklist (run once, immediately after enabling)

Fresh stores are flaky (fact #7), so bootstrap is an explicit procedure, done **through the MCP surface with the same env the server gets**. Easiest form: paste the initialize/tools/call lines into `./vendor/agentdb/node_modules/.bin/agentdb mcp start` (or run the equivalent from the first CLI session by asking the agent to call the tools). In order:

1. `agentdb_init` `{}` → **expect an error mentioning `"table"`** (the known upstream SQL bug). This is acceptable if and only if step 2 passes — the tool partially creates the schema before failing.
2. `agentdb_stats` `{}` → **must succeed with zero counters** (episodes/skills/patterns/edges all 0). If it errors with `no such table`, re-run `agentdb_init` once; if still broken, **abort the pilot** (bootstrap is a Gate-2 viability signal, not just a nuisance).
3. `reflexion_store` `{"session_id": "gate1-bootstrap", "task": "agentdb pilot bootstrap", "reward": 1, "success": true, "critique": "schema verified"}` → must succeed (this also proves the write path + embedder).
4. `reflexion_retrieve` `{"task": "pilot bootstrap", "k": 3}` → must return the stored episode. If it errors on the embedder, note the error — transformers.js WASM worked in the smoke test, so failure here means environment drift since the smoke test.
5. `agentdb_stats` again → episodes ≥ 1.
6. Confirm the file exists and is non-trivial: `ls -la state/agentdb/agentdb.db`; snapshot it: `cp state/agentdb/agentdb.db state/agentdb/agentdb.bootstrap-snapshot.db`.

Also record at enable time: session start latency before/after (time `uv run python main.py --help`-equivalent boot with the server enabled vs disabled) — the vendor-local binary booted in ~1–3 s in the smoke test, but measure.

**Rollback at any point:** set `"enabled": false` (web UI gear or edit) + `POST /api/mcp/reload`, or just close the CLI session. No code residue, no package changes; `state/agentdb/` is disposable.

---

## 6. Pilot protocol (1–2 weeks of normal use)

**Do:** run the agent's normal workload — financial research sessions, wiki work, coding tasks, web UI chats — at least ~15 sessions mixing CLI and `/api/chat`. Nothing about prompts or the nudge changes; the measurement is whether the agent reaches for the new tools on its own and what it writes.

**Don't:** tune prompts to encourage usage, pre-write episodes, or run synthetic "please store a reflexion" sessions — that invalidates the spontaneity signal. (Exception: the one bootstrap episode from §5, tagged `gate1-bootstrap`.)

### Metrics and where they come from

| Metric | Source | How |
|---|---|---|
| Spontaneous usage rate | `sessions.db` (tool calls are already archived verbatim) | `sqlite3 sessions.db "SELECT tool_name, COUNT(*) FROM sessions WHERE role='tool' AND tool_name IN ('reflexion_store','reflexion_retrieve','skill_create','skill_search','agentdb_pattern_store','agentdb_pattern_search','reward_signal','learning_feedback','consolidate_now') GROUP BY tool_name;"` — per-session via `session_id`. Nudge activity is never archived, so these counts are purely main-agent, user-visible turns |
| Tool error rate | same rows, content matching `Error`/`isError` markers; plus `agent.log` | Any tool erroring >20% of calls → drop it from `keep_tools` (config-only change) and note it for Gate 2 |
| Episode quality vs nudge | manual read | After sessions where the agent stored episodes, compare against what the nudge wrote to `memories/MEMORY.md`/skills in the same period: does `reflexion_store` capture anything the nudge misses (e.g., outcome+critique structure, failure episodes)? Does it duplicate? |
| Learning-loop coherence | `learning_metrics`, `agentdb_stats` trends | Are reward sessions being opened/closed, or do `learning_feedback` calls fail for want of a session? |
| Retrieval usefulness | manual | When `reflexion_retrieve`/`skill_search`/`agentdb_pattern_search` fire, does the returned context change the turn's behavior? (Read the surrounding transcript rows.) |
| Stability | `agent.log`, `mcp_report` | Server connect failures, unclean shutdowns, boot-time drift |
| Store growth | `ls -la state/agentdb/` | Growth rate informs Gate-2 capacity/backups |

### Escalation ladder — only if usage is exactly zero after ~10 genuine sessions

1. **Config-only nudge:** nothing config-only exists to fix spontaneity — that's the point. Record the finding; it is itself the Gate-1 answer ("tools alone don't drive adoption").
2. **Micro-change A (needs sign-off, breaks zero-code):** one sentence in `build_agent`'s system prompt (`main.py:281-318`) noting the experimental cognitive-memory tools exist. Re-measure 5 sessions.
3. **Micro-change B (needs sign-off):** bind `reflexion_store` + `skill_create` into the nudge's tool set (`main.py:479-514` binds only `memory_manage`/`skill_manage` today) so the nudge itself writes structured episodes. This previews the Gate-3 wiring and is the single highest-value change if A also fails.

---

## 7. Decision gate → Gate 2

**Proceed to the Gate-2 sidecar build if:** ≥3 spontaneous episodes/stored patterns across the pilot with ≥1 judged useful (changed a turn) and not duplicating the nudge; tool error rate <20%; boot overhead tolerable (<5 s); no stability incidents; `nm-skills-registry` untouched and unaffected.

**Abort / choose feasibility-option D (SQLite patches) if:** zero usage even after escalations A+B, or bootstrap cannot be made reliable, or the alpha proves too buggy in daily use.

**Re-check before Gate 2 regardless of outcome:** upstream release status (alpha.20 is 2+ months stale — if a v3 stable or new alpha landed, re-pin, re-run Appendix A name capture + the §5 checklist, since tool names/args changed between alphas before), and whether the v3 `.rvf` container path has replaced the v2 SQLite store under the MCP server (it had not as of alpha.20 — fact #5).

---

## 8. Risks specific to this gate

| Risk | Handling |
|---|---|
| Schema bootstrap flakiness (verified bug #7) | §5 explicit checklist; abort-if-unfixable is a legitimate pilot outcome |
| Tool-name/arg drift between alphas | Exact version pin + `keep_tools` + tool_count sanity check; schemas live in `tools/list`, so the agent always sees truth even when docs lie |
| Agent confusion / tool spam (35→14 kept, but still novel) | Tight allowlist, destructive tools excluded; usage metrics will show it |
| 1 GB vendor footprint | Committed `package.json` only; node_modules gitignored; `npm ci` documented |
| Store not covered by any backup regime | `state/agentdb/` is disposable pilot data; bootstrap snapshot (§5.6) is the only safety net needed until Gate 2 |
| Upstream wake-up mid-pilot with breaking changes | Pin holds; do not re-pin mid-pilot — note the release and re-verify at the decision gate |

---

## Appendix A — verified tool inventory (alpha.20, `tools/list` 2026-10-04)

35 tools: `agentdb_clear_cache`, `agentdb_delete`, `agentdb_delete_batch`, `agentdb_init`, `agentdb_insert`, `agentdb_insert_batch`, `agentdb_pattern_search`, `agentdb_pattern_stats`, `agentdb_pattern_store`, `agentdb_pattern_store_batch`, `agentdb_search`, `agentdb_stats`, `causal_add_edge`, `causal_query`, `causal_traverse`, `consolidate_now`, `db_stats`, `experience_record`, `learner_discover`, `learning_end_session`, `learning_explain`, `learning_feedback`, `learning_metrics`, `learning_predict`, `learning_start_session`, `learning_train`, `learning_transfer`, `recall_with_certificate`, `reflexion_retrieve`, `reflexion_store`, `reflexion_store_batch`, `reward_signal`, `skill_create`, `skill_create_batch`, `skill_search`.

Pilot allowlist schemas (required / properties, from `inputSchema`):

```
agentdb_init:            req=[]                    props=[db_path, reset]
agentdb_stats:           req=[]                    props=[detailed]
agentdb_pattern_store:   req=[taskType, approach, successRate]  props=[…, tags, metadata]
agentdb_pattern_search:  req=[task]                props=[task, k, threshold, filters]
reflexion_store:         req=[session_id, task, reward, success]  props=[…, critique, input, output, latency_ms, tokens]
reflexion_retrieve:      req=[task]                props=[task, k, only_failures, only_successes, min_reward]
skill_create:            req=[name, description]   props=[code, success_rate]
skill_search:            req=[task]                props=[task, k, min_success_rate]
reward_signal:           req=[success]             props=[episode_id, target_achieved, efficiency_score, quality_score, time_taken_ms, expected_time_ms, include_causal, reward_function]
learning_feedback:       req=[session_id, state, action, reward, success]  props=[next_state]
learning_start_session:  req=[user_id, session_type, config]
learning_end_session:    req=[session_id]
learning_metrics:        req=[]                    props=[session_id, time_window_days, include_trends, group_by]
consolidate_now:         req=[]                    props=[session_id]
```

## Appendix B — smoke-test transcript method (reusable for re-pins)

```bash
cd vendor/agentdb
printf '%s\n%s\n%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
 | AGENTDB_PATH=/tmp/smoke.db ./node_modules/.bin/agentdb mcp start 2>/dev/null \
 | python3 -c "import json,sys; [print(t['name']) for m in map(json.loads,sys.stdin) if m.get('id')==2 for t in m['result']['tools']]"
```

Then repeat the §5 sequence with `tools/call` lines. Any drift in names/schemas → update `keep_tools` and Appendix A before enabling.

## Appendix C — enablement log (2026-10-04, branch `ruvector`)

Steps §1–§5 executed. Nothing in `nm-memory-layer` or `nm-skills-registry` was touched.

| Plan step | Outcome |
|---|---|
| §2 vendor install | `vendor/agentdb` @ `agentdb@3.0.0-alpha.20` exact-pinned (`package.json` + `package-lock.json` committed, `node_modules/` gitignored, ~1 GB on disk). npm postinstall scripts blocked by this box's `allow-scripts` policy — the smoke-test-verified working mode. CLI confirms `agentdb v3.0.0-alpha.20`. |
| §3 config | `mcp_servers.json` `agentdb` entry added exactly as written in §3 (`enabled: true`), JSON validated. |
| §4 loader verification | Ran the real path (`mcp_config.load_mcp_servers` → `MultiServerMCPClient` → `apply_keep_tools`) with the repo venv: config parses, env interpolated, **35 raw tools → exactly the 14 planned tools bound**, names matching Appendix A. `agent_browser` binds alongside with no name collisions. |
| §5.1 `agentdb_init` | Server boot logged `✅ Database schema initialized` — the smoke test's init flakiness (fact #7) did **not** reproduce on this boot; schema came up clean. |
| §5.2 `agentdb_stats` | Succeeded; counters visible (0 episodes pre-write, exactly 1 after — so the write was the only one). |
| §5.3 `reflexion_store` | Bootstrap episode stored (`gate1-bootstrap`), with embedding. |
| §5.4 `reflexion_retrieve` | **Semantic recall verified**: returned the bootstrap episode at similarity 0.746. First embed downloaded the MiniLM model (~89 MB) into `node_modules/@huggingface/transformers/.cache` (under gitignore; a fresh `npm ci` re-downloads on first embed). |
| §5.5 stats re-check | Episodes: 1 ≥ 1 ✓ |
| §5.6 snapshot | `state/agentdb/agentdb.bootstrap-snapshot.db` (152 KB) taken; main store `agentdb.db` 152 KB. |
| §5 latency | **0.40 s** for spawn + initialize + tools/list (vendor-local binary; gate was <5 s). |

**Operational notes discovered during enablement:**

1. When driven by a naive `printf | server` handshake, the standalone server does **not** exit on stdin EOF after processing (the wrapper shim keeps the pipe alive). The langchain loader's session close shuts it down cleanly (observed in the §4 run), so this is a test-harness artifact, not a pilot blocker — but the Gate-2 sidecar must use a proper client close, not EOF-and-hope.
2. `tools/list` reports 35 tools while the server's own banner advertises "32 tools available" — the banner miscounts; `tools/list` (what actually binds) is authoritative.
3. Shell-level `pkill -f <pattern>` self-matches the invoking shell's own argv — bracket-trick patterns (`agentdb[-]mcp-server`) when cleaning up stray servers by hand.
