"""MCP server configuration: ``mcp_servers.json`` with per-server enable/disable.

Machine-local, git-tracked config (see MCP_TOGGLE_PLAN.md) — unlike skills,
this never goes near the object registry: a stdio ``command`` is meaningless
off this machine. Secrets are ``${VAR}``-interpolated from the environment at
load time and never stored in the file; an unresolved placeholder disables
that server with a warning (fail-closed), never a crash and never a leaked
literal. Toggles rewrite the file atomically (``.tmp`` + ``os.replace``) and
apply at the next runtime assembly (CLI: next session; server: reload).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path

_ALLOWED_TRANSPORTS = {"stdio", "streamable_http", "sse"}
_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_PASSTHROUGH_KEYS = ("transport", "command", "args", "env", "url", "headers")


class McpConfigError(ValueError):
    """The config file itself is unreadable/unparseable."""


@dataclass
class ServerStatus:
    name: str
    enabled: bool
    description: str = ""
    transport: str = ""
    error: str | None = None
    connected: bool | None = None
    tool_count: int | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def default_path() -> Path:
    return Path(os.environ.get("MCP_SERVERS_FILE", "mcp_servers.json"))


def _interpolate(value, name: str, missing: list[str]):
    if isinstance(value, str):
        def sub(match: re.Match) -> str:
            var = match.group(1)
            env = os.environ.get(var)
            if env is None:
                missing.append(var)
                return ""
            return env
        return _PLACEHOLDER.sub(sub, value)
    if isinstance(value, list):
        return [_interpolate(v, name, missing) for v in value]
    if isinstance(value, dict):
        return {k: _interpolate(v, name, missing) for k, v in value.items()}
    return value


def load_mcp_servers(path: str | Path | None = None) -> tuple[dict[str, dict], list[ServerStatus]]:
    """Read the config → ``(client_servers, statuses)``.

    ``client_servers`` holds the *enabled, successfully interpolated* servers,
    keyed by name, ready for ``MultiServerMCPClient``. ``statuses`` describes
    every configured server (enabled flag + fail-closed errors); connection
    results are filled in later by the caller.
    """
    p = Path(path) if path else default_path()
    statuses: list[ServerStatus] = []
    if not p.is_file():
        return {}, statuses
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise McpConfigError(f"{p}: unparseable JSON: {e}") from e
    servers = doc.get("servers", {})
    if not isinstance(servers, dict):
        raise McpConfigError(f"{p}: 'servers' must be an object")
    client_servers: dict[str, dict] = {}
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            statuses.append(ServerStatus(name, False, error="invalid entry (not an object)"))
            continue
        description = str(cfg.get("description", ""))
        transport = str(cfg.get("transport", ""))
        enabled = bool(cfg.get("enabled", False))
        status = ServerStatus(name, enabled, description=description, transport=transport)
        if transport not in _ALLOWED_TRANSPORTS:
            status.error = f"unsupported transport {transport!r}"
        elif not enabled:
            pass  # deliberately off — normal state, not an error
        else:
            missing: list[str] = []
            passthrough = {k: cfg[k] for k in _PASSTHROUGH_KEYS if k in cfg}
            resolved = _interpolate(passthrough, name, missing)
            if missing:
                status.error = (
                    "unresolved env vars: " + ", ".join(sorted(set(missing)))
                    + " (server skipped, fail-closed)"
                )
            else:
                client_servers[name] = resolved
        statuses.append(status)
    return client_servers, statuses


def set_server_enabled(path: str | Path | None, name: str, enabled: bool) -> str:
    """Atomically flip one server's ``enabled`` flag. Returns a status message
    ("Rejected: …" / "OK: …") suitable for REST responses."""
    p = Path(path) if path else default_path()
    doc = json.loads(p.read_text(encoding="utf-8"))
    servers = doc.get("servers", {})
    if name not in servers:
        return f"Rejected: no MCP server named {name!r}"
    servers[name]["enabled"] = bool(enabled)
    tmp = p.with_name(f".{p.name}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    verb = "enabled" if enabled else "disabled"
    return f"OK: {verb} MCP server {name!r}"


def apply_keep_tools(tools: list, keep: list[str] | None) -> list:
    """Filter bound tools by a server's ``keep_tools`` list. MCP adapters
    namespace tools as ``<server>_<tool>``, and tool names are themselves
    multi-word (``library_get_source_code``), so match on exact name or
    ``_<tool>`` suffix — never on the last underscore segment."""
    if not keep:
        return tools
    out = []
    for t in tools:
        raw = getattr(t, "name", "")
        if any(raw == k or raw.endswith("_" + k) for k in keep):
            out.append(t)
    return out
