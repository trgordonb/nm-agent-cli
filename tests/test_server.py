"""Wiring tests for server.py (FastAPI surface) — no LLM calls.

The chat endpoint itself calls the model, so only request validation, the
read-only endpoints, and the partial-turn trimming logic are exercised here;
the SSE stream and the in-process wiki engine (tests/test_wiki_engine.py) are
covered separately.
"""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from server import _valid_prefix_len, app


def _client():
    return TestClient(app)


def test_health_reports_status():
    with _client() as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["model"]
        assert isinstance(body["skills"], int)
        assert body["assembled"] is False  # lazy: no graph/MCP assembly yet


def test_sessions_list_shape():
    with _client() as client:
        r = client.get("/api/sessions")
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list)
        if sessions:
            assert {"session_id", "created_at", "turns"} <= sessions[0].keys()


def test_unknown_session_404():
    with _client() as client:
        r = client.get("/api/sessions/definitely-not-a-session")
        assert r.status_code == 404


def test_chat_rejects_empty_message():
    with _client() as client:
        r = client.post("/api/chat", json={"message": ""})
        assert r.status_code == 422


def test_skills_endpoint():
    with _client() as client:
        r = client.get("/api/skills")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_valid_prefix_full_turn():
    msgs = [
        HumanMessage("hi"),
        AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}]),
        ToolMessage(content="ok", tool_call_id="1"),
        AIMessage("done"),
    ]
    assert _valid_prefix_len(msgs) == 4


def test_valid_prefix_drops_unanswered_tool_call():
    msgs = [
        HumanMessage("hi"),
        AIMessage("thinking"),
        AIMessage(content="", tool_calls=[{"id": "1", "name": "x", "args": {}}]),
    ]
    # the AIMessage with the unanswered tool_call is dropped, earlier steps kept
    assert _valid_prefix_len(msgs) == 2


def test_valid_prefix_partial_tool_group():
    msgs = [
        HumanMessage("hi"),
        AIMessage(content="", tool_calls=[
            {"id": "1", "name": "x", "args": {}},
            {"id": "2", "name": "y", "args": {}},
        ]),
        ToolMessage(content="a", tool_call_id="1"),
    ]
    # one of two calls answered — the whole group is incomplete, human only
    assert _valid_prefix_len(msgs) == 1


def test_cancel_unknown_turn_is_idempotent():
    with _client() as client:
        r = client.post("/api/chat/cancel", json={"turn_id": "no-such-turn"})
        assert r.status_code == 200
        assert r.json() == {"cancelled": False, "detail": "turn not active (already finished?)"}
