# Skills Registry Plan — S3-backed, per-user enable/disable (Option A)

Status: **draft for review** · 2026-10-03
Feasibility study: conversation 2026-10-03 (full filesystem inventory of `skills/`, `wiki/`, `workspace/`, `raw/`, `memories/` across this repo and `nm-memory-layer`).

## 1. Goals and non-goals

**Goals**

1. A new, **independent skills registry library** (separate package, per Option A) with skills stored in **S3-compatible object storage** as the authoritative store.
2. **Per-user enable/disable** of skills (Hermes-Agent-style toggles): disabled skills are invisible to the agent's index, `load_skill`, and `skill_manage`; remain visible to an admin/toggle surface so they can be re-enabled.
3. `raw/` **moved off-box** the same way (S3-authoritative, local cache, sync CLI).
4. The storage core (object-store backends + cache) is generic so `wiki/` and `workspace/` can adopt it later — but they are **out of scope for this effort**.

**Non-goals (this phase)**

- Migrating `wiki/`, `workspace/`, `memories/`, or `sessions.db` (sessions.db stays local permanently — SQLite WAL/mmap semantics are incompatible with object storage).
- A hosted multi-tenant service. The registry is a **library**; a service can wrap it later.
- Changing how skill scripts are invoked: the agent still runs `skills/<category>/<name>/scripts/*.py` from a real local directory.

## 2. Architecture

```
┌────────────────────────────────────────────────────────────┐
│ S3-compatible bucket (authoritative)                       │
│   skills/<category>/<name>/SKILL.md + references/ scripts/ │
│   state/users/<user_id>/skills.json      (enabled/disabled)│
│   raw/…                                                    │
└──────────────▲─────────────────────────────────────────────┘
               │ list / get / put (CAS) / delete
┌──────────────┴─────────────────────────────────────────────┐
│ nm-skills-registry (new library)                           │
│   storage/: LocalDirStore · S3Store · CachedStore (ETag,   │
│             write-through, local disk mirror)              │
│   registry/: SkillRegistry (SkillLibrary-compatible) ·     │
│             SkillState (per-user toggles) · sync           │
│   cli: import · sync · list · enable/disable · doctor      │
└──────────────▲─────────────────────────────────────────────┘
               │ index once/session · load_skill · skill_manage
┌──────────────┴─────────────────────────────────────────────┐
│ nm-memory-layer (SkillLibrary delegates to registry)       │
│ langgraph-demo (main.py, server.py, frontend Skills tab)   │
└────────────────────────────────────────────────────────────┘
```

**Key design decision — the local mirror is not optional.** Skill *scripts* (39 `.py` files today) are executed by the agent via the `execute` shell tool and read/write real paths. Therefore `SKILLS_DIR` (default `./skills`) stays exactly where it is, with its exact current layout, as a **materialized write-through cache** of the bucket. The registry keeps it coherent; nothing about script invocation changes.

## 3. New package: `nm-skills-registry` (working name)

Sibling repo to `nm-memory-layer` (same owner, same install pattern: `[tool.uv.sources]` path dep, later GitHub dep).

```
nm-skills-registry/
  pyproject.toml            # py>=3.11; deps: obstore, pyyaml; optional: fastapi
  nm_skills_registry/
    storage/
      base.py               # ObjectStore protocol (below)
      local.py              # LocalDirStore — real files; dev, tests, and the mirror
      s3.py                 # S3Store via obstore (AWS/MinIO/R2/Wasabi via endpoint config)
      cache.py              # CachedStore — S3 authority + local disk mirror + ETag revalidation
    registry/
      store.py              # SkillRegistry: index/resolve/load/CRUD — byte-compatible with SkillLibrary
      state.py              # SkillState: per-user enabled/disabled map (single JSON object, ETag CAS)
      sync.py               # materialize(dir) / publish(dir) / drift report
    fastapi.py              # optional APIRouter (skills list, toggle, sync) for server.py
    cli.py                  # `nm-skills` CLI
  tests/                    # local-backend unit tests + optional MinIO integration (marked, skipped by default)
```

### 3.1 `ObjectStore` protocol (the whole surface)

From the feasibility inventory — the vault-facing code needs exactly these primitives and nothing more (no append, no locking, no fsync, no rename on content):

| Method | Used by |
|---|---|
| `list_prefix(prefix) → [(key, etag, size, mtime)]` | index build, sync reconcile |
| `get(key) → bytes` / `get_text(key)` | SKILL.md, references, scripts |
| `put(key, data, *, if_match: etag \| None)` | create/patch/edit, state writes |
| `delete(key)` / `delete_prefix(prefix)` | remove_file, delete_skill (`rmtree` equivalent) |
| `head(key) → etag, size, mtime` / `exists(key)` | resolve, guard checks |

