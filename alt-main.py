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
from nm_memory_layer import SessionStore, create_session_search_tool

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

user = os.getenv("OPENVIKING_USER", "gordon")
session_id = str(uuid.uuid4())

store = SessionStore()
session_search_tool = create_session_search_tool(store)

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
            "You are an adaptable AI agent.\n"
            "\n"
            "SESSION MEMORY:\n"
            "session_search queries your archived past sessions (episodic memory). "
            "Call it BEFORE redoing work when the user's request may relate to something "
            "from a previous conversation — prior decisions, findings, errors and their "
            "fixes, or procedures you already worked out. It returns short excerpts with "
            "session ids and turn numbers, not full transcripts, so it is cheap to consult.\n"
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
async def run_cli(resume_session_id: str | None = None):
    global session_id

    #mcp_tools = await _load_mcp_tools()
    #if mcp_tools:
    #    print(f"Connected to Finance Toolkit MCP ({len(mcp_tools)} tools)")
    # Drop OpenViking tools (shared tools.py) — the local store replaces them.
    all_tools = [t for t in tools if not t.name.startswith("viking_")] + [session_search_tool]
    app = build_agent(all_tools)

    print("LangGraph Agent CLI (local SQLite/FTS5 session store)")
    print("=" * 50)
    print(f"\nHello {user}\n")
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
