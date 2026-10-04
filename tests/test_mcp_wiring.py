"""Wiring test for _load_mcp_tools over mcp_servers.json.

Uses a real MCP server (FastMCP over stdio) for the success path, plus a
deliberately broken server to prove per-server resilience: one bad server
must not take the others down. No LLM calls.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

import main

TINY_SERVER = """\
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tiny")


@mcp.tool()
def tiny_echo(x: str) -> str:
    \"\"\"Echo x back.\"\"\"
    return x


mcp.run()
"""


def _write_config(tmp_path, servers) -> Path:
    p = tmp_path / "mcp_servers.json"
    p.write_text(json.dumps({"version": 1, "servers": servers}), encoding="utf-8")
    return p


@pytest.fixture()
def tiny_server_script(tmp_path) -> Path:
    script = tmp_path / "tiny_mcp_server.py"
    script.write_text(TINY_SERVER, encoding="utf-8")
    return script


def test_binds_real_stdio_server_and_filters(tmp_path, monkeypatch, tiny_server_script):
    cfg = _write_config(tmp_path, {
        "tiny": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(tiny_server_script)],
            "keep_tools": ["tiny_echo"],
            "enabled": True,
        },
    })
    monkeypatch.setenv("MCP_SERVERS_FILE", str(cfg))
    tools, report = asyncio.run(main._load_mcp_tools())
    assert len(tools) == 1
    assert tools[0].name.endswith("tiny_echo")  # prefixed as <server>_<tool>
    row = next(r for r in report if r["name"] == "tiny")
    assert row["connected"] is True and row["tool_count"] == 1


def test_broken_server_skipped_others_survive(tmp_path, monkeypatch, tiny_server_script):
    cfg = _write_config(tmp_path, {
        "broken": {
            "transport": "stdio",
            "command": sys.executable,
            "args": ["-c", "raise SystemExit(1)"],
            "enabled": True,
        },
        "tiny": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [str(tiny_server_script)],
            "enabled": True,
        },
    })
    monkeypatch.setenv("MCP_SERVERS_FILE", str(cfg))
    tools, report = asyncio.run(main._load_mcp_tools())
    by_name = {r["name"]: r for r in report}
    assert by_name["broken"]["connected"] is False
    assert by_name["broken"]["error"]
    assert by_name["tiny"]["connected"] is True
    assert len(tools) == 1  # tiny's tool survived the broken neighbor


def test_all_disabled_yields_zero_tools(tmp_path, monkeypatch):
    cfg = _write_config(tmp_path, {
        "off": {"transport": "stdio", "command": "x", "enabled": False},
    })
    monkeypatch.setenv("MCP_SERVERS_FILE", str(cfg))
    tools, report = asyncio.run(main._load_mcp_tools())
    assert tools == []
    assert report[0]["enabled"] is False