Notes:
- **Directories are implicit prefixes.** `mkdir(parents=True)` at `skills.py:134/180` and `PromptMemory`'s init mkdir become no-ops. `remove_skill_file`'s leftover empty dirs disappear (harmless).
- **Conditional PUT (If-Match)** turns the current unlocked read-modify-writes (`patch_skill` `skills.py:143`, `edit_skill` `skills.py:157`) into safe CAS. AWS S3, R2, and MinIO support conditional writes; for backends that don't, degrade to last-writer-wins **with bucket versioning on** and log a warning.
- **Bucket versioning is required** — skills are agent-authored executable instructions; versioning is the undo button.
- Backend config via env: `SKILLS_REGISTRY=s3://<bucket>/<prefix>` (or `local:<path>`), plus standard endpoint/credentials envs (`AWS_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, region). `obstore` reads these natively.

### 3.2 `CachedStore` (latency mitigation, part of storage core)

- Read path: serve from local mirror/memory; revalidate with `list_prefix` (1 request) + conditional GET on changed ETags. Steady-state session start ≈ 1 list + a few conditional gets (~100–300 ms); cold first run ≈ full pull (4 MB, sub-second on decent links).
- Write path: write-through `put` (CAS) → update mirror on success; failed CAS = conflict surfaced to caller (agent retries read-modify-write, same as a human editor).
- Offline mode: if the store is unreachable, serve the mirror read-only and warn (`doctor` reports staleness). The agent keeps working with last-known skills — the mirror is durable across restarts.
- The same CachedStore is what `wiki/` and `workspace/` would adopt later.

### 3.3 `SkillRegistry` — parity contract with `SkillLibrary`

The registry reimplements `nm_memory_layer/skills.py` semantics exactly (it is ~190 lines; we port, we don't improvise). Parity checklist (mirrors the A/B parity discipline used for the wiki engine port):

- [ ] Index: `sorted()` recursive scan for `SKILL.md`, frontmatter parse (`name`, `description`), `render_index` output **byte-identical** for the same tree.
- [ ] `resolve`: frontmatter-name match beats parent-dir name; full scan semantics preserved (then cached).
- [ ] `create`: reject existing skill; implicit prefix creation.
- [ ] `patch`: first-occurrence `str.replace` semantics, now under CAS.
- [ ] `edit`, `write_skill_file`, `remove_skill_file`, `delete_skill` (recursive prefix delete).
- [ ] Path guard: reject absolute paths and `..` (`skills.py:167-174`).
- [ ] One encoding pinned everywhere (`utf-8`) — fixes the current locale-dependent `read_text()`/`write_text()` calls.

### 3.4 Enable/disable (`SkillState`)

- Storage: `state/users/<user_id>/skills.json` — `{"disabled": ["category/name", …], "updated_at": …}`. Written with ETag CAS; single object, no scan cost.
- Semantics: **enabled-by-default**; the disabled list is the only state (no "enablement drift" when new skills appear).
- `user_id` defaults to `"default"` (env `SKILLS_USER_ID`). The schema is user-scoped from day one; multi-user ships later without migration.
- Visibility rules:
  - Agent-facing (`render_index`, `load_skill`, `skill_manage` list/resolve): **enabled only**.
  - Toggle/admin surface (CLI, REST, UI, `skill_manage` with `include_disabled`): **all skills + status**.
- `skill_manage` gains actions `enable` / `disable` (and `list` with status) — no new tool sprawl; `load_skill` on a disabled skill returns a "skill is disabled" result rather than silent failure.
- Timing note: the skills index is injected once per session (`main.py:553-557`) and re-read by the nudge (`main.py:499-501`), so a toggle fully applies **next session**; mid-session it takes effect on the next nudge re-render. Document this; don't build mid-session re-injection yet.

## 4. Bucket layout

```
s3://<bucket>/
  skills/                              # authority; mirrors today's ./skills layout 1:1
    browser-act/SKILL.md
    convert-web-article-to-md/SKILL.md
    convert-web-article-to-md/references/…
    convert-web-article-to-md/scripts/…
    …
  state/
    users/default/skills.json
  raw/                                 # phase 5 — same store, separate prefix
```

Import excludes `__pycache__/` and `*.pyc` (7 stray `.pyc` files exist in `skills/` today; they are never content).

## 5. Integration — `nm-memory-layer` and this repo

**Recommended: one implementation, delegated.** `nm-memory-layer` gains a dependency on `nm-skills-registry`; its `SkillLibrary` becomes a delegating shim over `SkillRegistry` with a `LocalDirStore` default — **zero behavior change** for any other consumer of the memory layer, and no risk of two implementations of `skill_manage` semantics drifting. (`PromptMemory` is untouched; `WikiStore` untouched.)

`langgraph-demo` wiring:

- `main.py:175` / `server.py`: construct `SkillRegistry` with `CachedStore(S3Store(...))` instead of `SkillLibrary` with a bare path — single construction site each, injected through the same interfaces the memory layer already exposes.
- Env: `SKILLS_REGISTRY=s3://…` set in `.env`; `SKILLS_DIR` unchanged (it is the mirror path).
- `server.py:178` `/api/skills` → registry (now includes enabled state; also stops the per-request full `rglob`+read of all 56 SKILL.md files).
- `server.py:158` `/api/health` → registry `available()` (cached listing) instead of a full vault walk+read — an incidental but real win.
- New REST: `POST /api/skills/{name}/enabled {enabled: bool}` (user = `"default"` for now).
- Optional frontend **Skills tab** (React, alongside Wiki tab): list with enable/disable switches, search, sync button. Est. ~1 day; phase 6, explicitly optional.
- New agent tool action availability: `skill_manage(enable|disable)` — the agent can toggle on explicit user request; the UI remains the primary Hermes-style surface.

## 6. `raw/` offload (phase 5)

- One-time `nm-skills import ./raw s3://<bucket>/raw` (39 MB, 716 files — PDFs/CSVs).
- After cutover, `raw/` is a **sync cache, not a live-mounted store**: skill scripts keep reading local paths, and a sync pass (`nm-skills sync raw` — list-diff by ETag/size, pull/push) runs at session start (optional flag — it's a few seconds) and on demand. Writes that scripts drop into `raw/` (e.g. convert-pdf-to-md outputs next to a source PDF) are pushed by the next sync.
- Conflict policy: newest-mtime-wins with a drift report printed; bucket versioning catches mistakes. raw/ has a single writer in practice (this box), so this is backup + portability, not multi-master.

## 7. Migration and cutover

1. **Build & parity** — library with `LocalDirStore`; run the §3.3 checklist against the current `skills/` tree (index bytes, resolve order, CRUD behaviors). All green before any S3 code is trusted.
2. **Import** — `nm-skills import ./skills s3://…/skills`; verify object count + ETag checksums; keep the local tree untouched (rollback = nothing changed yet).
3. **Cutover this repo** — set `SKILLS_REGISTRY` in `.env`; `git rm -r --cached skills/` + gitignore `skills/` (tag the last commit carrying skills as `skills-in-git-final` — history remains browsable; the registry + bucket versioning replace git as the transport). Existing tests `uv run pytest tests/ -q` still pass (registry runs against a `local:` URL in tests).
4. **Toggle rollout** — `SkillState`, `skill_manage` actions, REST; verify disabled skills vanish from the injected index and `load_skill`.
5. **raw/** — import + sync wiring (§6).
6. **UI** (optional) — Skills tab.

Each phase is independently shippable; step 3 is the only one that changes agent behavior, and it is reversible by unsetting one env var.

## 8. Testing & acceptance

- Unit (no network, no LLM): store protocol conformance for `LocalDirStore` and `S3Store` (MinIO via docker, marked/skipped by default); CAS conflict paths; toggle filtering; path guard.
- Parity: §3.3 checklist as an actual test fixture run against both the old `SkillLibrary` and the registry (the wiki-engine A/B pattern, repeated).
- Integration (this repo): existing `tests/` suite stays green with `SKILLS_REGISTRY=local:…`; new wiring tests for registry construction, `/api/skills`, toggle endpoint.
- Browser regression of the Skills tab if built (same discipline as the wiki-tab pass).

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| S3 unavailable at session start | Offline mode: durable local mirror served read-only + warning (`§3.4` of storage core; `doctor` shows staleness) |
| Conditional PUT unsupported on some S3-compatibles | Feature-detect; fall back to last-writer-wins + bucket versioning + warning log |
| Agent-written skills are executable instructions (prompt-injection / supply-chain surface) | Bucket write creds are the trust boundary; versioning = undo; per-user disable = kill switch; import excludes non-content files |
| Two skill implementations drift (memory layer vs registry) | Delegation design (§5) — one implementation, memory layer is a shim |
| Sync clobbers local script output in `raw/` | Sync is explicit + drift report; versioning catches it |
| Toggle confusion mid-session | Documented semantics: next session (nudge re-render is the only mid-session path) |

## 10. Open decisions (recommendations included)

1. **Package/repo name** — `nm-skills-registry` (working name). Any preference?
2. **Object-store client** — `obstore` (Rust `object_store` bindings; async, one API for S3/GCS/Azure/local; my recommendation) vs `aioboto3`.
3. **Toggle surface for v1** — REST + `skill_manage` actions + CLI now, React tab as optional phase 6 (my recommendation), or UI in v1.
4. **Mid-session toggle semantics** — accept "next session" (recommended) vs rebuild the system prompt each turn (costlier, touches main.py flow).
5. **raw/ sync trigger** — explicit CLI only (recommended v1) vs automatic session-start pull.

## 11. Effort estimate

| Phase | Work | Est. |
|---|---|---|
| 1 | Storage core: protocol, LocalDirStore, tests | 2–3 d |
| 2 | Registry + SkillState + parity suite | 2–3 d |
| 3 | S3Store + CachedStore + MinIO integration tests | 2 d |
| 4 | nm-memory-layer shim + langgraph-demo wiring + cutover | 2 d |
| 5 | raw/ import + sync CLI | 1 d |
| 6 | REST polish + optional Skills tab | 0.5–1.5 d |
| | **Total** | **~9–11 focused days**, phases shippable independently |
