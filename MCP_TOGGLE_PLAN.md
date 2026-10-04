# MCP Toggle Plan — config-file-driven MCP servers with enable/disable (Hermes-style)

Status: **implemented 2026-10-04**
Sibling effort to the skills registry (`SKILLS_REGISTRY_PLAN.md`, implemented). Same UX contract — list, toggle, "applies to new sessions" — but a different storage model, because MCP servers are **machine-local configuration**, not content.

## Outcome (2026-10-04)

Shipped as planned (`mcp_config.py` + `mcp_servers.json`, `_load_mcp_tools` per-server resilience, `GET/POST /api/mcp*` with the reload 409 guard, gear-driven settings view hosting Skills | MCP). First two servers: `agent_browser` (enabled — identical tool set to the previous hardcoded binding) and `finance_toolkit` (the formerly commented-out block, disabled). Third server added same-day: **luxalgo** (`npx -y @luxalgo/mcp`, keyless) filtered to 9 `library_*` + 4 `trackers_*` tools via `keep_tools` — which required fixing the filter to suffix-matching for multi-word tool names (regression-tested). Live verification: reload bound 29 + 13 tools; LangSmith trace `01a10685` shows the agent using `library_search`/`library_get_concept`/`library_get_indicator` in a real turn, including a graceful structured-error recovery.

## 1. Goals and non-goals

**Goals**

1. The set of MCP servers moves from hardcoded Python (`main.py:212-231` + the commented-out Finance Toolkit block, `main.py:202-209`) into a **local, git-tracked JSON file** — the list mechanism the user asked for.
2. Per-server **enable/disable** with the same surfaces as skills: REST endpoints + a React **MCP tab**. Toggling `finance_toolkit` on replaces the commented-out block for good.
3. Toggles apply at the next runtime assembly — with an explicit **reload** so a long-running server doesn't need a restart.

**Non-goals**

- **No S3/registry** for MCP config: a stdio `command` (e.g. `agent-browser`) is meaningless off this machine, so bucket-authoritative config buys nothing. The JSON is the single source of truth, diffable in git.
- **No LLM-facing toggle tool** — a deliberate divergence from skills. `skill_manage(enable|disable)` exists because agent curation of skills is the point; MCP servers are infrastructure the *user* controls. The agent can still *use* enabled servers' tools as before.
- No changes to `nm-memory-layer` (MCP wiring is consumer-side), and no hot-swapping of tools mid-turn.

## 2. Config file: `mcp_servers.json` (repo root)

```json
{
  "version": 1,
  "servers": {
    "agent_browser": {
      "transport": "stdio",
      "command": "agent-browser",
      "args": ["mcp", "--tools", "core"],
      "env": {"AGENT_BROWSER_SESSION": "nm-agent"},
      "enabled": true,
      "description": "Local Chrome automation (Rust CLI, core tool profile)"
    },
    "finance_toolkit": {
      "transport": "streamable_http",
      "url": "https://financetoolkit.jeroenbouma.com/mcp",
      "headers": {"Authorization": "Bearer ${FMP_API_KEY}"},
      "keep_tools": ["breadth", "discovery", "market_data", "models", "momentum",
                     "overlap", "rates", "risk", "volatility", "search_categories",
                     "search_by_category", "search_metrics", "search_instruments"],
      "enabled": false,
      "description": "FinanceToolkit analytics (FMP-backed; dormant since 2026-09)"
    }
  }
}
```

Design points:

