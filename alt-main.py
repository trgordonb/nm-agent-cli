import os
import time
import argparse
import asyncio
import functools
import logging
import uuid

from typing import TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from tools import tools
from nm_memory_layer import (
    DEFAULT_NUDGE_INTERVAL,
    MEMORY_CHAR_LIMIT,
    NudgePolicy,
    PromptMemory,
    SessionStore,
    SkillLibrary,
    build_nudge_prompt,
    create_load_skill_tool,
    create_memory_manage_tool,
    create_openrouter_compressor,
    create_openrouter_summarizer,
    create_session_search_tool,
    create_skill_manage_tool,
    flatten_transcript,
)

# override=True: .env is the source of truth for this project. Without it,
# dotenv will NOT replace variables already exported in the shell (e.g. an
# OPENAI_BASE_URL exported in ~/.bashrc silently wins and redirects the LLM).
load_dotenv(override=True)

# --- Logging -----------------------------------------------------------------
# INFO shows: every LLM call attempt (model + base_url), retry decisions, and —
# via the httpx logger — the actual request line of every HTTP call made by the
# process (e.g. "HTTP Request: POST https://api.z.ai/api/paas/v4/chat/completions
# HTTP/1.1 200 OK"), which is how we verify which endpoint is really hit.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,  # imported libs may pre-add root handlers, making plain basicConfig a no-op
)
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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


def _endpoint_hint(fn) -> str:
    """Describe which model/endpoint a wrapped LLM method points at."""
    target = getattr(fn, "__self__", None)
    if target is None:
        return "target=?"
    base_url = getattr(target, "openai_api_base", None) or getattr(target, "base_url", "")
    model_name = getattr(target, "model_name", None) or getattr(target, "model", "")
    return f"model={model_name} base_url={base_url}"


def _error_hint(exc: Exception) -> str:
    """Extract status + request URL from an SDK/httpx exception when present."""
    url = getattr(getattr(exc, "request", None), "url", "")
    status = getattr(exc, "status_code", "")
    return f"{type(exc).__name__}{f' status={status}' if status != '' else ''}{f' url={url}' if url else ''}"

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
                logging.info(f"LLM call (sync) attempt {attempt}/{max_attempts} [{_endpoint_hint(fn)}]")
                _last_call_time = time.time()
                return fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    last_exc = e
                    wait = backoff ** attempt
                    logging.warning(f"LLM retry {attempt}/{max_attempts} after {wait}s: {_error_hint(e)}: {err_str[:200]}")
                    time.sleep(wait)
                else:
                    logging.error(f"LLM call failed (non-retryable) [{_endpoint_hint(fn)}]: {_error_hint(e)}: {err_str[:300]}")
                    raise
        logging.error(f"LLM call failed after {max_attempts} attempts [{_endpoint_hint(fn)}]: {_error_hint(last_exc) if last_exc else ''}")
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
                logging.info(f"LLM call (async) attempt {attempt}/{max_attempts} [{_endpoint_hint(fn)}]")
                _last_call_time = time.time()
                return await fn(*args, **kwargs)
            except Exception as e:
                err_str = str(e)
                if any(code in err_str for code in ("500", "502", "503", "504", "Connection", "Timeout", "429", "rate", "socket", "timeout")):
                    last_exc = e
                    wait = backoff ** attempt
                    logging.warning(f"LLM retry {attempt}/{max_attempts} after {wait}s: {_error_hint(e)}: {err_str[:200]}")
                    await asyncio.sleep(wait)
                else:
                    logging.error(f"LLM call failed (non-retryable) [{_endpoint_hint(fn)}]: {_error_hint(e)}: {err_str[:300]}")
                    raise
        logging.error(f"LLM call failed after {max_attempts} attempts [{_endpoint_hint(fn)}]: {_error_hint(last_exc) if last_exc else ''}")
        raise last_exc # type: ignore
    return wrapper

object.__setattr__(model, "invoke", _rate_limit_and_retry_wrapper(model.invoke))
object.__setattr__(model, "ainvoke", _async_rate_limit_and_retry_wrapper(model.ainvoke))

user = os.getenv("OPENVIKING_USER", "gordon")
session_id = str(uuid.uuid4())

store = SessionStore()
search_summarizer = create_openrouter_summarizer()
session_search_tool = create_session_search_tool(store, summarizer=search_summarizer)

