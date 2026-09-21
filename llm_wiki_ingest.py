"""Self-contained LLM-wiki ingestion: LangGraph agent + OpenViking, no gateway.

Materializes an OpenViking source tree into ./workspace, packages a skill into
the agent context, runs a ReAct loop (LangGraph) whose tools read the
materialized corpus or query OpenViking directly, then upserts the agent's
output directory back into OpenViking under --to.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Sequence, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from openviking_sdk import AsyncHTTPClient

load_dotenv()

_SCRIPT_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _SCRIPT_DIR / "workspace"
_OPENVIKING_URL = (os.getenv("OPENVIKING_URL") or "http://localhost:1933").rstrip("/")
_OPENVIKING_KEY = os.getenv("OPENVIKING_API_KEY") or ""

_TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".csv", ".tsv",
    ".py", ".js", ".ts", ".tsx", ".html", ".htm", ".xml", ".rst", ".log",
}
_SKIP_NAME_RE = re.compile(r"(^|/)(\.path\.|.*\.ovlock$|\.DS_Store$)")
_MAX_SINGLE_LINE = 240

RUN_DIR: Path | None = None
OV: AsyncHTTPClient | None = None


def _normalize_uri(uri: str) -> str:
    return uri.rstrip("/")


def _rel_from_uri(uri: str, root: str) -> str:
    norm = _normalize_uri(uri)
    base = _normalize_uri(root)
    if norm == base:
        return ""
    if norm.startswith(base + "/"):
        return norm[len(base) + 1:]
    return norm.rsplit("/", 1)[-1]


def _resolve_under(root: Path, rel: str) -> Path:
    target = (root / rel).resolve()
    root_res = root.resolve()
    if target != root_res and root_res not in target.parents:
        raise ValueError(f"path escapes workspace root: {rel}")
    return target


def _safe_rel(rel: str) -> str:
    cleaned = rel.strip().lstrip("/")
    if not cleaned or ".." in Path(cleaned).parts:
        raise ValueError(f"unsafe relative path: {rel}")
    return cleaned


def _is_text_candidate(name: str, size: int, max_file_bytes: int) -> bool:
    if size > max_file_bytes:
        return False
    suffix = Path(name).suffix.lower()
    return suffix in _TEXT_SUFFIXES


async def _walk_uri(client: AsyncHTTPClient, root_uri: str) -> list[dict[str, Any]]:
    try:
        entries = await client.ls(uri=root_uri, recursive=True, node_limit=5000, abs_limit=20000, show_all_hidden=True)
        return [e for e in entries if isinstance(e, dict)]
    except Exception:
        try:
            content = await client.read(uri=root_uri)
            size = len(content.encode("utf-8"))
            name = _normalize_uri(root_uri).rsplit("/", 1)[-1]
            return [{"uri": _normalize_uri(root_uri), "isDir": False, "size": size, "name": name, "_inline": content}]
        except Exception:
            return []


async def _materialize_tree(
    client: AsyncHTTPClient,
     root_uri: str,
     dest: Path,
     *,
     max_files: int,
     max_total_bytes: int,
     max_file_bytes: int,
     include_hidden: bool = True,
) -> tuple[list[dict[str, str]], list[str], int]:
    entries = await _walk_uri(client, root_uri)
    root_norm = _normalize_uri(root_uri)
    inline = [e for e in entries if e.get("_inline")]
    files = [e for e in entries if e.get("isDir") is False and not e.get("_inline")]
    if inline and not files:
        files = inline
    if not include_hidden:
        files = [
            e for e in files
            if not any(part.startswith(".") for part in Path(_rel_from_uri(str(e.get("uri") or ""), root_norm)).parts)
        ]
    total_in_tree = len(files)

    candidates = [e for e in files if _is_text_candidate(str(e.get("name") or ""), int(e.get("size") or 0), max_file_bytes)]
    fallback_used = False
    if not candidates and files:
        candidates, fallback_used = files[:max_files], True
    candidates = candidates[:max_files]

    manifest: list[dict[str, str]] = []
    failures: list[str] = []
    total = 0
    semaphore = asyncio.Semaphore(8)

    async def fetch(entry: dict[str, Any]) -> None:
        nonlocal total
        uri = str(entry.get("uri") or "")
        rel = _rel_from_uri(uri, root_norm)
        if not rel or _SKIP_NAME_RE.search(rel):
            return
        size = int(entry.get("size") or 0)
        if total + size > max_total_bytes:
            failures.append(f"{uri} (total-size budget reached)")
            return
        async with semaphore:
            try:
                content = entry.get("_inline") or await client.read(uri=uri)
            except Exception as exc:
                failures.append(f"{uri} ({str(exc)[:80]})")
                return
        target = _resolve_under(dest, _safe_rel(rel))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8", errors="replace")
        total += size
        manifest.append({"uri": uri, "path": rel, "bytes": str(size)})

    await asyncio.gather(*(fetch(e) for e in candidates))
    manifest.sort(key=lambda m: m["path"])
    if fallback_used:
        failures.append("note: no text-suffix files matched; fell back to first files regardless of type")
    return manifest, failures, total_in_tree


def _write_manifest(dest: Path, manifest: list[dict[str, str]], failures: list[str]) -> None:
    lines = ["# Source manifest", "", "| Source URI | Local path | Bytes |", "|---|---|---|"]
    lines += [f"| {m['uri']} | sources/{m['path']} | {m['bytes']} |" for m in manifest]
    if failures:
        lines += ["", "## Not materialized", ""]
        lines += [f"- {f}" for f in failures]
    (dest / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


_INGESTION_LOG_PAGE = "ingestion-log.md"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_ingestion_log(text: str) -> dict[str, tuple[str, str]]:
    entries: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = re.match(r"^\|\s*(\S+)\s*\|\s*(viking://\S+)\s*\|\s*([0-9a-f]{64})\s*\|", line)
        if match:
            entries[match.group(2)] = (match.group(3), match.group(1))
    return entries


_RUN_LINE_RE = re.compile(r"^- \d{4}-\d{2}-\d{2}T")


def _extract_run_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if _RUN_LINE_RE.match(line)]


def _render_ingestion_log(
    entries: dict[str, tuple[str, str]],
    run_lines: list[str],
) -> str:
    lines = [
        "# Ingestion log",
        "",
        "Tracks which source revisions have been compiled into this wiki. "
        "Maintained by llm_wiki_ingest.py: one row per source, updated only when that "
        "source is (re)compiled; each run appends to the run history.",
        "",
        "| Compiled (UTC) | Source URI | SHA-256 |",
        "|---|---|---|",
    ]
    for uri, (sha, compiled) in sorted(entries.items(), key=lambda item: (item[1][1], item[0])):
        lines.append(f"| {compiled} | {uri} | {sha} |")
    lines += ["", "## Run history", ""]
    lines += run_lines
    return "\n".join(lines) + "\n"


@tool
async def read_file(path: str) -> str:
    """Read a text file from the task workspace (sources/, skill/, output/, MANIFEST.md). Use relative paths."""
    assert RUN_DIR is not None
    target = _resolve_under(RUN_DIR, path)
    if not target.is_file():
        return f"Error: no such file: {path}"
    data = target.read_text(encoding="utf-8", errors="replace")
    if len(data) > 200_000:
        return data[:200_000] + "\n...[truncated at 200000 chars]"
    return data


@tool
async def list_files(path: str = ".") -> str:
    """List files under a workspace directory (relative paths), e.g. 'sources' or 'skill/llm-wiki'."""
    assert RUN_DIR is not None
    root = _resolve_under(RUN_DIR, path)
    if not root.is_dir():
        return f"Error: no such directory: {path}"
    entries = sorted(str(p.relative_to(RUN_DIR)) for p in root.rglob("*") if p.is_file())
    if len(entries) > 500:
        entries = entries[:500] + ["...[truncated at 500 entries]"]
    return "\n".join(entries) if entries else "(empty)"


@tool
async def grep_files(pattern: str, path: str = ".", max_results: int = 80) -> str:
    """Regex-search files under a workspace directory. Returns 'path:line: text' matches."""
    assert RUN_DIR is not None
    root = _resolve_under(RUN_DIR, path)
    if not root.is_dir() and not root.is_file():
        return f"Error: no such path: {path}"
    try:
        rx = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"Error: invalid regex: {exc}"
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    hits: list[str] = []
    for file_path in files:
        try:
            for line_no, line in enumerate(file_path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{file_path.relative_to(RUN_DIR)}:{line_no}: {line.strip()[:_MAX_SINGLE_LINE]}")
                    if len(hits) >= max_results:
                        hits.append("...[result cap reached]")
                        return "\n".join(hits)
        except Exception:
            continue
    return "\n".join(hits) if hits else "(no matches)"


@tool
async def write_output_file(path: str, content: str) -> str:
    """Create or overwrite a wiki page under 'output/'. Relative path becomes the target path."""
    assert RUN_DIR is not None
    rel = _safe_rel(path)
    if rel.startswith("output/"):
        rel = rel[len("output/"):]
    target = _resolve_under(RUN_DIR / "output", rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote output/{rel} ({len(content)} chars)"


@tool
async def ov_search(query: str, target_uri: str = "", limit: int = 5) -> str:
    """Semantic search in OpenViking. Optionally scope with target_uri; context_type filter optional via raw query."""
    assert OV is not None
    try:
        result = await OV.search(query=query, target_uri=target_uri, limit=limit)
    except Exception as exc:
        return f"Error: ov_search failed: {str(exc)[:200]}"
    lines = []
    for group in ("memories", "resources", "skills"):
        for item in result.get(group) or []:
            lines.append(f"{item.get('uri')} score={item.get('score')}\n{str(item.get('abstract') or '')[:400]}")
    return "\n\n".join(lines) if lines else "(no results)"


@tool
async def ov_read(uri: str) -> str:
    """Read a file's content from OpenViking by viking:// URI. Directory URIs resolve to their .overview.md sidecar."""
    assert OV is not None
    try:
        return str(await OV.read(uri=uri))
    except Exception:
        for sidecar in (f"{_normalize_uri(uri)}/.overview.md", f"{_normalize_uri(uri)}/.abstract.md"):
            try:
                content = await OV.read(uri=sidecar)
                return f"[directory content via {sidecar.rsplit('/', 1)[-1]}]\n{content}"
            except Exception:
                continue
        return (
            f"Error: cannot read {uri} as a file and it has no .overview.md/.abstract.md sidecar. "
            "Use ov_ls on its parent to find readable file URIs."
        )


