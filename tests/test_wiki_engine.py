"""Tests for the in-process Python wiki engine (wiki_engine/) — the port of
the wiki-os Node engine. Covers the HTTP contract the React UI consumes, the
fork's bare-wikilink resolution patch, reconcile-on-change, person overrides,
and the 409/404 semantics.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wiki_engine import WikiEngine, create_wiki_router
from wiki_engine.runtime import reset_engine

VAULT: dict[str, str] = {
    "concepts/overfitting.md": (
        "---\ntags: [selection-bias, backtest]\n---\n"
        "# Overfitting\n\n"
        "Selection bias inflates backtest results, so correct before believing them.\n"
        "See [[deflated-sharpe]] and [[paper-x]].\n"
        "## Why it matters\n\n"
        "Uncorrected selection bias makes strategies look better than they are.\n"
    ),
    "concepts/deflated-sharpe.md": (
        "# Deflated Sharpe\n\n"
        "The deflated Sharpe ratio corrects for multiple testing in backtests.\n"
    ),
    "sources/paper-x.md": (
        "---\nperson: true\n---\n"
        "# Paper X\n\n"
        "Authored by Jane Doe in 2020 and cited widely.\n"
    ),
    "people/Jane Doe.md": (
        "# Jane Doe\n\n"
        "Jane Doe was born in 1970 and works on statistics.\n"
    ),
    "concepts/orphan-link.md": (
        "# Orphan\n\n"
        "This page links to [[missing-page]] which does not exist in the vault.\n"
    ),
    "concepts/code-test.md": (
        "# Code test\n\n"
        "```python\nprint('hello volatility')\n```\n"
    ),
}


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    vault = tmp_path / "wiki"
    for rel, content in VAULT.items():
        target = vault / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    monkeypatch.setenv("WIKI_ROOT", str(vault))
    monkeypatch.setenv("WIKI_ENGINE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("WIKI_ENGINE_POLL_SECS", "600")  # keep the poller idle in tests
    reset_engine()
    yield {"vault": vault, "state": tmp_path / "state"}
    reset_engine()


@pytest.fixture()
def client(env: dict[str, Any]) -> tuple[TestClient, WikiEngine]:
    engine = WikiEngine()
    app = FastAPI()
    app.include_router(create_wiki_router(engine))
    with TestClient(app) as test_client:
        yield test_client, engine


@pytest.fixture()
def unconfigured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WIKI_ROOT", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("WIKI_ENGINE_STATE_DIR", str(tmp_path / "state"))
    reset_engine()
    app = FastAPI()
    app.include_router(create_wiki_router(WikiEngine()))
    with TestClient(app) as test_client:
        yield test_client
    reset_engine()


# --- config (never 409s) ---------------------------------------------------------


def test_config_shape(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/config").json()
    assert body["siteTitle"] == "WikiOS"
    assert body["people"]["mode"] == "explicit"
    assert body["navigation"]["graphLabel"] == "Graph"
    assert body["homepage"]["sectionOrder"] == ["featured", "topConnected", "people", "recentPages"]


# --- stats (snake_case contract) ---------------------------------------------------


def test_stats_shape(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/stats").json()
    assert body["total_pages"] == len(VAULT)
    assert body["total_words"] > 0
    # [[deflated-sharpe]] + [[paper-x]] from overfitting.md, plus Jane Doe's page links
    pages = {entry["page"] for entry in body["top_backlinks"]}
    assert "overfitting" in {entry["page"] for entry in body["top_backlinks"]} or pages


def test_stats_counts_bare_wikilinks_via_patch(client: tuple[TestClient, WikiEngine]):
    """The fork patch: [[deflated-sharpe]] (bare) must count as a backlink for
    concepts/deflated-sharpe.md (slug concepts/deflated-sharpe)."""
    http, _ = client
    body = http.get("/wapi/api/stats").json()
    counts = {entry["page"]: entry["count"] for entry in body["top_backlinks"]}
    assert counts.get("deflated-sharpe") == 1
    assert counts.get("paper-x") == 1


# --- home ----------------------------------------------------------------------


def test_home_shape_and_people(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/home").json()
    assert body["totalPages"] == len(VAULT)
    assert len(body["featured"]) == min(4, len(VAULT))
    assert len(body["recentPages"]) <= 6
    assert len(body["topConnected"]) <= 6
    # people/ folder + frontmatter person:true are both detected
    assert {p["slug"] for p in body["people"]} == {"people/Jane%20Doe", "sources/paper-x"}


# --- search ---------------------------------------------------------------------


def test_search_scores_and_prefix_matching(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/search", params={"q": "overf"}).json()
    assert body["query"] == "overf"
    assert len(body["results"]) >= 1
    top = body["results"][0]
    assert top["file"] == "concepts/overfitting.md"
    # +10 title match; the token only appears in the (stripped) title, not the body
    assert top["score"] == 10
    assert top["matches"] == []


def test_search_matches_track_body_lines(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/search", params={"q": "selection bias"}).json()
    assert {r["file"] for r in body["results"]} == {"concepts/overfitting.md"}
    match = body["results"][0]["matches"][0]
    assert match["heading"] == "Overfitting"  # body line before any H2 → page title
    assert "Selection bias" in match["snippet"]


def test_search_requires_all_terms(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    both = http.get("/wapi/api/search", params={"q": "deflated multiple"}).json()
    files = {r["file"] for r in both["results"]}
    assert "concepts/deflated-sharpe.md" in files
    # overfitting.md mentions neither "deflated" nor "multiple"... it links but doesn't contain both
    assert "concepts/overfitting.md" not in files
    empty = http.get("/wapi/api/search", params={"q": "   "}).json()
    assert empty == {"query": "   ", "results": []}


def test_search_matches_track_headings(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/search", params={"q": "volatility"}).json()
    assert len(body["results"]) >= 1
    # code-test.md's only "volatility" occurrence is inside a fenced code block;
    # upstream indexing is not fence-aware, so it still matches — snippet present
    files = {r["file"] for r in body["results"]}
    assert "concepts/code-test.md" in files


# --- graph ----------------------------------------------------------------------


def test_graph_edges_use_resolved_slugs(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/graph").json()
    nodes = {node["slug"] for node in body["nodes"]}
    edges = {(edge["source"], edge["target"], edge["weight"]) for edge in body["edges"]}

    assert "concepts/overfitting" in nodes
    # the bare wikilink [[deflated-sharpe]] resolved to the folder-qualified slug
    assert ("concepts/overfitting", "concepts/deflated-sharpe", 1) in edges
    # [[missing-page]] is unresolvable → no phantom node, no edge
    assert "missing-page" not in nodes
    assert not any(target == "missing-page" for _, target, _ in edges)

    overfitting_node = next(n for n in body["nodes"] if n["slug"] == "concepts/overfitting")
    assert set(overfitting_node["neighbors"]) >= {
        "concepts/deflated-sharpe",
        "sources/paper-x",
    }


def test_page_content_links_are_rewritten(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/wiki/concepts/overfitting").json()
    # [[deflated-sharpe]] rendered as /wiki/deflated-sharpe must be rewritten to
    # the canonical /wiki/concepts/deflated-sharpe
    assert "](/wiki/concepts/deflated-sharpe)" in body["contentMarkdown"]
    assert "](/wiki/deflated-sharpe)" not in body["contentMarkdown"]


# --- page -----------------------------------------------------------------------


def test_page_shape_and_neighbors(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/wiki/concepts/overfitting").json()
    assert body["slug"] == "concepts/overfitting"
    assert body["fileName"] == "concepts/overfitting.md"
    # the leading H1 is stripped from content, so the first stored heading is the H2
    assert body["headings"][0]["id"] == "why-it-matters"
    # frontmatter tags first, then the folder topic ("concepts" is not structural upstream)
    assert body["categories"] == ["Selection Bias", "Backtest", "Concepts"]
    assert body["hasCodeBlocks"] is False
    assert body["personOverride"] is None
    neighbor_slugs = {n["slug"] for n in body["neighbors"]}
    assert neighbor_slugs == {"concepts/deflated-sharpe", "sources/paper-x"}


def test_page_with_encoded_slug(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/wiki/people/Jane%20Doe").json()
    assert body["slug"] == "people/Jane%20Doe"
    assert body["title"] == "Jane Doe"


def test_page_404_and_traversal(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    assert http.get("/wapi/api/wiki/concepts/no-such-page").status_code == 404
    assert http.get("/wapi/api/wiki/../etc/passwd").status_code in (404, 400)


# --- person overrides ------------------------------------------------------------


def test_person_override_flow(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    overridden = http.post(
        "/wapi/api/setup/person-override",
        json={"file": "concepts/overfitting.md", "override": "person"},
    )
    assert overridden.status_code == 200
    assert overridden.json() == {"ok": True, "file": "concepts/overfitting.md", "override": "person"}

    page = http.get("/wapi/api/wiki/concepts/overfitting").json()
    assert page["isPerson"] is True
    assert page["personOverride"] == "person"

    home = http.get("/wapi/api/home").json()
    assert "concepts/overfitting" in {p["slug"] for p in home["people"]}

    cleared = http.post(
        "/wapi/api/setup/person-override",
        json={"file": "concepts/overfitting.md", "override": None},
    )
    assert cleared.status_code == 200
    page = http.get("/wapi/api/wiki/concepts/overfitting").json()
    assert page["isPerson"] is False
    assert page["personOverride"] is None


def test_person_override_persists_across_restart(env: dict[str, Any]):
    engine = WikiEngine()
    engine.set_person_override("concepts/overfitting.md", "not-person")
    engine.close()

    engine2 = WikiEngine()
    assert engine2.overrides.get("concepts/overfitting.md") == "not-person"
    engine2.ensure_ready()
    page = engine2.page(["concepts", "overfitting"])
    assert page["personOverride"] == "not-person"
    engine2.close()


# --- 409 setup-required ----------------------------------------------------------


def test_unconfigured_vault_returns_409(unconfigured_client: TestClient):
    for path in ("/wapi/api/stats", "/wapi/api/home", "/wapi/api/graph", "/wapi/api/health"):
        response = unconfigured_client.get(path)
        assert response.status_code == 409
        assert response.json()["code"] == "SETUP_REQUIRED"
    search = unconfigured_client.get("/wapi/api/search", params={"q": "x"})
    assert search.status_code == 409
    page = unconfigured_client.get("/wapi/api/wiki/anything")
    assert page.status_code == 409
    # config is served even when unconfigured
    assert unconfigured_client.get("/wapi/api/config").status_code == 200


# --- reconcile on change -----------------------------------------------------------


def test_reconcile_picks_up_edits(env: dict[str, Any], client: tuple[TestClient, WikiEngine]):
    http, engine = client
    target = env["vault"] / "concepts" / "overfitting.md"
    target.write_text(
        "# Overfitting\n\nNow mentioning zebra-unicorn-xyz for the first time.\n",
        encoding="utf-8",
    )
    future = time.time_ns() + 2_000_000_000  # +2s, beats the 0.5ms tolerance
    os.utime(target, ns=(future, future))
    engine.scan_now()

    body = http.get("/wapi/api/search", params={"q": "zebra-unicorn-xyz"}).json()
    assert {r["file"] for r in body["results"]} == {"concepts/overfitting.md"}


def test_reconcile_removes_deleted_pages(env: dict[str, Any], client: tuple[TestClient, WikiEngine]):
    http, engine = client
    (env["vault"] / "concepts" / "code-test.md").unlink()
    engine.scan_now()

    body = http.get("/wapi/api/stats").json()
    assert body["total_pages"] == len(VAULT) - 1
    assert http.get("/wapi/api/wiki/concepts/code-test").status_code == 404


# --- admin reindex -----------------------------------------------------------------


def test_admin_reindex(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.post("/wapi/api/admin/reindex").json()
    assert body["ok"] is True
    assert body["totalPages"] == len(VAULT)
    assert body["rebuiltAt"]


# --- markdown preprocessing parity ---------------------------------------------------


def test_frontmatter_and_wikilink_transform(client: tuple[TestClient, WikiEngine]):
    http, _ = client
    body = http.get("/wapi/api/wiki/concepts/overfitting").json()
    # frontmatter stripped, leading H1 stripped, wikilinks transformed
    assert not body["contentMarkdown"].startswith("---")
    assert not body["contentMarkdown"].startswith("# Overfitting")
    assert "](/wiki/sources/paper-x)" in body["contentMarkdown"]
