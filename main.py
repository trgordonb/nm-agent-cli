import os
import time
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
from langchain_openviking.messages import OPENVIKING_CONTEXT_MARKER
from dotenv import load_dotenv
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
    model="glm-4.7",
    api_key=os.getenv("OPENAI_API_KEY",""), # type: ignore
    base_url="https://api.z.ai/api/paas/v4/"
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

_CONTEXT_QUOTAS = {
    "skills": 3,
    "resources": 3,
    "events": 0,
    "entities": 0,
    "preferences": 0,
    "experiences": 0,
}

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
                "max_tokens": 3000,
                "dedup_turns": 0,
                "rewrite": False,
                "score_threshold": _CONTEXT_SCORE_FLOOR,
            },
        )
        body = response.json()
        if body.get("status") != "ok":
            raise RuntimeError(str(body.get("error"))[:300])
        result = body.get("result") or {}
    except Exception as exc:
        logging.warning(f"OpenViking context assembly failed: {exc}")
        return "", []

    entries = _filter_context_entries(result.get("entries") or [])
    if not entries:
        return "", []
    block = f"{OPENVIKING_CONTEXT_MARKER}\n{_render_context_entries(entries)}\n</openviking_context>"
    return block, [_context_part_from_entry(entry) for entry in entries]

# Define the agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    openviking_context: str

# Create tool node
tool_node = ToolNode(tools)
model_with_tools = model.bind_tools(tools)

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

# CLI interface
async def run_cli():
    await ov_client.initialize()

    print("LangGraph Agent CLI (type 'quit' to exit)")
    print("=" * 50)
    print(f"\nHello {user}\n")
    messages = []
    
    while True:
        try:
            user_input = input(f"\n{user}: ").strip()

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                continue
            
            # Assemble OpenViking context once per user turn
            context_block, context_parts = await aassemble_openviking_context(session_id, user_input)
            
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
                await recorder.aflush(session_id)
    
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
        except Exception as e:
            print(f"\nError: {str(e)}")
            messages = messages[:-1] if messages else []

    await _context_http.aclose()
    await recorder.aclose()

if __name__ == "__main__":
    asyncio.run(run_cli())
