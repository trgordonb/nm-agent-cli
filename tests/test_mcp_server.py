"""Server endpoints for MCP config (GET /api/mcp, toggle, reload).

The config file is redirected to a tmp path so toggles never touch the repo's
mcp_servers.json; re-assembly is stubbed so reload tests don't spawn MCP
processes. No LLM calls.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

import server as server_mod

CFG = {
    "version": 1,
    "servers": {
        "agent_browser": {
            "transport": "stdio",
            "command": "agent-browser",
            "enabled": True,
            "description": "local chrome automation",
        },
        "finance_toolkit": {
            "transport": "streamable_http",
            "url": "https://example.invalid/mcp",
            "enabled": False,
            "description": "dormant",
        },
    },
}


def _client(tmp_path, monkeypatch):
    cfg_path = tmp_path / "mcp_servers.json"
    cfg_path.write_text(json.dumps(CFG), encoding="utf-8")
    monkeypatch.setenv("MCP_SERVERS_FILE", str(cfg_path))
    return TestClient(server_mod.app), cfg_path


def test_list_mcp_reports_config_and_pending_assembly(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(server_mod, "_runtime", None)
    with client:
        r = client.get("/api/mcp")
        assert r.status_code == 200
        body = r.json()
        assert body["assembled"] is False
        rows = {s["name"]: s for s in body["servers"]}
        assert rows["agent_browser"]["enabled"] is True
        assert rows["agent_browser"]["transport"] == "stdio"
        assert rows["finance_toolkit"]["enabled"] is False
        assert rows["agent_browser"]["connected"] is None  # not assembled yet


def test_toggle_rewrites_config_file(tmp_path, monkeypatch):
    client, cfg_path = _client(tmp_path, monkeypatch)
    with client:
        r = client.post("/api/mcp/finance_toolkit/enabled", json={"enabled": True})
        assert r.status_code == 200
        assert r.json()["status"].startswith("OK:")
        doc = json.loads(cfg_path.read_text())
        assert doc["servers"]["finance_toolkit"]["enabled"] is True
        # agent_browser untouched
        assert doc["servers"]["agent_browser"]["enabled"] is True

        r = client.post("/api/mcp/ghost/enabled", json={"enabled": True})
        assert r.status_code == 404


def test_reload_reassembles_and_reports(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)

    async def fake_assemble():
        return {"mcp_tools": ["t1", "t2"], "mcp_report": [
            {"name": "agent_browser", "enabled": True, "connected": True, "tool_count": 2},
        ]}

    monkeypatch.setattr(server_mod, "assemble_agent_runtime", fake_assemble)
    monkeypatch.setattr(server_mod, "_runtime", None)
    with client:
        r = client.post("/api/mcp/reload")
        assert r.status_code == 200
        body = r.json()
        assert body["mcp_tools"] == 2
        assert server_mod._runtime["mcp_tools"] == ["t1", "t2"]

        # after reload, GET reflects the assembly report
        rows = {s["name"]: s for s in client.get("/api/mcp").json()["servers"]}
        assert rows["agent_browser"]["connected"] is True
        assert rows["agent_browser"]["tool_count"] == 2


def test_reload_409_while_turns_active(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(server_mod, "ACTIVE_TURNS", {"turn-1": __import__("asyncio").Event()})
    with client:
        r = client.post("/api/mcp/reload")
        assert r.status_code == 409