@tool
async def ov_ls(uri: str) -> str:
    """List an OpenViking directory (non-recursive) by viking:// URI."""
    assert OV is not None
    try:
        entries = await OV.ls(uri=uri, node_limit=500)
        lines = [
            f"{'dir ' if e.get('isDir') else 'file'}  {e.get('uri')}  {e.get('size')}B"
            for e in entries if isinstance(e, dict)
        ]
        return "\n".join(lines) if lines else "(empty)"
    except Exception as exc:
        return f"Error: ov_ls failed for {uri}: {str(exc)[:200]}"


@tool
async def submit_wiki(summary: str) -> str:
    """Finish the task: submit the wiki. Call ONLY when all pages are written under output/."""
    return summary


class WikiState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


CONTEXT_CHAR_BUDGET = 1_200_000
KEEP_RECENT_MESSAGES = 8


def _block_reasonable_size(block: Sequence[BaseMessage]) -> int:
    return sum(len(str(getattr(m, "content", "") or "")) for m in block) + 60


def _group_blocks(messages: Sequence[BaseMessage]) -> list[list[BaseMessage]]:
    blocks: list[list[BaseMessage]] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        if isinstance(m, AIMessage) and m.tool_calls:
            block = [m]
            i += 1
            while i < len(messages) and isinstance(messages[i], ToolMessage):
                block.append(messages[i])
                i += 1
            blocks.append(block)
        else:
            blocks.append([m])
            i += 1
    return blocks


