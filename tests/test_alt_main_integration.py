"""Integration tests for alt-main.py wiring of the nm-memory-layer package.

alt-main.py instantiates SessionStore and PromptMemory at import time, so the
env overrides must be set BEFORE the module is executed. The LLM is never
called in these tests — only graph construction, tool binding, and the
memory-layer round-trips.
"""

import importlib.util
import os
import tempfile
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

REPO_ROOT = Path(__file__).resolve().parent.parent
ALT_MAIN = REPO_ROOT / "alt-main.py"


@pytest.fixture(scope="module")
def alt(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("altmain")
    os.environ["SESSION_DB_PATH"] = str(tmp / "sessions.db")
    os.environ["MEMORY_DIR"] = str(tmp / "memories")
    spec = importlib.util.spec_from_file_location("altmain_under_test", ALT_MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module.store.close()


class TestToolBinding:
    def test_local_memory_tools_are_bound(self, alt):
        assert alt.session_search_tool.name == "session_search"
        assert alt.memory_manage_tool.name == "memory_manage"

    def test_viking_tools_filtered_out_of_binding(self, alt):
        """tools.py is shared with main.py and still imports viking tools;
        alt-main must not bind them."""
        bound = [t for t in alt.tools if not t.name.startswith("viking_")]
        assert len(bound) < len(alt.tools)
        assert all(not t.name.startswith("viking_") for t in bound)


class TestGraph:
    def test_build_agent_compiles_with_all_memory_tools(self, alt):
        all_tools = [
            t for t in alt.tools if not t.name.startswith("viking_")
        ] + [alt.session_search_tool, alt.memory_manage_tool]
        app = alt.build_agent(all_tools, memory_block="")
        assert app is not None

    def test_build_agent_accepts_memory_block(self, alt):
        alt.memory.add("memory", "Quarterly reports live in reports/YYYY/qN.md")
        alt.memory.add("user", "Gordon prefers concise answers")
        block = alt.memory.load()
        assert block.startswith("<agent_memory>")
        assert "reports/YYYY" in block and "Gordon" in block
        app = alt.build_agent([], memory_block=block)
        assert app is not None


class TestMemoryWiring:
    def test_memory_manage_end_to_end_through_bound_tool(self, alt):
        result = alt.memory_manage_tool.invoke(
            {"operation": "add", "target": "memory", "content": "E2E wiring line"}
        )
        assert result.startswith("OK:")
        result = alt.memory_manage_tool.invoke(
            {"operation": "remove", "target": "memory", "old_content": "E2E wiring line"}
        )
        assert result.startswith("OK:")

    def test_session_store_roundtrip_through_module(self, alt):
        sid = alt.session_id
        alt.store.record_turn(
            sid,
            [
                HumanMessage(content="Backfill the EUR/USD series for August"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "execute", "args": {"command": "jetta backfill eurusd"}, "id": "call_9"}],
                ),
                ToolMessage(content="backfill complete: 23 trading days", tool_call_id="call_9", name="execute"),
                AIMessage(content="EUR/USD August series backfilled."),
            ],
        )
        resumed = alt.store.load_session(sid)
        assert resumed[1].tool_calls[0]["id"] == resumed[2].tool_call_id
        # AND semantics: only the tool result contains both tokens.
        search_result = alt.session_search_tool.invoke({"query": "backfill complete"})
        assert "backfill complete: 23 trading days" in search_result

    def test_session_and_memory_layers_are_independent_stores(self, alt):
        """Prompt memory is file-based; episodic memory is SQLite — one must not
        interfere with the other."""
        alt.memory.add("memory", "memory layer marker entry")
        alt.store.record_turn(alt.session_id, [HumanMessage(content="session layer marker entry")])
        assert "memory layer marker entry" in alt.memory._read("memory")
        assert alt.memory.load().count("memory layer marker entry") == 1
        assert "session layer marker entry" in alt.session_search_tool.invoke(
            {"query": "session layer marker"}
        )