memory = PromptMemory()
memory_manage_tool = create_memory_manage_tool(memory)

nudge_policy = NudgePolicy(interval=int(os.getenv("NUDGE_INTERVAL", str(DEFAULT_NUDGE_INTERVAL))))

skill_library = SkillLibrary()
skill_manage_tool = create_skill_manage_tool(skill_library)
load_skill_tool = create_load_skill_tool(skill_library)

context_compressor = create_openrouter_compressor()

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


def build_agent(all_tools: list, memory_block: str = "", skill_index: str = "") -> Any:
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
            "You are an adaptable AI agent.\n"
            "\n"
            "SESSION MEMORY (episodic, on-demand):\n"
            "session_search queries your archived past sessions. Call it BEFORE redoing work "
            "when the user's request may relate to something from a previous conversation — "
            "prior decisions, findings, errors and their fixes, or procedures you already "
            "worked out. It returns short excerpts, not full transcripts, so it is cheap to consult.\n"
            "\n"
            "PROMPT MEMORY (always-on, self-curated):\n"
            "memory_manage edits your MEMORY.md (facts/decisions relevant to EVERY future "
            "session) and USER.md (who the user is, preferences, working style). Combined "
            f"budget: {MEMORY_CHAR_LIMIT} chars — keep entries terse, consolidate instead of accumulating. "
            "Do NOT store topic-specific findings there; leave those to the session archive. "
            "Memory edits take effect from the NEXT session, never mid-conversation.\n"
            "\n"
            "SKILLS (procedural memory, on demand):\n"
            "The skills index below lists names + descriptions ONLY. If a listed skill "
            "matches the task, call load_skill(name) FIRST and follow its loaded "
            "instructions before falling back to generic approaches. You can curate "
            "skills with skill_manage (create/patch/edit/delete/write_file/remove_file); "
            "PREFER patch for updates — targeted and safe, unlike full rewrites.\n"
        )

        if memory_block:
            system_prompt = f"{system_prompt}\n{memory_block}\n"
        if skill_index:
            system_prompt = f"{system_prompt}\n{skill_index}\n"

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

# --- Periodic nudge: the learning loop's curation step (Hermes-style) ---

async def run_memory_nudge(recent_messages: list[BaseMessage], nudge_model=None, max_iters: int = 3) -> str:
    """Run one internal curation review over a completed turn (no user input).

    The nudge model sees the turn as a flattened transcript and may call
    memory_manage several times; its writes take effect from the next session.
    Nudge activity is deliberately NOT written to the session archive.
    """
    if not recent_messages:
        return "No memory updates."
    bound = nudge_model if nudge_model is not None else model.bind_tools([memory_manage_tool, skill_manage_tool])
    convo = [
        SystemMessage(content=build_nudge_prompt(chars_used=memory.total_chars(), char_budget=MEMORY_CHAR_LIMIT)),
        SystemMessage(content=f"Current memory contents:\n{memory.load() or '(empty)'}"),
        SystemMessage(content=f"Current skills index:\n{skill_library.render_index() or '(none)'}"),
        HumanMessage(
            content=(
                "RECENT CONVERSATION TURN:\n\n"
                f"{flatten_transcript(recent_messages)}\n\n"
                "Review it now and persist anything that clears the bar."
            )
        ),
    ]
    for _ in range(max_iters):
        response = await bound.ainvoke(convo)
        if not getattr(response, "tool_calls", None):
            return (response.content or "No memory updates.").strip()[:200] or "No memory updates."
        convo.append(response)
        for call in response.tool_calls:
            if call["name"] == "memory_manage":
                result = memory_manage_tool.invoke(dict(call["args"]))
            elif call["name"] == "skill_manage":
                result = skill_manage_tool.invoke(dict(call["args"]))
            else:
                result = f"Rejected: unknown tool {call['name']!r} during nudge"
            convo.append(ToolMessage(content=result, tool_call_id=call.get("id") or "nudge"))
    return "Nudge reached its tool-call limit."


async def maybe_nudge(session_id: str, new_messages: list[BaseMessage], nudge_model=None, max_iters: int = 3) -> str | None:
    """Post-turn bookkeeping: count the turn and run the nudge when due."""
    nudge_policy.record_turn(session_id)
    if not nudge_policy.should_nudge(session_id):
        return None
    nudge_policy.mark_nudged(session_id)
    return await run_memory_nudge(new_messages, nudge_model=nudge_model, max_iters=max_iters)


