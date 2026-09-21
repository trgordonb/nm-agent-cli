import os
import json
import sys
import time
import argparse
import asyncio
import functools
import logging
import math
import re
import uuid
import warnings

from typing import TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
import httpx
from openviking_sdk import AsyncHTTPClient
from langchain_openviking import OpenVikingCommitPolicy, OpenVikingPartialWriteError, OpenVikingSessionRecorder
from langchain_openviking.history import OpenVikingChatMessageHistory
from langchain_openviking.messages import OPENVIKING_CONTEXT_MARKER
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from tools import tools

# Filter LangChain deprecation warnings from langchain-openviking library
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_openviking")

load_dotenv()

_last_call_time = 0.0
_MIN_INTERVAL = 4.0 

# Initialize the LLM

model = ChatOpenAI(
    temperature=1.0,
    max_completion_tokens=16384,
    model="glm-5.3-flash",
    api_key=os.getenv("OPENAI_API_KEY",""), # type: ignore
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.z.ai/api/paas/v4/")
)

def _rate_limit_and_retry_wrapper(fn, max_attempts=5, backoff=2):
    """Wrap a method with manual rate limiting and retry logic for transient HTTP errors."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _last_call_time
        # Enforce minimum interval between calls
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < _MIN_INTERVAL:
            wait_time = _MIN_INTERVAL - elapsed
            logging.info(f"Rate limiter: waiting {wait_time:.1f}s before next call")
            time.sleep(wait_time)

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                _last_call_time = time.time()
                return fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    last_exc = e
                    wait = backoff ** attempt
                    logging.warning(f"Retry {attempt}/{max_attempts} after {wait}s: {err_str[:200]}")
                    time.sleep(wait)
                else:
                    raise
        raise last_exc # type: ignore
    return wrapper

def _async_rate_limit_and_retry_wrapper(fn, max_attempts=5, backoff=2):
    """Async wrap a method with manual rate limiting and retry logic for transient HTTP errors."""
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        global _last_call_time
        # Enforce minimum interval between calls
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < _MIN_INTERVAL:
            wait_time = _MIN_INTERVAL - elapsed
            logging.info(f"Rate limiter: waiting {wait_time:.1f}s before next call")
            await asyncio.sleep(wait_time)

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                _last_call_time = time.time()
                return await fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    last_exc = e
                    wait = backoff ** attempt
                    logging.warning(f"Retry {attempt}/{max_attempts} after {wait}s: {err_str[:200]}")
                    await asyncio.sleep(wait)
                else:
                    raise
        raise last_exc # type: ignore
    return wrapper

object.__setattr__(model, "invoke", _rate_limit_and_retry_wrapper(model.invoke))
object.__setattr__(model, "ainvoke", _async_rate_limit_and_retry_wrapper(model.ainvoke))

ov_client = AsyncHTTPClient(url=os.getenv("OPENVIKING_URL"), api_key=os.getenv("OPENVIKING_API_KEY"))
commit_policy = OpenVikingCommitPolicy(mode="pending_tokens", pending_token_threshold=4_000)
recorder = OpenVikingSessionRecorder(async_client=ov_client, commit_policy=commit_policy)

user = os.getenv("OPENVIKING_USER", "gordon")
session_id = str(uuid.uuid4())

_OPENVIKING_URL = (os.getenv("OPENVIKING_URL") or "http://localhost:1933").rstrip("/")
_context_http = httpx.AsyncClient(timeout=180.0)

_CONTEXT_QUOTAS: dict[str, int] = {
    "skills": 3,
    "resources": 2,
    "events": 0,
    "entities": 0,
    "preferences": 0,
    "experiences": 2,
}

_TRAJECTORY_DIR = "viking://user/gordon/memories/trajectories"
_TRAJECTORY_LIMIT = 3

_RESOURCE_MIN_RELEVANCE = float(os.getenv("OPENVIKING_RESOURCE_MIN_RELEVANCE", "0.55"))
_CONTEXT_SCORE_FLOOR = float(os.getenv("OPENVIKING_CONTEXT_SCORE_FLOOR", "-8.0"))

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _recall_query(text: str) -> str:
    return _URL_RE.sub(" ", text).strip()


def _context_part_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    category = entry.get("category") or ""
    return {
        "type": "context",
        "uri": entry.get("uri") or "",
        "context_type": {"skills": "skill", "resources": "resource"}.get(category, "memory"),
        "abstract": str(entry.get("text") or "")[:500],
    }


def _logit_relevance(logit: float) -> float:
    return 1.0 / (1.0 + math.exp(-logit))


def _filter_context_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for entry in entries:
        category = entry.get("category") or ""
        if category == "resources":
            relevance = _logit_relevance(float(entry.get("score") or 0.0))
            if relevance < _RESOURCE_MIN_RELEVANCE:
                logging.info(
                    f"OpenViking context dropped low-relevance resource "
                    f"{entry.get('uri')} (relevance={relevance:.2f})"
                )
                continue
        kept.append(entry)
    return kept


_ENTRY_TAGS = {"skills": "skill", "resources": "resource"}
_CONTEXT_ENVELOPE_RE = re.compile(r"</?(skill|resource|memory)(?=[\s/>])", re.IGNORECASE)


def _xml_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _xml_body(text: str) -> str:
    return _CONTEXT_ENVELOPE_RE.sub(r"<\\\1", text)


def _render_context_entry(entry: dict[str, Any]) -> str:
    category = entry.get("category") or ""
    tag = _ENTRY_TAGS.get(category, "memory")
    attrs = [
        f'uri="{_xml_attr(str(entry.get("uri") or ""))}"',
        f'score="{_logit_relevance(float(entry.get("score") or 0.0)):.3f}"',
        f'detail="{_xml_attr(str(entry.get("detail") or ""))}"',
    ]
    if tag == "memory":
        attrs.insert(1, f'type="{_xml_attr(category)}"')
    head = f"<{tag} " + " ".join(attrs)
    text = str(entry.get("text") or "")
    if not text.strip():
        return head + " />"
    return f"{head}>\n{_xml_body(text)}\n</{tag}>"


def _render_context_entries(entries: list[dict[str, Any]]) -> str:
    skills = [e for e in entries if (e.get("category") or "") == "skills"]
    rest = [e for e in entries if (e.get("category") or "") != "skills"]
    by_score = lambda e: float(e.get("score") or 0.0)
    skills.sort(key=by_score, reverse=True)
    rest.sort(key=by_score, reverse=True)
    return "\n".join(_render_context_entry(entry) for entry in [*skills, *rest])


async def _afind_trajectory_entries(query: str) -> list[dict[str, Any]]:
    """Fetch trajectory memories via scoped /find — bucketed context mode
    can never reach them (they own no quota bucket)."""
    try:
        response = await _context_http.post(
            f"{_OPENVIKING_URL}/api/v1/search/find",
            headers={"X-API-Key": os.getenv("OPENVIKING_API_KEY", "")},
            json={
                "query": _recall_query(query),
                "target_uri": _TRAJECTORY_DIR,
                "limit": _TRAJECTORY_LIMIT,
                "score_threshold": _CONTEXT_SCORE_FLOOR,
            },
        )
        body = response.json()
        if body.get("status") != "ok":
            raise RuntimeError(str(body.get("error"))[:300])
        hits = (body.get("result") or {}).get("memories") or []
    except Exception as exc:
        logging.warning(f"OpenViking trajectory find failed: {exc}")
        return []
    entries: list[dict[str, Any]] = []
    for hit in hits:
        uri = str(hit.get("uri") or "")
        if not uri:
            continue
        entries.append(
            {
                "uri": uri,
                "category": "memories",
                "score": float(hit.get("score") or 0.0),
                "detail": "abstract",
                "text": str(hit.get("abstract") or hit.get("overview") or ""),
            }
        )
    return entries


async def aassemble_openviking_context(session_id: str, query: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        response = await _context_http.post(
            f"{_OPENVIKING_URL}/api/v1/search/search",
            headers={"X-API-Key": os.getenv("OPENVIKING_API_KEY", "")},
            json={
                "query": _recall_query(query),
                "mode": "context",
                "session_id": session_id,
                "quotas": _CONTEXT_QUOTAS,
                "max_tokens": 6000,
                "limit": 15,
                "dedup_turns": 0,
                "rewrite": False,
                "score_threshold": _CONTEXT_SCORE_FLOOR,
                "detail": {"skills": "overview", "experiences": "full", "memories": "abstract"},
            },
        )
        body = response.json()
        if body.get("status") != "ok":
            raise RuntimeError(str(body.get("error"))[:300])
        result = body.get("result") or {}
    except Exception as exc:
        logging.warning(f"OpenViking context assembly failed: {exc}")
        return "", [], {} # type: ignore

    entries = _filter_context_entries(result.get("entries") or [])
    trajectory_entries = await _afind_trajectory_entries(query)
    existing_uris = {entry.get("uri") for entry in entries}
    entries.extend(e for e in trajectory_entries if e["uri"] not in existing_uris)
    if not entries:
        return "", [], {}
    return (
        f"{OPENVIKING_CONTEXT_MARKER}\n{_render_context_entries(entries)}\n</openviking_context>",
        [_context_part_from_entry(entry) for entry in entries],
        body,
    ) # type: ignore


async def afetch_retrieval_observer() -> dict[str, Any]:
    """Read /observer/retrieval — retrieval quality and timing metrics."""
    try:
        response = await _context_http.get(
            f"{_OPENVIKING_URL}/api/v1/observer/retrieval",
            headers={"X-API-Key": os.getenv("OPENVIKING_API_KEY", "")},
        )
        return (response.json().get("result") or {})
    except Exception as exc:
        logging.warning(f"Retrieval observer fetch failed: {exc}")
        return {}


async def abench_context_latency(query: str, runs: int = 1, sample_delay: float = 1.0) -> None:
    """Measure aassemble_openviking_context end-to-end latency.

    Each iteration times a full context-assembly call, then reads the
    server-side /observer/retrieval metrics so client and server views can be
    compared. The observer table covers the last N retrieval queries; the last
    rows correspond to these runs.
    """
    await ov_client.initialize()
    print(f"Benchmarking context assembly ({runs} run(s)) for query:\n  {query!r}\n")
    latencies: list[float] = []
    for run in range(1, runs + 1):
        start = asyncio.get_running_loop().time()
        block, parts, body = await aassemble_openviking_context(session_id, query) # type: ignore
        elapsed = asyncio.get_running_loop().time() - start
        latencies.append(elapsed)
        result = body.get("result") or {}
        stats = result.get("stats") or {}
        print(f"Run {run}: client latency {elapsed * 1000:.1f} ms | "
              f"server time {float(body.get('time') or 0.0) * 1000:.1f} ms | "
              f"entries {len(parts)} | block {len(block)} chars | "
              f"stats {json.dumps(stats) if isinstance(stats, dict) else stats}")
        if block:
            print(f"  abstracts: {[str(e.get('text') or '')[:60] + '...' for e in result.get('entries') or []][:3]}")
        # Give the observer a moment to record the retrieval before reading it
        await asyncio.sleep(sample_delay)
        observer = await afetch_retrieval_observer()
        status_text = str(observer.get("status") or "").strip().splitlines()
        print("  observer/retrieval: " + ("healthy" if observer.get("is_healthy") else "unavailable"))
        for line in status_text[-6:]:
            print(f"    {line}")
        print()
    if len(latencies) > 1:
        lat_sorted = sorted(latencies)
        mean = sum(latencies) / len(latencies)
        med = (lat_sorted[(len(lat_sorted) - 1) // 2] + lat_sorted[len(lat_sorted) // 2]) / 2
        print(f"Summary over {len(latencies)} runs: mean {mean * 1000:.1f} ms | "
              f"median {med * 1000:.1f} ms | min {lat_sorted[0] * 1000:.1f} ms | "
              f"max {lat_sorted[-1] * 1000:.1f} ms")

_FINANCETOOLKIT_URL = "https://financetoolkit.jeroenbouma.com/mcp"

_MCP_KEEP_TOOLS = frozenset({
    "breadth",
    "discovery",
    "market_data",
    "models",
    "momentum",
    "overlap",
    "rates",
    "risk",
    "volatility",
    "search_categories",
    "search_by_category",
    "search_metrics",
    "search_instruments",
})


async def _load_mcp_tools() -> list:
    fmp_key = os.getenv("FINANCIAL_MODELING_PREP_API_KEY", "")
    if not fmp_key:
        raise RuntimeError("FINANCIAL_MODELING_PREP_API_KEY is not set (required for the Finance Toolkit MCP server).")
    mcp_client = MultiServerMCPClient(
        {
            "finance_toolkit": {
                "transport": "streamable_http",
                "url": _FINANCETOOLKIT_URL,
                "headers": {"Authorization": f"Bearer {fmp_key}"},
            }
        }
    )
    try:
        all_mcp_tools = await mcp_client.get_tools()
    except Exception as e:
        logging.warning(f"Finance Toolkit MCP connection failed, continuing without MCP tools: {str(e)[:300]}")
        return []
    kept = [t for t in all_mcp_tools if t.name in _MCP_KEEP_TOOLS]
    filtered = [t.name for t in all_mcp_tools if t.name not in _MCP_KEEP_TOOLS]
    if filtered:
        logging.info(f"Finance Toolkit MCP: bound {len(kept)} tools, filtered out: {filtered}")
    return kept


# Define the agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    openviking_context: str


def build_agent(all_tools: list) -> Any:
    # Create tool node
    tool_node = ToolNode(all_tools)
    model_with_tools = model.bind_tools(all_tools)

    def should_continue(state: AgentState) -> str:
        messages = state["messages"]
        last_message = messages[-1]

        # Check if last tool execution failed
        if isinstance(last_message, ToolMessage) and last_message.content.startswith("Error:"): # type: ignore
            return END

        if last_message.tool_calls: # type: ignore
            return "execute_tool"
        return END

    async def execute_tool_with_error_handling(state: AgentState):
        """Execute tools with error handling and retry logic for failures."""
        max_attempts = 3
        backoff = 2
        last_exc = None
    
        for attempt in range(1, max_attempts + 1):
            try:
                result = await tool_node.ainvoke(state)
                return result
            except Exception as e:
                err_str = str(e)
                last_exc = e
                # Retry on timeout, connection, and socket errors
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    wait = backoff ** attempt
                    logging.warning(f"Tool execution retry {attempt}/{max_attempts} after {wait}s: {err_str[:200]}")
                    await asyncio.sleep(wait)
                else:
                    # For non-retryable errors, fail immediately
                    error_message = ToolMessage(
                        content=f"Tool execution failed: {str(e)}",
                        tool_call_id=state["messages"][-1].tool_calls[0]["id"] if state["messages"][-1].tool_calls else "unknown" # type: ignore
                    )
                    return {"messages": [error_message]}
    
        # If all retries failed, return error
        error_message = ToolMessage(
            content=f"Tool execution failed after {max_attempts} attempts: {str(last_exc)}",
            tool_call_id=state["messages"][-1].tool_calls[0]["id"] if state["messages"][-1].tool_calls else "unknown" # type: ignore
        )
        return {"messages": [error_message]}
 
    async def call_model(state: AgentState):
        system_prompt = (
            "You are an adaptable AI agent. "
            "Tools with name starting with viking_ are from OpenViking API.\n"
            "Use them to access resources and skills when given an explicit uri starting with viking://\n"
            "If any skill file references other files, assume those files can be accessed using the same base URI\n"
            "NEVER use viking_read to access a url starting with https, use web_to_markdown_tool instead\n"
            "\n"
            "SKILL WORKFLOW (MANDATORY):\n"
            "The OpenViking context below may contain <skill> entries. Each <skill> entry is a set of "
            "step-by-step instructions for exactly the kind of task its description matches; the body "
            "shown in the context is only an abstract. If ANY <skill> entry is relevant to the user's request:\n"
            "1. FIRST call viking_read on that skill's uri to load the full instructions.\n"
            "2. Follow those instructions exactly, using whatever tools they specify.\n"
            "3. While a matching skill exists, do NOT use internet_search or web_to_markdown_tool directly; "
            "use the search/fetch procedure the skill prescribes instead.\n"
            "Call internet_search directly ONLY when no <skill> in the context matches the request, "
            "or after the loaded skill explicitly tells you to fall back.\n"
        )

        context_block = state.get("openviking_context") or ""
        if context_block:
            system_prompt = (
                f"{system_prompt}\n\n{context_block}\n\n"
                "Reminder: if any <skill> above matches the user's request, call viking_read "
                "on its uri and follow the loaded instructions before any other tool call."
            )

        # Inject system prompt into messages
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"]) # type: ignore

        # Add retry logic for the main LLM call
        max_attempts = 3
        backoff = 2
        last_exc = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = await model_with_tools.ainvoke(messages)
                return {"messages": [response]}
            except Exception as e:
                err_str = str(e)
                last_exc = e
                # Retry on timeout, connection, and socket errors
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    wait = backoff ** attempt
                    logging.warning(f"LLM call retry {attempt}/{max_attempts} after {wait}s: {err_str[:200]}")
                    await asyncio.sleep(wait)
                else:
                    # For non-retryable errors, fail immediately
                    raise
    
        # If all retries failed, raise the last exception
        raise last_exc # type: ignore


    # Build the graph
    workflow = StateGraph(AgentState)
    # Add Nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("execute_tool", execute_tool_with_error_handling)

    # Define Relationships
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "execute_tool": "execute_tool",
            END: END
        }
    )
    workflow.add_edge("execute_tool", "agent")
    app = workflow.compile()
    return app

# CLI interface
async def _load_archived_history(sid: str) -> list[BaseMessage]:
    """Rebuild history from committed OpenViking archives when the session has no active messages."""
    messages: list[BaseMessage] = []
    for index in range(1, 1000):
        try:
            result = await ov_client.get_session_archive(sid, f"archive_{index:03d}")
        except Exception:
            break
        for raw in result.get("messages") or []:
            text = "\n".join(
                part.get("text", "")
                for part in raw.get("parts") or []
                if part.get("type") == "text"
            ).strip()
            if not text:
                continue
            if raw.get("role") == "assistant":
                messages.append(AIMessage(content=text))
            elif raw.get("role") == "user":
                messages.append(HumanMessage(content=text))
    return messages


async def _commit_on_exit(session_id: str) -> None:
    """Commit any pending session content before the CLI exits.

    recorder.aclose() discards pending-commit bookkeeping without committing,
    so this is the last chance to roll uncommitted turns into a searchable
    archive (and trigger Working Memory / overview generation server-side).
    """
    try:
        result = await recorder.aflush(session_id)
        if result:
            print(f"Session {session_id} committed on exit.")
        else:
            print("Session already committed (nothing pending).")
    except Exception as exc:
        print(f"Warning: failed to commit session on exit: {str(exc)[:200]}")


async def run_cli(resume_session_id: str | None = None):
    await ov_client.initialize()
    global session_id

    #mcp_tools = await _load_mcp_tools()
    #if mcp_tools:
    #    print(f"Connected to Finance Toolkit MCP ({len(mcp_tools)} tools)")
    all_tools = [*tools]
    app = build_agent(all_tools)

    print("LangGraph Agent CLI (type 'quit' to exit)")
    print("=" * 50)
    print(f"\nHello {user}\n")
    print(f"Session ID: {session_id} (pass --session-id to resume)\n")
    messages = []

    if resume_session_id:
        session_id = resume_session_id
        history = OpenVikingChatMessageHistory(session_id, _recorder=recorder)
        messages = await history.aget_messages()
        source = "active session history"
        if not messages:
            # Committed/pending sessions roll their turns into archives, so
            # active messages can be empty even though history exists.
            messages = await _load_archived_history(session_id)
            source = "committed archives"
        print(
            f"Resumed session {session_id} ({len(messages)} messages from {source})\n"
        )


    
    while True:
        try:
            user_input = input(f"\n{user}: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Assemble OpenViking context once per user turn
            context_block, context_parts, _context_body = await aassemble_openviking_context(session_id, user_input) # type: ignore
            
            # Add user message
            messages.append(HumanMessage(content=user_input))
            input_message_count = len(messages)
            
            # Run the agent
            print("\nAgent:\n", end="", flush=True)
            
            final_state = None
            prev_count = input_message_count
            async for state_snapshot in app.astream(
                {"messages": messages, "openviking_context": context_block},
                stream_mode="values",
            ):
                final_state = state_snapshot
                snapshot_messages = state_snapshot["messages"]
                for msg in snapshot_messages[prev_count:]:
                    if isinstance(msg, AIMessage):
                        if msg.content:
                            print(msg.content)
                        elif msg.tool_calls:
                            print(f"[Calling tools: {[call['name'] + ' ' + str(call['args']) for call in msg.tool_calls]}]")
                    elif isinstance(msg, ToolMessage):
                        print(f"[Tool result: {msg.name}]")
                prev_count = len(snapshot_messages)
            
            # Update messages with final state
            if final_state and "messages" in final_state:
                messages = final_state["messages"]
                new_messages = messages[input_message_count - 1:]
                # Commit the session
                try:
                    try:
                        await recorder.arecord(
                            session_id,
                            new_messages,
                            context_parts=context_parts,
                        )
                    except OpenVikingPartialWriteError as exc:
                        await recorder.arecord(
                            session_id,
                            new_messages[exc.input_messages_consumed :],
                        )
                finally:
                    # Flush even when recording partially failed, so whatever
                    # reached the server still gets committed this turn.
                    try:
                        await recorder.aflush(session_id)
                    except Exception as flush_exc:
                        logging.warning(f"Session flush failed: {str(flush_exc)[:200]}")
    
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
        except Exception as e:
            print(f"\nError: {str(e)}")
            messages = messages[:-1] if messages else []

    await _commit_on_exit(session_id)
    await _context_http.aclose()
    await recorder.aclose()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph agent CLI with OpenViking session persistence")
    parser.add_argument(
        "--session-id",
        help="Resume an existing OpenViking session by loading its recorded history",
    )
    parser.add_argument(
        "--bench-context",
        metavar="QUERY",
        help="Benchmark context-assembly latency for QUERY and report server-side retrieval metrics",
    )
    parser.add_argument(
        "--bench-runs",
        type=int,
        default=1,
        help="Number of benchmark iterations (default: 1)",
    )
    args = parser.parse_args()
    if args.bench_context:
        asyncio.run(abench_context_latency(args.bench_context, max(1, args.bench_runs)))
    else:
        asyncio.run(run_cli(args.session_id))
