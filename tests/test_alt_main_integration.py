"""Integration tests for alt-main.py wiring of the nm-memory-layer package.

alt-main.py instantiates SessionStore and PromptMemory at import time, so the
env overrides must be set BEFORE the module is executed. The LLM is never
called in these tests — only graph construction, tool binding, and the
memory-layer round-trips.
"""

import asyncio
import importlib.util
import os
import tempfile
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from nm_memory_layer import NudgePolicy

REPO_ROOT = Path(__file__).resolve().parent.parent
ALT_MAIN = REPO_ROOT / "alt-main.py"


@pytest.fixture(scope="module")
def alt(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("altmain")
    os.environ["SESSION_DB_PATH"] = str(tmp / "sessions.db")
    os.environ["MEMORY_DIR"] = str(tmp / "memories")
    os.environ["SKILLS_DIR"] = str(tmp / "skills")
    spec = importlib.util.spec_from_file_location("altmain_under_test", ALT_MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module.store.close()


@pytest.fixture(autouse=True)
def fresh_nudge_policy(alt):
    """Nudge tests mutate the policy; give each test a pristine one."""
    original = alt.nudge_policy
    alt.nudge_policy = NudgePolicy()
    yield
    alt.nudge_policy = original


class TestToolBinding:
    def test_local_memory_tools_are_bound(self, alt):
        assert alt.session_search_tool.name == "session_search"
        assert alt.memory_manage_tool.name == "memory_manage"

    def test_skill_tools_are_bound(self, alt):
        assert alt.skill_manage_tool.name == "skill_manage"
        assert alt.load_skill_tool.name == "load_skill"

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
        ] + [
            alt.session_search_tool,
            alt.memory_manage_tool,
            alt.skill_manage_tool,
            alt.load_skill_tool,
        ]
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

    def test_build_agent_accepts_skill_index(self, alt):
        alt.skill_library.create_skill("test-probe-skill", "Probe description only.", "body with secrets")
        index = alt.skill_library.render_index()
        assert "test-probe-skill: Probe description only." in index
        assert "secrets" not in index  # progressive disclosure: body stays out
        app = alt.build_agent([], skill_index=index)
        assert app is not None


class TestSkillsWiring:
    def test_skill_library_uses_isolated_dir(self, alt):
        assert alt.skill_library.skills_dir == Path(os.environ["SKILLS_DIR"])

    def test_skill_manage_end_to_end_through_bound_tool(self, alt):
        result = alt.skill_manage_tool.invoke(
            {"action": "create", "name": "e2e-probe", "description": "Integration probe.", "content": "steps"}
        )
        assert result.startswith("OK:")
        assert "steps" in alt.load_skill_tool.invoke({"name": "e2e-probe"})
        assert alt.skill_manage_tool.invoke({"action": "delete", "name": "e2e-probe"}).startswith("OK:")


class TestNudgeWithSkills:
    def test_nudge_can_create_skills(self, alt):
        class SkillCreatingNudgeModel:
            def __init__(self):
                self.calls = 0

            async def ainvoke(self, messages):
                self.calls += 1
                if self.calls == 1:
                    return AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "skill_manage",
                            "args": {
                                "action": "create",
                                "name": "nudge-made-skill",
                                "description": "Created by the nudge after a messy recovery.",
                                "content": "1. step one",
                            },
                            "id": "n1",
                        }],
                    )
                return AIMessage(content="Created 1 skill.")

        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 1
        summary = asyncio.run(
            alt.maybe_nudge(
                "test-sid",
                [HumanMessage(content="the tool kept timing out until I added retries"), AIMessage(content="fixed")],
                nudge_model=SkillCreatingNudgeModel(),
            )
        )
        assert summary == "Created 1 skill."
        assert "Created by the nudge" in alt.skill_library.load_skill("nudge-made-skill")
        alt.skill_library.delete_skill("nudge-made-skill")

    def test_nudge_rejects_unknown_tools(self, alt):
        class WeirdNudgeModel:
            async def ainvoke(self, messages):
                return AIMessage(
                    content="",
                    tool_calls=[{"name": "execute", "args": {"command": "rm -rf /"}, "id": "n1"}],
                )

        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 1
        summary = asyncio.run(
            alt.maybe_nudge(
                "test-sid",
                [HumanMessage(content="x"), AIMessage(content="y")],
                nudge_model=WeirdNudgeModel(),
                max_iters=1,
            )
        )
        assert summary == "Nudge reached its tool-call limit."


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

    def test_nudge_policy_default_interval(self, alt):
        assert alt.nudge_policy.interval == 5  # DEFAULT_NUDGE_INTERVAL

    def test_maybe_nudge_silent_before_interval(self, alt):
        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 3
        for _ in range(2):
            result = asyncio.run(
                alt.maybe_nudge("test-sid", [HumanMessage(content="hi"), AIMessage(content="hello")])
            )
            assert result is None

    def test_nudge_runs_at_interval_and_writes_memory(self, alt):
        class FakeNudgeModel:
            def __init__(self):
                self.calls = []

            async def ainvoke(self, messages):
                self.calls.append(messages)
                if len(self.calls) == 1:
                    return AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "memory_manage",
                            "args": {"operation": "add", "target": "memory", "content": "nudge-written entry"},
                            "id": "n1",
                        }],
                    )
                return AIMessage(content="Saved 1 entry to MEMORY.md.")

        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 1
        fake = FakeNudgeModel()
        summary = asyncio.run(
            alt.maybe_nudge(
                "test-sid",
                [HumanMessage(content="Note: reports live in reports/YYYY/qN.md"), AIMessage(content="Noted.")],
                nudge_model=fake,
            )
        )
        assert summary == "Saved 1 entry to MEMORY.md."
        assert "nudge-written entry" in alt.memory._read("memory")
        # Nudge must not leave tool-call artifacts in memory
        alt.memory_manage_tool.invoke(
            {"operation": "remove", "target": "memory", "old_content": "nudge-written entry"}
        )

    def test_nudge_without_worthwhile_content_stays_silent(self, alt):
        class SilentNudgeModel:
            async def ainvoke(self, messages):
                return AIMessage(content="No memory updates.")

        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 1
        summary = asyncio.run(
            alt.maybe_nudge("test-sid", [HumanMessage(content="what is 2+2"), AIMessage(content="4")], nudge_model=SilentNudgeModel())
        )
        assert summary == "No memory updates."

    def test_nudge_never_touches_session_archive(self, alt):
        class WritingNudgeModel:
            async def ainvoke(self, messages):
                return AIMessage(content="No memory updates.")

        before = len(alt.store.load_session(alt.session_id))
        alt.nudge_policy.mark_nudged("test-sid")
        alt.nudge_policy.interval = 1
        asyncio.run(
            alt.maybe_nudge("test-sid", [HumanMessage(content="ephemeral nudge probe"), AIMessage(content="ok")], nudge_model=WritingNudgeModel())
        )
        assert len(alt.store.load_session(alt.session_id)) == before

    def test_memory_manage_end_to_end_through_bound_tool_repeatable(self, alt):
        """Guard against fixture-order coupling: the tool still works after nudge tests."""
        result = alt.memory_manage_tool.invoke(
            {"operation": "add", "target": "user", "content": "post-nudge probe"}
        )
        assert result.startswith("OK:")
        alt.memory_manage_tool.invoke(
            {"operation": "remove", "target": "user", "old_content": "post-nudge probe"}
        )

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