def _compact_messages(
    messages: Sequence[BaseMessage],
    *,
    keep_recent: int,
    budget_chars: int,
) -> list[BaseMessage]:
    """Build the view sent to the LLM: system + initial task + recent turns
    verbatim, older tool history folded into the task prompt. State history
    stays intact; only what is re-sent each iteration is bounded.

    Sequencing constraints for strict providers (e.g. Zai/GLM code 1214):
    - never emit consecutive assistant messages;
    - never emit a ToolMessage without its assistant tool_calls (blocks are
      kept whole);
    - never emit an empty-content tool message.
    """
    msgs = list(messages)
    if len(msgs) <= 3:
        return msgs
    head = msgs[:1] if isinstance(msgs[0], SystemMessage) else list(msgs[:1])
    body = msgs[len(head):]
    first_human: BaseMessage | None = None
    if body and isinstance(body[0], HumanMessage) and not getattr(body[0], "tool_calls", None):
        first_human = body[0]
        body = body[1:]
    blocks = _group_blocks(body)

    keep: list[list[BaseMessage]] = []
    used = 0
    for block in reversed(blocks):
        size = _block_reasonable_size(block)
        if len(keep) >= keep_recent or used + size > budget_chars:
            break
        keep.insert(0, block)
        used += size
    if not keep and blocks:
        keep = [blocks[-1]]
    dropped = len(blocks) - len(keep)
    if dropped == 0:
        return list(msgs)
    digest = (
        f"\n\n[History compacted: {dropped} earlier agent/tool step(s) omitted. Their "
        "evidence is already integrated into the pages written under output/. "
        "Continue: finish remaining pages or call submit_wiki.]"
    )
    if first_human is not None:
        lead = [
            *head,
            HumanMessage(content=str(first_human.content or "") + digest),
        ]
    else:
        lead = head + [HumanMessage(content=digest.strip())]
    view: list[BaseMessage] = list(lead)
    for block in keep:
        for m in block:
            if isinstance(m, ToolMessage) and not str(m.content or "").strip():
                view.append(
                    ToolMessage(content="(empty result)", tool_call_id=m.tool_call_id)
                )
            else:
                view.append(m)
    return view