# CLI interface
async def run_cli(resume_session_id: str | None = None):
    global session_id

    #mcp_tools = await _load_mcp_tools()
    #if mcp_tools:
    #    print(f"Connected to Finance Toolkit MCP ({len(mcp_tools)} tools)")
    # Drop OpenViking tools (shared tools.py) — the local memory layer replaces them.
    all_tools = [t for t in tools if not t.name.startswith("viking_")] + [
        session_search_tool,
        memory_manage_tool,
        skill_manage_tool,
        load_skill_tool,
    ]
    # Load the always-on memory block and the skills index once per session:
    # stable prompt prefix (provider prompt-cache friendly); edits and new
    # skills apply from the next session.
    memory_block = memory.load()
    skill_index = skill_library.render_index()
    app = build_agent(all_tools, memory_block, skill_index)

    print("LangGraph Agent CLI (nm-memory-layer: sessions + prompt memory + skills)")
    print("=" * 50)
    print(f"\nHello {user}\n")
    print(f"Memory: {memory.total_chars()}/{MEMORY_CHAR_LIMIT} chars | Skills: {len(skill_library.list_skills())}")
    print(f"Search summarizer: {search_summarizer.label if search_summarizer else 'disabled (raw excerpts)'}")
    print(f"Context compressor: {context_compressor.label if context_compressor else 'disabled'}\n")
    print(f"Session ID: {session_id} (pass --session-id to resume)\n")
    messages = []

    if resume_session_id:
        session_id = resume_session_id
        messages = store.load_session(session_id)
        if messages:
            print(f"Resumed session {session_id} ({len(messages)} messages from local archive)\n")
        else:
            print(f"Session {session_id} not found in archive — starting fresh.\n")

    try:
        while True:
            try:
                user_input = input(f"\n{user}: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                if not user_input:
                    continue

                # Pre-flight context compression (Hermes-style): before hitting
                # the token threshold, middle turns are summarized via the
                # secondary LLM and lineage is recorded in the session store.
                if context_compressor:
                    try:
                        cres = await asyncio.to_thread(context_compressor.compress, messages)
                        if cres.compressed:
                            store.record_compression(
                                session_id,
                                summary=cres.summary,
                                summarized_first_turn=cres.summarized_first_turn,
                                summarized_last_turn=cres.summarized_last_turn,
                                message_count=cres.original_count,
                                model=cres.model_label,
                            )
                            messages = cres.compressed_messages
                            print(
                                f"\n[context compression] turns {cres.summarized_first_turn}-"
                                f"{cres.summarized_last_turn} summarized by {cres.model_label} "
                                f"({cres.original_count} -> {cres.compressed_count} messages, {cres.elapsed_ms}ms)"
                            )
                    except Exception as comp_exc:
                        logging.warning(f"Context compression failed: {str(comp_exc)[:200]}")

                # Add user message
                messages.append(HumanMessage(content=user_input))
                input_message_count = len(messages)

                # Run the agent
                print("\nAgent:\n", end="", flush=True)

                final_state = None
                prev_count = input_message_count
                async for state_snapshot in app.astream(
                    {"messages": messages},
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

                # Update messages with final state and persist the turn locally
                if final_state and "messages" in final_state:
                    messages = final_state["messages"]
                    new_messages = messages[input_message_count - 1:]
                    try:
                        turn = store.record_turn(session_id, new_messages)
                        logging.debug(f"Recorded turn {turn} ({len(new_messages)} messages)")
                    except Exception as record_exc:
                        logging.warning(f"Session record failed: {str(record_exc)[:200]}")
                    # Periodic nudge: agent-curated memory review, no user input
                    try:
                        summary = await maybe_nudge(session_id, new_messages)
                        if summary:
                            print(f"\n[memory nudge] {summary}")
                    except Exception as nudge_exc:
                        logging.warning(f"Memory nudge failed: {str(nudge_exc)[:200]}")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'quit' to exit.")
            except Exception as e:
                print(f"\nError: {str(e)}")
                messages = messages[:-1] if messages else []
    finally:
        store.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LangGraph agent CLI with local SQLite/FTS5 session persistence")
    parser.add_argument(
        "--session-id",
        help="Resume an existing session by loading its recorded history from the local store",
    )
    args = parser.parse_args()
    asyncio.run(run_cli(args.session_id))