- **Dict keyed by server name** — passes through to `MultiServerMCPClient`'s servers dict shape; the name prefixes tool names (`agent_browser_…`) exactly as today.
- **Transport whitelist**: `stdio`, `streamable_http`, `sse` (everything `MultiServerMCPClient` handles); anything else fails at load with a per-server error, not a crash.
- **`${VAR}` interpolation** in `command`/`args`/`env`/`url`/`headers` from `os.environ` at load time. Unresolved placeholder → that server is skipped with a warning (**fail-closed**), never a crash and never a leaked literal. This is what keeps the file git-tracked while `headers` carries the FMP key: only the *name* `FMP_API_KEY` is committed; the value stays in `.env`.
- **`keep_tools`** (optional, per server) — replaces the global `_MCP_KEEP_TOOLS`, which was always finance-specific. Absent = bind all tools (agent_browser's case today).
- **`enabled`** lives in the same file (single source of truth). Unlike skills — whose toggle state went to S3 — this is machine-local infra config; git diff is the audit log. Writes are atomic (`.tmp` + `os.replace`, the `wiki_engine/runtime.py` pattern).
- Path override `MCP_SERVERS_FILE` env (tests), default `./mcp_servers.json`.

## 3. Loader: new `mcp_config.py` (repo root)

```python
load_mcp_servers(path) -> tuple[dict[str, dict], list[ServerStatus]]
# resolved servers ready for MultiServerMCPClient (enabled only, interpolated),
# plus per-server status: {name, enabled, connected?, tool_count?, error?}
set_server_enabled(path, name, enabled) -> str   # atomic rewrite, status message
```

- Validates schema (pydantic, already a dep) and interpolation; **disabled and errored servers never enter the client dict** — `_load_mcp_tools` connects only what's enabled, keeping today's per-server resilience (one bad server = warning + continue).
- `main.py` rewiring: `_load_mcp_tools()` iterates `load_mcp_servers()` and aggregates per-server tool lists (report stashed into the runtime dict as `mcp_report`); the hardcoded dict, the dormant block, `_FINANCETOOLKIT_URL`, and `_MCP_KEEP_TOOLS` are deleted. `_AGENT_BROWSER_SESSION` moves into the JSON's `env`.

## 4. Toggle semantics ("applies when?")

- **CLI agent**: runtime assembles per session — a toggle applies at the **next session**, identical to skills.
- **FastAPI server**: `_runtime` assembles once per process (`server.py:64-70`), so without help a toggle would need a restart. Add **`POST /api/mcp/reload`**: under `_runtime_lock`, reject with 409 while `ACTIVE_TURNS` is non-empty (in-flight turns keep their own graph reference and finish safely), else drop `_runtime` → the next chat re-assembles with the new server set. Caveat noted in code: the old runtime's stdio child processes are reclaimed by GC/process exit.
- UI copy mirrors the skills tab: *"applies after reload (server) or the next session (CLI)"*.

## 5. API surface (mirrors skills)

| Endpoint | Behavior |
|---|---|
| `GET /api/mcp` | Per-server: name, description, transport, enabled, plus last-assembly status (`connected`, `tool_count`, `error`) from `_runtime["mcp_report"]`; `assembled: false` → status "pending" |
| `POST /api/mcp/{name}/enabled` `{enabled}` | Atomic JSON rewrite; 404 unknown name; returns status message |
| `POST /api/mcp/reload` | 409 while turns are active; else re-arms assembly, returns new tool counts |

`/api/health` keeps reporting `mcp_tools` (bound tool count) — unchanged shape.

## 6. React: gear-driven settings view (per user decision 2026-10-04)

No fourth tabbar tab. The **sidebar footer** (model-name row) gains a gear icon button, right-aligned; it opens a **settings view** in the content area with an internal `Skills | MCP` switcher (same `.tab` styling). The sidebar stays visible on the settings view so the gear remains present; its `active` state tracks the open view. The tabbar keeps `Chat | Wiki` — Skills moves out of the tabbar into the settings view (its component is unchanged, only its entry point moves).

## 7. Migration & cutover (zero behavior change on day 1)

1. Write `mcp_servers.json` exactly as §2 (agent_browser enabled — byte-equal behavior; finance_toolkit disabled — the current commented state).
2. Rewire `main.py` to the loader; run the parity check: bound tool-name set for `agent_browser` identical before/after.
3. Delete the hardcoded dict + dormant block from `main.py`.
4. REST + reload; React tab.
5. Optional exercise: flip `finance_toolkit` on with a bogus `${FMP_API_KEY}` → fail-closed warning, agent_browser unaffected.

## 8. Testing

- Unit (`mcp_config`): parse, `${VAR}` interpolation + fail-closed, transport whitelist, `keep_tools` filter, atomic write roundtrip, unknown-name toggle.
- Wiring (`tests/test_main_integration.py` style): with `MCP_SERVERS_FILE` pointed at a temp config — broken command → skipped with warning, others bound; disabled server → zero tools; tool-name parity vs today for agent_browser.
- Server tests: GET/POST roundtrip rewrites the file; reload 409 while `ACTIVE_TURNS` non-empty; reload then assemble picks up the change.
- Browser pass of the MCP tab (same discipline as Skills).

## 9. Risks

| Risk | Mitigation |
|---|---|
| Secrets leaking via committed JSON | `${VAR}` indirection only; fail-closed on unresolved; grep CI check for `Bearer ` literals |
| Reload races an in-flight turn | 409 guard on `ACTIVE_TURNS`; in-flight turns keep their graph reference |
| Duplicate stdio children after reload | Old runtime GC'd; documented caveat, dev-scale |
| Agent-browser MCP down at assembly | Per-server try/except → warning + report row (today's behavior, generalized) |

## 10. Open decisions (recommendations included)

1. **File location** — repo root `mcp_servers.json` (recommended, matches `.env` visibility) vs `config/mcp_servers.json`.
2. **Toggle state in the same file** (recommended — single source of truth, git audit) vs a separate state file like skills' S3 state.
3. **Reload endpoint** (recommended) vs restart-only semantics.
4. ~~Separate MCP tab~~ — **resolved 2026-10-04**: gear icon in the sidebar footer opens a settings view hosting Skills + MCP (§6).
5. **No LLM toggle tool** (recommended, see §1) vs a `mcp_manage` tool symmetric with `skill_manage`.

## 11. Effort estimate

| Phase | Work | Est. |
|---|---|---|
| 1 | `mcp_config.py` + JSON + main.py rewiring + parity/tests | 0.5–1 d |
| 2 | REST endpoints + reload guard | 0.5 d |
| 3 | React MCP tab | 0.5–1 d |
| | **Total** | **~2 days**, phases shippable independently |