TOOLS = [read_file, list_files, grep_files, write_output_file, ov_search, ov_read, ov_ls, submit_wiki]
TOOL_NODE = ToolNode([t for t in TOOLS if t.name != "submit_wiki"], handle_tool_errors=True)


def _route(state: WikiState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage):
        if any(call["name"] == "submit_wiki" for call in (last.tool_calls or [])):
            return "finalize"
        if last.tool_calls:
            return "execute_tool"
        return "finalize"
    return "agent"


async def _finalize(state: WikiState) -> dict[str, Any]:
    assert RUN_DIR is not None and OV is not None
    output_dir = RUN_DIR / "output"
    pages = sorted(
        p for p in output_dir.rglob("*")
        if p.is_file() and p.stat().st_size > 0 and p.name != _INGESTION_LOG_PAGE
    )
    if not pages:
        return {"messages": [AIMessage(content="Nothing was written under output/; no ingestion performed.")]}
    operations = []
    for page in pages:
        rel = str(page.relative_to(output_dir))
        target_uri = f"{_normalize_uri(TARGET_URI)}/{rel}"
        operations.append({
            "uri": target_uri,
            "content_base64": base64.b64encode(page.read_bytes()).decode("ascii"),
            "mode": "upsert",
        })
    merged_log = dict(EXISTING_LOG)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for uri, sha in SOURCE_HASHES.items():
        existing = EXISTING_LOG.get(uri)
        if existing and existing[0] == sha:
            merged_log[uri] = existing
        else:
            merged_log[uri] = (sha, now)
    run_line = (
        f"- {now} — compiled {len(SOURCE_HASHES)} source(s): "
        f"{len(FRESHNESS['new'])} new, {len(FRESHNESS['changed'])} changed, "
        f"{len(FRESHNESS['unchanged'])} unchanged; wrote {len(operations)} page(s)."
    )
    operations.append({
        "uri": f"{_normalize_uri(TARGET_URI)}/{_INGESTION_LOG_PAGE}",
        "content_base64": base64.b64encode(
            _render_ingestion_log(merged_log, _extract_run_lines(EXISTING_LOG_TEXT) + [run_line]).encode("utf-8")
        ).decode("ascii"),
        "mode": "upsert",
    })
    try:
        result = await OV.batch_write(root_uri=TARGET_URI, operations=operations, wait=True, timeout=900)
    except Exception as exc:
        landed = []
        try:
            entries = await OV.ls(uri=TARGET_URI, node_limit=50)
            landed = [str(e.get("name")) for e in entries if isinstance(e, dict)]
        except Exception:
            pass
        note = (
            f"batch_write errored ({type(exc).__name__}: {str(exc)[:200]}). "
            f"The write may still complete server-side; target currently contains: "
            f"{landed or '(empty or unreadable)'}."
        )
        return {"messages": [AIMessage(content=note)]}
    freshness_note = (
        f"freshness: {len(FRESHNESS['new'])} new, {len(FRESHNESS['changed'])} changed, "
        f"{len(FRESHNESS['unchanged'])} unchanged sources; ingestion log updated "
        f"({len(merged_log)} tracked revision(s))"
    )
    summary = f"Ingested {len(operations) - 1} page(s) into {TARGET_URI}: " + ", ".join(
        str(op["uri"]) for op in operations if op["uri"] != f"{_normalize_uri(TARGET_URI)}/{_INGESTION_LOG_PAGE}"
    )
    return {"messages": [AIMessage(content=summary + f"\n{freshness_note}\nbatch_write result: {str(result)[:300]}")]}


