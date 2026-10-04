"""FastAPI routes — port of the wiki-os app.ts surface our frontend uses (MIT).

Mounted at /wapi/api/* so the frontend adapter (which rewrites /api/… →
/wapi/api/…) needs zero changes. Status semantics match upstream: 409
SETUP_REQUIRED for unconfigured vaults (the client keys on it), 404 for
unknown/invalid slugs, optional admin token on reindex.
"""

from __future__ import annotations

import functools
import os
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .queries import InvalidWikiSlug, WikiPageNotFound
from .runtime import WikiEngine, WikiSetupRequired


class PersonOverrideRequest(BaseModel):
    file: str
    override: Literal["person", "not-person", None] = None


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, WikiSetupRequired):
        return JSONResponse(
            status_code=409,
            content={"error": "Vault setup required", "code": "SETUP_REQUIRED"},
        )
    if isinstance(exc, (WikiPageNotFound, InvalidWikiSlug)):
        return JSONResponse(status_code=404, content={"error": str(exc)})
    return JSONResponse(status_code=500, content={"error": str(exc)})


def create_wiki_router(engine: WikiEngine) -> APIRouter:
    router = APIRouter(prefix="/wapi/api")

    def guarded(fn):
        # functools.wraps keeps the original signature visible to FastAPI's
        # dependency injection (query params, path params) and response model.
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (WikiSetupRequired, WikiPageNotFound, InvalidWikiSlug) as exc:
                return _error_response(exc)
            except Exception as exc:  # noqa: BLE001 — mirror the engine's catch-all 500
                return _error_response(exc)

        return wrapper

    @router.get("/config")
    def get_config() -> dict[str, Any]:
        # /api/config never 409s upstream — served even when unconfigured
        return engine.get_config()

    @router.get("/home")
    @guarded
    def get_home() -> dict[str, Any]:
        return engine.get_home()

    @router.get("/stats")
    @guarded
    def get_stats() -> dict[str, Any]:
        return engine.get_stats()

    @router.get("/graph")
    @guarded
    def get_graph() -> dict[str, Any]:
        return engine.graph()

    @router.get("/search")
    @guarded
    def search(q: str = Query(default="")) -> dict[str, Any]:
        return {"query": q, "results": engine.search(q)}

    @router.get("/wiki/{slug:path}")
    @guarded
    def get_wiki_page(slug: str) -> dict[str, Any]:
        # `slug` arrives percent-decoded (matching react-router's splat param);
        # queries re-canonicalizes it exactly like upstream's loader.
        return engine.page(slug.split("/"))

    @router.post("/setup/person-override")
    @guarded
    def post_person_override(body: PersonOverrideRequest) -> dict[str, Any]:
        if not body.file.strip():
            return JSONResponse(status_code=400, content={"error": "file is required"})
        return engine.set_person_override(body.file.strip(), body.override)

    @router.post("/admin/reindex")
    @guarded
    def post_reindex(request: Request) -> dict[str, Any]:
        admin_token = os.getenv("WIKIOS_ADMIN_TOKEN")
        if admin_token and request.headers.get("x-admin-token") != admin_token:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return engine.reindex()

    @router.get("/health")
    @guarded
    def get_health() -> dict[str, Any]:
        return engine.health()

    return router
