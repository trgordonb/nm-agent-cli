"""FastAPI server exposing the NM-Agent-CLI LangGraph agent over HTTP.

Same turn semantics as the interactive CLI (main.py): per-turn wiki recall,
pre-turn context compression, tool streaming, session archiving, memory
nudges — plus turn-level cancel (CLI Ctrl+C equivalent, with partial turns
persisted up to the last complete tool-call group).

Endpoints:
    GET  /api/health            banner-equivalent status (no model calls)
    GET  /api/sessions          archived sessions (SessionStore.list_sessions)
    GET  /api/sessions/{sid}    full message history (resumable)
    GET  /api/skills            skills index
    /wapi/api/*                 in-process wiki engine (wiki_engine/, port-free)
    POST /api/chat              one agent turn as an SSE event stream
    POST /api/chat/cancel       abort an active turn ({turn_id})

Run:
    uv run uvicorn server:app --port 8000
    uv run python server.py      # same, honours SERVER_PORT

SSE events (one `event:` + `data:` pair each):
    session      {session_id, turn_id, resumed}
    wiki         {pages}                     — pages recalled into this turn
    compression  {first, last, model, ...}   — pre-turn compression fired
    message      {type, role, content, tool_calls?, tool_call_id?, tool_name?, status?}
    nudge        {summary}                   — memory nudge ran post-turn
    cancelled    {turn_id, persisted}        — turn aborted, partial state saved
    done         {session_id, messages}
    error        {error}
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

import main as agent
from wiki_engine import (
    create_wiki_router,
    get_engine as get_wiki_engine,
    reset_engine as reset_wiki_engine,
)
from main import assemble_agent_runtime

# --- shared runtime (lazy: graph + MCP tools assemble on first chat) ---------

_runtime: dict | None = None
_runtime_lock = asyncio.Lock()

# Active turns: turn_id -> cancel event (set by POST /api/chat/cancel)
ACTIVE_TURNS: dict[str, asyncio.Event] = {}


async def get_runtime() -> dict:
    global _runtime
    if _runtime is None:
        async with _runtime_lock:
            if _runtime is None:
                _runtime = await assemble_agent_runtime()
    return _runtime


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The Python wiki engine indexes at startup (fast for personal vaults);
    # an unconfigured vault must not crash the boot — routes 409 instead.
    try:
        get_wiki_engine().ensure_ready()
    except Exception as exc:  # noqa: BLE001
        agent.logging.warning(f"wiki engine startup deferred: {str(exc)[:200]}")
    yield  # the runtime assembles lazily; the store outlives the server
    reset_wiki_engine()


app = FastAPI(title="NM-Agent-CLI", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-first tool; the UI may run on any dev port
    allow_methods=["*"],
    allow_headers=["*"],
)

_ROLE_BY_TYPE = {"human": "user", "ai": "assistant", "tool": "tool"}


def serialize_message(msg: BaseMessage) -> dict[str, Any]:
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    out: dict[str, Any] = {
        "type": msg.type,
        "role": _ROLE_BY_TYPE.get(msg.type, msg.type),
        "content": content,
    }
    if isinstance(msg, AIMessage) and msg.tool_calls:
        out["tool_calls"] = [
            {"id": c.get("id"), "name": c.get("name"), "args": c.get("args")}
            for c in msg.tool_calls
        ]
    if isinstance(msg, ToolMessage):
        out["tool_call_id"] = msg.tool_call_id
        out["tool_name"] = msg.name
        out["status"] = getattr(msg, "status", None)
    return out


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _valid_prefix_len(new_messages: list[BaseMessage]) -> int:
    """Longest prefix of a partial turn that is safe to archive.

    Every AIMessage tool_call must be answered by a ToolMessage before the
    next AIMessage; an incomplete group (cancel mid-tool) is dropped, because
    a provider rejects histories with unanswered tool_call ids. The leading
    human message is always valid on its own.
    """
    valid = 0
    pending: set[str] = set()
    for i, msg in enumerate(new_messages):
        if isinstance(msg, AIMessage):
            if pending:
                break
            pending = {c["id"] for c in (msg.tool_calls or []) if c.get("id")}
            if not pending:
                valid = i + 1
        elif isinstance(msg, ToolMessage):
            if msg.tool_call_id not in pending:
                break
            pending.discard(msg.tool_call_id)
            if not pending:
                valid = i + 1
        else:
            if pending:
                break
            valid = i + 1
    return valid


# --- read endpoints -----------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": agent.model.model_name,
        "memory_chars": agent.memory.total_chars(),
        "skills": len(agent.skill_library.list_skills()),
        "wiki_available": agent.WikiStore().available(),
        "mcp_tools": len(_runtime["mcp_tools"]) if _runtime else 0,
        "assembled": _runtime is not None,
        "time": agent.time.time(),
    }


@app.get("/api/sessions")
def list_sessions() -> list[dict]:
    return agent.store.list_sessions()


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    messages = agent.store.load_session(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail=f"session not found: {session_id}")
    return {"session_id": session_id, "messages": [serialize_message(m) for m in messages]}


class SkillEnabledRequest(BaseModel):
    enabled: bool


@app.get("/api/skills")
def list_skills() -> list:
    """Admin view: every skill with its enabled state (Hermes-style toggles)."""
    return agent.skill_library.list_all()


@app.post("/api/skills/{name:path}/enabled")
def set_skill_enabled(name: str, req: SkillEnabledRequest) -> dict:
    """Enable/disable a skill. Takes full effect on the next session (the
    index is injected once per session; the nudge re-render is the only
    mid-session path)."""
    result = agent.skill_library.set_enabled(name, req.enabled)
    if result.startswith("Rejected"):
        raise HTTPException(status_code=404, detail=result)
    if result.startswith("ERROR"):
        raise HTTPException(status_code=409, detail=result)
    return {"status": result}


# --- wiki surface (/wapi) ------------------------------------------------------
# The in-process Python engine (wiki_engine/) serves /wapi/api/* with the same
# contract the React UI has always consumed. (The legacy wiki-os Node engine
# this replaced is archived at workspace/wiki-archive/ and on GitHub as
# trgordonb/wiki-os; the port preserves its bare-wikilink resolution patch.)

app.include_router(create_wiki_router(get_wiki_engine()))


# --- chat (SSE) + turn cancel -------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class CancelRequest(BaseModel):
    turn_id: str


@app.post("/api/chat/cancel")
async def cancel_turn(req: CancelRequest) -> dict:
    event = ACTIVE_TURNS.get(req.turn_id)
    if event is None:
        return {"cancelled": False, "detail": "turn not active (already finished?)"}
    event.set()
    return {"cancelled": True}


async def _event_stream(req: ChatRequest) -> AsyncIterator[str]:
    runtime = await get_runtime()
    graph, wiki = runtime["graph"], runtime["wiki"]

    turn_id = uuid.uuid4().hex
    cancel_event = asyncio.Event()
    ACTIVE_TURNS[turn_id] = cancel_event

    session_id = req.session_id or agent.store.new_session_id()
    history = agent.store.load_session(session_id)
    resumed = bool(history)
    yield _sse("session", {"session_id": session_id, "turn_id": turn_id, "resumed": resumed})
    messages = history

    # Pre-turn context compression (Hermes-style), same policy as the CLI.
    if agent.context_compressor and messages:
        try:
            cres = await asyncio.to_thread(agent.context_compressor.compress, messages)
            if cres.compressed:
                agent.store.record_compression(
                    session_id,
                    summary=cres.summary,
                    summarized_first_turn=cres.summarized_first_turn,
                    summarized_last_turn=cres.summarized_last_turn,
                    message_count=cres.original_count,
                    model=cres.model_label,
                )
                messages = cres.compressed_messages
                yield _sse("compression", {
                    "first": cres.summarized_first_turn,
                    "last": cres.summarized_last_turn,
                    "original": cres.original_count,
                    "compressed": cres.compressed_count,
                    "model": cres.model_label,
                })
        except Exception as exc:
            agent.logging.warning(f"Context compression failed: {str(exc)[:200]}")

    messages.append(HumanMessage(content=req.message))
    input_message_count = len(messages)

    # Pre-flight wiki recall for this turn (never archived).
    wiki_context = wiki.build_context(req.message) if wiki.available() else ""
    state_input: dict[str, Any] = {"messages": messages}
    if wiki_context:
        state_input["wiki_context"] = wiki_context
        yield _sse("wiki", {"pages": wiki_context.count("<page path=")})

    # Drive the graph in a task so cancel can interrupt it mid-node, with
    # snapshots relayed through a queue (values mode, same as the CLI).
    queue: asyncio.Queue = asyncio.Queue()

    async def run_graph() -> None:
        try:
            async for snapshot in graph.astream(state_input, stream_mode="values"):
                await queue.put({"snapshot": snapshot})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await queue.put({"error": str(exc)[:400]})
        finally:
            await queue.put(None)

    task = asyncio.create_task(run_graph())
    last_snapshot: dict | None = None
    errored: str | None = None
    cancelled = False
    persisted = 0
    final_new_messages: list[BaseMessage] | None = None
    final_total = input_message_count
    prev_count = input_message_count

    try:
        while True:
            getter = asyncio.create_task(queue.get())
            waiter = asyncio.create_task(cancel_event.wait())
            done, _ = await asyncio.wait({getter, waiter}, return_when=asyncio.FIRST_COMPLETED)
            waiter.cancel()
            if waiter in done:
                cancelled = True
                getter.cancel()
                task.cancel()
                break
            item = getter.result()
            if item is None:
                break
            if "error" in item:
                errored = item["error"]
                break
            snapshot = item["snapshot"]
            last_snapshot = snapshot
            snapshot_messages = snapshot["messages"]
            for msg in snapshot_messages[prev_count:]:
                yield _sse("message", serialize_message(msg))
            prev_count = len(snapshot_messages)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        ACTIVE_TURNS.pop(turn_id, None)
        if last_snapshot is not None:
            snapshot_messages = last_snapshot["messages"]
            final_total = len(snapshot_messages)
            new_messages = snapshot_messages[input_message_count - 1:]
            valid = _valid_prefix_len(new_messages)
            if valid >= 2:  # human message + at least one completed response step
                final_new_messages = new_messages[:valid]
                persisted = await asyncio.to_thread(
                    agent.store.record_turn,
                    session_id,
                    final_new_messages,
                )

    if errored:
        yield _sse("error", {"error": errored})
        return
    if cancelled:
        yield _sse("cancelled", {"turn_id": turn_id, "persisted_turns": persisted})
    else:
        if final_new_messages:
            nudge_summary = await agent.maybe_nudge(session_id, final_new_messages)
            if nudge_summary:
                yield _sse("nudge", {"summary": nudge_summary})
    yield _sse("done", {"session_id": session_id, "messages": final_total})


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    # SERVER_HOST=0.0.0.0 exposes the server (agent API + in-process wiki
    # engine) to Tailscale/phone clients; localhost-only by default.
    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
    )