TARGET_URI = ""
SOURCE_HASHES: dict[str, str] = {}
EXISTING_LOG: dict[str, tuple[str, str]] = {}
EXISTING_LOG_TEXT = ""
FRESHNESS: dict[str, list[str]] = {"new": [], "changed": [], "unchanged": []}
EXISTING_PAGE_COUNT = 0


def _build_graph() -> Any:
    workflow = StateGraph(WikiState)
    workflow.add_node("agent", _call_model)
    workflow.add_node("execute_tool", TOOL_NODE)
    workflow.add_node("finalize", _finalize)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", _route, {"execute_tool": "execute_tool", "finalize": "finalize"})
    workflow.add_edge("execute_tool", "agent")
    workflow.add_edge("finalize", END)
    return workflow.compile()


async def _call_model(state: WikiState) -> dict[str, Any]:
    view = _compact_messages(
        state["messages"],
        keep_recent=KEEP_RECENT_MESSAGES,
        budget_chars=CONTEXT_CHAR_BUDGET,
    )
    response = await MODEL_WITH_TOOLS.ainvoke(view)
    return {"messages": [response]}


MODEL_WITH_TOOLS: Any = None


async def ingest_once(args: argparse.Namespace, *, run_dir: Path, ov: AsyncHTTPClient) -> dict[str, Any]:
    """One compilation run of args.from_uri into args.to_uri. Returns a summary dict."""
    global RUN_DIR, OV, TARGET_URI, MODEL_WITH_TOOLS
    global SOURCE_HASHES, EXISTING_LOG, EXISTING_LOG_TEXT, FRESHNESS, EXISTING_PAGE_COUNT

    RUN_DIR = run_dir
    OV = ov
    TARGET_URI = args.to_uri
    for sub in ("sources", "skill", "output", "existing_target"):
        (RUN_DIR / sub).mkdir(parents=True, exist_ok=True)
    print(f"workspace: {RUN_DIR}")

    t0 = time.perf_counter()
    manifest, failures, total_in_tree = await _materialize_tree(
        OV, args.from_uri, RUN_DIR / "sources",
        max_files=args.max_files,
        max_total_bytes=int(args.max_total_mb * 1024 * 1024),
        max_file_bytes=int(args.max_file_kb * 1024),
    )
    _write_manifest(RUN_DIR / "sources", manifest, failures)
    print(f"materialized {len(manifest)} source file(s) in {time.perf_counter() - t0:.1f}s "
          f"(tree holds {total_in_tree} file(s); {len(failures)} skipped/failed)")

    skill_name = _rel_from_uri(args.skill_uri, args.skill_uri)
    skill_bundle: list[dict[str, str]] = []
    skill_md = ""
    if args.skill_uri:
        skill_bundle, skill_failures, _skill_total = await _materialize_tree(
            OV, args.skill_uri, RUN_DIR / "skill",
            max_files=100, max_total_bytes=32 * 1024 * 1024, max_file_bytes=1024 * 1024,
        )
        skill_dir_name = next((m["path"].split("/")[0] for m in skill_bundle if "/" in m["path"]), "")
        if skill_dir_name:
            skill_name = skill_dir_name
        for candidate in (f"{skill_name}/SKILL.md", "SKILL.md", f"{skill_name}/.abstract.md"):
            candidate_path = RUN_DIR / "skill" / candidate
            if candidate_path.is_file():
                skill_md = candidate_path.read_text(encoding="utf-8", errors="replace")
                break
        print(f"skill packaged: {len(skill_bundle)} file(s); SKILL.md found: {bool(skill_md)}")
        if not skill_bundle:
            print(f"WARNING: skill URI yielded nothing: {args.skill_uri}")

    existing_manifest, _existing_failures, _existing_total = await _materialize_tree(
        OV, args.to_uri, RUN_DIR / "existing_target",
        max_files=args.max_files,
        max_total_bytes=int(args.max_total_mb * 1024 * 1024),
        max_file_bytes=int(args.max_file_kb * 1024),
        include_hidden=False,
    )
    EXISTING_PAGE_COUNT = len(existing_manifest)
    existing_log_path = RUN_DIR / "existing_target" / _INGESTION_LOG_PAGE
    if existing_log_path.is_file():
        EXISTING_LOG_TEXT = existing_log_path.read_text(encoding="utf-8", errors="replace")
        EXISTING_LOG = _parse_ingestion_log(EXISTING_LOG_TEXT)
    else:
        EXISTING_LOG = {}

    SOURCE_HASHES = {
        entry["uri"]: _sha256_of(RUN_DIR / "sources" / entry["path"]) for entry in manifest
    }
    FRESHNESS = {"new": [], "changed": [], "unchanged": []}
    for uri, sha in SOURCE_HASHES.items():
        if uri not in EXISTING_LOG:
            FRESHNESS["new"].append(uri)
        elif EXISTING_LOG[uri][0] != sha:
            FRESHNESS["changed"].append(uri)
        else:
            FRESHNESS["unchanged"].append(uri)
    print(f"existing wiki: {EXISTING_PAGE_COUNT} page(s); freshness: "
          f"{len(FRESHNESS['new'])} new, {len(FRESHNESS['changed'])} changed, "
          f"{len(FRESHNESS['unchanged'])} unchanged")

    if args.materialize_only:
        return {
            "skipped": False,
            "new": len(FRESHNESS["new"]),
            "changed": len(FRESHNESS["changed"]),
            "unchanged": len(FRESHNESS["unchanged"]),
            "pages": 0,
            "summary": "(materialize-only)",
        }

    if getattr(args, "per_source", False) and not FRESHNESS["new"] and not FRESHNESS["changed"]:
        print(f"[skip] {args.from_uri}: all {len(FRESHNESS['unchanged'])} source file(s) unchanged")
        return {"skipped": True, "new": 0, "changed": 0,
                "unchanged": len(FRESHNESS["unchanged"]), "pages": 0, "summary": "(all unchanged)"}

    def _bounded_uris(uris: list[str], cap: int = 25) -> str:
        lines = [f"  - {uri}" for uri in uris[:cap]]
        if len(uris) > cap:
            lines.append(f"  - ...and {len(uris) - cap} more")
        return "\n".join(lines) if lines else "  (none)"

    freshness_section = (
        "## Freshness report (vs. the ingestion log in the existing wiki)\n"
        f"New sources (never compiled): {len(FRESHNESS['new'])}\n{_bounded_uris(FRESHNESS['new'])}\n"
        f"Changed since last compile: {len(FRESHNESS['changed'])}\n{_bounded_uris(FRESHNESS['changed'])}\n"
        f"Already digested (unchanged): {len(FRESHNESS['unchanged'])}\n{_bounded_uris(FRESHNESS['unchanged'])}\n\n"
        "Focus reading on new and changed sources. Reread unchanged sources only when a page "
        "you must revise depends on them.\n"
    )

    if EXISTING_PAGE_COUNT:
        existing_section = (
            f"## Existing wiki\nMaterialized under `existing_target/` — the current state of "
            f"{_normalize_uri(args.to_uri)} ({EXISTING_PAGE_COUNT} page(s)).\n"
            "Read `existing_target/index.md` first, then inspect the catalog. Integrate new "
            "evidence into existing pages instead of rebuilding: match pages by subject identity, "
            "update the canonical page, and keep cross-references consistent. Do not rewrite "
            "pages that need no changes; writes are upserts, so pages you leave out of `output/` "
            "are preserved as-is.\n\n"
        )
    else:
        existing_section = (
            f"## Existing wiki\nNone yet — this is the first compilation of "
            f"{_normalize_uri(args.to_uri)}. Build the wiki from scratch.\n\n"
        )

    system_prompt = (
        "You are a wiki compilation agent. Your job is to compile the sources into a "
        "team-searchable wiki inside the task workspace, following the Skill below.\n\n"
        f"## Task reason\n{args.reason or '(not provided)'}\n\n"
        f"## Sources\nMaterialized under `sources/` (see `sources/MANIFEST.md` for the "
        f"viking:// URI of every local file — cite these URIs as provenance for claims).\n"
        f"Source root in OpenViking: {args.from_uri}\n\n"
        + existing_section
        + freshness_section
        + f"## Output\nWrite pages under `output/` as Markdown. Relative paths map directly "
        f"under the target URI {args.to_uri}. e.g. `output/index.md` -> "
        f"{_normalize_uri(args.to_uri)}/index.md\n\n"
        "## Rules\n"
        "- Keep the source of every claim: cite the source viking:// URI (from MANIFEST.md) or a relative source path.\n"
        "- Prefer grep_files over reading everything; read only what you need.\n"
        "- Do not read files outside the workspace; do not invent URIs.\n"
        "- Never create ingestion-log.md; it is maintained for you.\n"
        "- When the wiki is complete (index + topic pages), call submit_wiki with a one-paragraph summary.\n\n"
        f"## Skill\nURI: {args.skill_uri or '(none)'}\n\n{skill_md or '(skill content unavailable)'}\n"
    )

    llm = ChatOpenAI(
        temperature=args.temperature,
        max_completion_tokens=16384,
        model=args.model,
        api_key=os.getenv("OPENAI_API_KEY", ""), # type: ignore
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.z.ai/api/paas/v4/"),
    )
    MODEL_WITH_TOOLS = llm.bind_tools(TOOLS)

    user_prompt = (
        f"Compile the wiki now. {len(manifest)} source file(s) are materialized "
        f"({len(FRESHNESS['new'])} new, {len(FRESHNESS['changed'])} changed, "
        f"{len(FRESHNESS['unchanged'])} unchanged vs. the last compile); "
        f"{EXISTING_PAGE_COUNT} existing wiki page(s) are under existing_target/; "
        f"{len(skill_bundle)} skill file(s) are packaged under skill/. "
        "Begin by reading sources/MANIFEST.md, the freshness report above, and the skill instructions."
    )

    app = _build_graph()
    final_state = await app.ainvoke(
        {"messages": [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]},
        config={"recursion_limit": args.max_iterations * 2 + 20},
    )
    final_messages = final_state["messages"]
    agent_summary = ""
    for message in reversed(final_messages):
        if isinstance(message, AIMessage) and message.content:
            print("\n=== Agent summary ===\n" + str(message.content)[:2000])
            agent_summary = str(message.content)[:500]
            break

    pages_written = len([
        p for p in (RUN_DIR / "output").rglob("*")
        if p.is_file() and p.stat().st_size > 0
    ])
    return {
        "skipped": False,
        "new": len(FRESHNESS["new"]),
        "changed": len(FRESHNESS["changed"]),
        "unchanged": len(FRESHNESS["unchanged"]),
        "pages": pages_written,
        "summary": agent_summary,
    }


