"""mcp_config: loader, ${VAR} interpolation (fail-closed), atomic toggles."""

from __future__ import annotations

import json

import pytest

from mcp_config import (
    McpConfigError,
    apply_keep_tools,
    load_mcp_servers,
    set_server_enabled,
)


def write_config(tmp_path, servers):
    p = tmp_path / "mcp_servers.json"
    p.write_text(json.dumps({"version": 1, "servers": servers}), encoding="utf-8")
    return p


def test_load_enabled_server_passes_through(tmp_path):
    p = write_config(tmp_path, {
        "agent_browser": {
            "transport": "stdio", "command": "agent-browser",
            "args": ["mcp", "--tools", "core"], "enabled": True,
        },
    })
    servers, statuses = load_mcp_servers(p)
    assert list(servers) == ["agent_browser"]
    assert servers["agent_browser"]["command"] == "agent-browser"
    assert statuses[0].enabled and statuses[0].error is None


def test_disabled_server_excluded_but_reported(tmp_path):
    p = write_config(tmp_path, {"off": {"transport": "stdio", "command": "x", "enabled": False}})
    servers, statuses = load_mcp_servers(p)
    assert servers == {}
    assert statuses[0].enabled is False and statuses[0].error is None  # off is normal


def test_interpolation_and_fail_closed(tmp_path, monkeypatch):
    p = write_config(tmp_path, {
        "good": {"transport": "streamable_http", "url": "https://x/${GOOD_VAR}/mcp",
                 "headers": {"Authorization": "Bearer ${SECRET_VAR}"}, "enabled": True},
    })
    monkeypatch.setenv("GOOD_VAR", "resolved")
    monkeypatch.setenv("SECRET_VAR", "s3cret")
    servers, statuses = load_mcp_servers(p)
    assert servers["good"]["url"] == "https://x/resolved/mcp"
    assert servers["good"]["headers"]["Authorization"] == "Bearer s3cret"

    monkeypatch.delenv("SECRET_VAR")
    servers, statuses = load_mcp_servers(p)
    assert servers == {}  # fail-closed: skipped entirely
    assert "SECRET_VAR" in statuses[0].error


def test_unsupported_transport_rejected(tmp_path):
    p = write_config(tmp_path, {"bad": {"transport": "carrier_pigeon", "enabled": True}})
    servers, statuses = load_mcp_servers(p)
    assert servers == {}
    assert "carrier_pigeon" in statuses[0].error


def test_unparseable_json_raises(tmp_path):
    p = tmp_path / "mcp_servers.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(McpConfigError):
        load_mcp_servers(p)


def test_missing_file_is_empty_not_error(tmp_path):
    servers, statuses = load_mcp_servers(tmp_path / "nope.json")
    assert servers == {} and statuses == []


def test_set_server_enabled_roundtrip(tmp_path):
    p = write_config(tmp_path, {
        "a": {"transport": "stdio", "command": "a", "enabled": True},
        "b": {"transport": "stdio", "command": "b", "enabled": False},
    })
    assert set_server_enabled(p, "b", True).startswith("OK:")
    servers, _ = load_mcp_servers(p)
    assert list(servers) == ["a", "b"]
    assert set_server_enabled(p, "a", False).startswith("OK:")
    servers, _ = load_mcp_servers(p)
    assert list(servers) == ["b"]
    assert "Rejected" in set_server_enabled(p, "ghost", True)
    assert json.loads(p.read_text())["servers"]["a"]["enabled"] is False  # persisted
    assert not list(tmp_path.glob(".mcp_servers.json.tmp-*"))  # atomic: no litter


def test_keep_tools_filters_prefixed_names():
    class T:
        def __init__(self, n):
            self.name = n

    tools = [
        T("srv_breadth"),
        T("srv_risk"),
        T("srv_other"),
        T("breadth"),
        # multi-word tool names under a server prefix (luxalgo case)
        T("luxalgo_library_search"),
        T("luxalgo_library_get_source_code"),
        T("luxalgo_trackers_query"),
        T("luxalgo_journal_get_trade"),  # not in keep
    ]
    kept = apply_keep_tools(tools, ["breadth", "risk", "library_search", "library_get_source_code", "trackers_query"])
    assert [t.name for t in kept] == [
        "srv_breadth", "srv_risk", "breadth",
        "luxalgo_library_search", "luxalgo_library_get_source_code", "luxalgo_trackers_query",
    ]
    assert apply_keep_tools(tools, None) is tools