async def run_per_source(args: argparse.Namespace) -> None:
    """Run ingest_once once per child directory of --from, skipping dirs whose
    files are all unchanged against the wiki's ingestion log."""
    global OV
    OV = AsyncHTTPClient(url=os.getenv("OPENVIKING_URL"), api_key=_OPENVIKING_KEY, timeout=args.timeout)
    await OV.initialize()
    try:
        entries = await OV.ls(uri=args.from_uri, node_limit=500)
        children = sorted(
            (e for e in entries if isinstance(e, dict) and e.get("isDir")),
            key=lambda e: str(e.get("name") or ""),
        )
        if not children:
            print("no child directories under --from; falling back to a single run")
            await ingest_once(args, run_dir=_new_run_dir(), ov=OV)
            return
        print(f"per-source mode: {len(children)} source dir(s) under {args.from_uri} (LLM runs for new/changed only)")
        results: list[tuple[str, dict[str, Any]]] = []
        for idx, child in enumerate(children, 1):
            label = _rel_from_uri(str(child.get("uri") or ""), args.from_uri)
            sub_args = argparse.Namespace(**{**vars(args), "from_uri": str(child.get("uri") or "")})
            print(f"\n=== [{idx}/{len(children)}] {label} ===")
            result = await ingest_once(sub_args, run_dir=_new_run_dir(idx), ov=OV)
            results.append((label, result))
        print("\n=== per-source summary ===")
        for label, result in results:
            if result.get("skipped"):
                print(f"  SKIP  {label} ({result.get('unchanged', 0)} unchanged file(s))")
            else:
                print(
                    f"  RUN   {label}: new={result.get('new', 0)}, changed={result.get('changed', 0)}, "
                    f"unchanged={result.get('unchanged', 0)}, pages written={result.get('pages', 0)}"
                )
    finally:
        await OV.close()


def _new_run_dir(index: int = 0) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + (f"-{index:02d}" if index else "")
    return _WORKSPACE_ROOT / f"wiki-runs/{stamp}"


async def main() -> None:
    global CONTEXT_CHAR_BUDGET, KEEP_RECENT_MESSAGES

    parser = argparse.ArgumentParser(description="LLM-wiki ingestion via LangGraph + OpenViking (no gateway)")
    parser.add_argument("--from", dest="from_uri", required=True, help="Source viking:// URI")
    parser.add_argument("--to", dest="to_uri", required=True, help="Target viking:// URI for the wiki")
    parser.add_argument("--skill", dest="skill_uri", default="", help="Skill package viking:// URI to package into context")
    parser.add_argument("--reason", default="", help="Why this wiki is being compiled")
    parser.add_argument("--model", default=os.getenv("WIKI_MODEL", "glm-4.7"))
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--max-iterations", type=int, default=40)
    parser.add_argument("--max-files", type=int, default=300)
    parser.add_argument("--max-total-mb", type=float, default=64.0)
    parser.add_argument("--max-file-kb", type=float, default=512.0)
    parser.add_argument("--timeout", type=float, default=900.0, help="HTTP client timeout for OpenViking calls (batch_write waits server-side)")
    parser.add_argument("--materialize-only", action="store_true", help="Materialize sources/skill then exit")
    parser.add_argument("--per-source", action="store_true",
                        help="Run once per child directory of --from, skipping already-compiled dirs (no LLM calls for unchanged sources)")
    parser.add_argument("--keep-recent", type=int, default=8,
                        help="Agent turns re-sent verbatim after history compaction")
    parser.add_argument("--context-char-budget", type=int, default=1_200_000,
                        help="Approximate characters (~4 chars/token) allowed in one LLM call after compaction")
    args = parser.parse_args()

    if not _OPENVIKING_KEY:
        raise SystemExit("OPENVIKING_API_KEY is not set")
    if args.per_source and args.materialize_only:
        print("note: --materialize-only ignores --per-source")
    CONTEXT_CHAR_BUDGET = args.context_char_budget
    KEEP_RECENT_MESSAGES = args.keep_recent

    if args.per_source and not args.materialize_only:
        await run_per_source(args)
        return

    OV = AsyncHTTPClient(url=os.getenv("OPENVIKING_URL"), api_key=_OPENVIKING_KEY, timeout=args.timeout)
    await OV.initialize()
    try:
        run_dir = _new_run_dir()
        await ingest_once(args, run_dir=run_dir, ov=OV)
    finally:
        await OV.close()


if __name__ == "__main__":
    asyncio.run(main())
