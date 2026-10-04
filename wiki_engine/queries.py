"""Read-side queries — port of wiki-os src/lib/wiki-queries.ts (MIT).

Pure functions over the sqlite connection + resolved config (no cache, no
engine state — runtime.py wraps these with the revision-keyed derived cache
and the ensure-ready contract).
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .classification import build_fts_query, build_search_matches, count_term_occurrences
from .config import get_topic_emoji, get_topic_label, is_topic_hidden
from .shared import decode_slug_parts, encode_uri_component


class WikiPageNotFound(Exception):
    """Mapped to 404 by routes (the engine's only notFoundStatus=404 route)."""


class InvalidWikiSlug(Exception):
    """Malformed slug — also mapped to 404 on the wiki-page route."""


def parse_json_array(value: Any) -> list[Any]:
    if not isinstance(value, str):
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def normalize_search_terms(query: str) -> list[str]:
    trimmed = query.strip().lower()
    if not trimmed:
        return []
    return [term for term in re.split(r"\s+", trimmed) if term]


def pick_random(items: list[Any], count: int, rng: random.Random | None = None) -> list[Any]:
    rng = rng or random.Random()
    if len(items) <= count:
        return list(items)
    shuffled = list(items)
    for i in range(len(shuffled) - 1, 0, -1):
        j = rng.randint(0, i)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled[:count]


def to_iso_string(value_ms: float | None) -> str | None:
    if value_ms is None:
        return None
    return (
        datetime.fromtimestamp(value_ms / 1000, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


# --- derived data (stats + homepage); runtime caches it by revision ------------


def get_derived_data(
    con: sqlite3.Connection,
    config: dict[str, Any],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    total_pages, total_words = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM pages"
    ).fetchone()

    top_backlinks = [
        {"page": row[0], "count": row[1]}
        for row in con.execute(
            """
            SELECT
              COALESCE(p.title, MIN(b.target_raw)) AS page,
              CAST(SUM(b.occurrence_count) AS INTEGER) AS count
            FROM backlinks b
            LEFT JOIN pages p ON p.slug = b.target_slug
            GROUP BY b.target_slug
            ORDER BY count DESC, page ASC
            LIMIT 15
            """
        ).fetchall()
    ]

    visible_rows = con.execute(
        """
        SELECT
          file, slug, title, summary,
          word_count, modified_at, backlink_count,
          category_names_json, is_person
        FROM pages
        """
    ).fetchall()
    visible_rows = sorted(visible_rows, key=lambda row: row[0])

    page_summaries = [
        {
            "file": row[0],
            "slug": row[1],
            "title": row[2],
            "summary": row[3],
            "wordCount": row[4],
            "modifiedAt": row[5],
            "backlinkCount": row[6],
        }
        for row in visible_rows
    ]
    page_summaries_by_file = {page["file"]: page for page in page_summaries}

    recent_pages = sorted(page_summaries, key=lambda page: -page["modifiedAt"])[:6]
    top_connected = sorted(
        page_summaries, key=lambda page: (-page["backlinkCount"], -page["modifiedAt"])
    )[:6]

    hidden_topics = config["categories"]["hidden"]
    aliases = config["categories"]["aliases"]
    topic_pages: dict[str, list[dict[str, Any]]] = {}
    for row in visible_rows:
        page = page_summaries_by_file.get(row[0])
        if page is None:
            continue
        for topic in parse_json_array(row[7]):
            if is_topic_hidden(topic, hidden_topics):
                continue
            label = get_topic_label(topic, aliases)
            topic_pages.setdefault(label, []).append(page)

    categories = []
    for name, pages in topic_pages.items():
        deduped = list({page["file"]: page for page in pages}.values())
        deduped.sort(key=lambda page: (-page["backlinkCount"], -page["modifiedAt"]))
        categories.append({
            "name": name,
            "emoji": get_topic_emoji(name, aliases),
            "count": len(deduped),
            "pages": deduped,
        })
    categories = [category for category in categories if category["count"] > 0]
    categories.sort(
        key=lambda category: (
            -category["count"],
            -(category["pages"][0]["backlinkCount"] if category["pages"] else 0),
            category["name"],
        )
    )
    categories = categories[: config["categories"]["maxTopics"]]

    people = sorted(
        (
            page_summaries_by_file[row[0]]
            for row in visible_rows
            if row[8] == 1 and row[0] in page_summaries_by_file
        ),
        key=lambda page: (-page["backlinkCount"], page["title"]),
    )

    return {
        "stats": {
            "total_pages": total_pages,
            "total_words": total_words,
            "top_backlinks": top_backlinks,
        },
        "homepage": {
            "totalPages": total_pages,
            "totalWords": total_words,
            "featured": pick_random(page_summaries, 4, rng),
            "recentPages": recent_pages,
            "categories": categories,
            "topConnected": top_connected,
            "people": people,
        },
    }


def canonical_slug_from_route_parts(slug_parts: list[str]) -> str:
    decoded_parts = decode_slug_parts(slug_parts)
    if not decoded_parts:
        raise InvalidWikiSlug("Invalid wiki slug")
    for part in decoded_parts:
        if part in (".", "..") or "\x00" in part or "\\" in part:
            raise InvalidWikiSlug("Invalid wiki slug")
    return "/".join(encode_uri_component(part) for part in decoded_parts)


def search_wiki(con: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    terms = normalize_search_terms(query)
    if not terms:
        return []

    fts_query = build_fts_query(terms)
    try:
        candidates = con.execute(
            """
            SELECT
              p.file, p.title, p.title_lower, p.content_lower, p.markdown
            FROM pages_fts f
            JOIN pages p ON p.file = f.file
            WHERE pages_fts MATCH ?
            ORDER BY bm25(pages_fts)
            LIMIT 80
            """,
            (fts_query,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []

    results: list[dict[str, Any]] = []
    for file, title, title_lower, content_lower, markdown in candidates:
        score = 0
        matched_terms: set[str] = set()

        for term in terms:
            if term in title_lower:
                score += 10
                matched_terms.add(term)
            count = count_term_occurrences(content_lower, term)
            if count > 0:
                score += count
                matched_terms.add(term)

        if len(matched_terms) < len(terms) or score == 0:
            continue

        results.append({
            "file": file,
            "score": score,
            "matches": build_search_matches(markdown, title, terms),
        })

    results.sort(key=lambda result: -result["score"])
    return results[:20]


def get_graph_data(con: sqlite3.Connection, config: dict[str, Any]) -> dict[str, Any]:
    nodes = con.execute(
        """
        SELECT slug, title, summary, backlink_count, word_count, category_names_json
        FROM pages
        """
    ).fetchall()

    edges = [
        {"source": row[0], "target": row[1], "weight": row[2]}
        for row in con.execute(
            """
            SELECT p1.slug AS source, b.target_slug AS target, b.occurrence_count AS weight
            FROM backlinks b
            JOIN pages p1 ON p1.file = b.source_file
            JOIN pages p2 ON p2.slug = b.target_slug
            """
        ).fetchall()
    ]

    # dict keys preserve JS Set insertion order
    neighbor_map: dict[str, dict[str, None]] = {}
    for edge in edges:
        neighbor_map.setdefault(edge["source"], {})[edge["target"]] = None
        neighbor_map.setdefault(edge["target"], {})[edge["source"]] = None

    hidden_topics = config["categories"]["hidden"]
    visible_nodes = []
    for slug, title, summary, backlink_count, word_count, category_names_json in nodes:
        categories = parse_json_array(category_names_json)
        # JS keeps nodes with no categories or at least one non-hidden category
        if categories and all(is_topic_hidden(category, hidden_topics) for category in categories):
            continue
        visible_nodes.append({
            "slug": slug,
            "title": title,
            "backlinkCount": backlink_count,
            "wordCount": word_count,
            "categories": categories,
            "summary": summary,
            "neighbors": list(neighbor_map.get(slug, {})),
        })

    visible_slugs = {node["slug"] for node in visible_nodes}
    return {
        "nodes": [
            {**node, "neighbors": [slug for slug in node["neighbors"] if slug in visible_slugs]}
            for node in visible_nodes
        ],
        "edges": [
            edge
            for edge in edges
            if edge["source"] in visible_slugs and edge["target"] in visible_slugs
        ],
    }


def get_wiki_page(
    con: sqlite3.Connection,
    slug_parts: list[str],
    person_overrides: dict[str, str],
) -> dict[str, Any]:
    canonical_slug = canonical_slug_from_route_parts(slug_parts)
    row = con.execute(
        """
        SELECT
          file, slug, title, content_markdown, has_code_blocks,
          headings_json, modified_at, category_names_json, is_person
        FROM pages
        WHERE slug = ?
        """,
        (canonical_slug,),
    ).fetchone()

    if row is None:
        raise WikiPageNotFound("Wiki page not found")

    file, slug, title, content_markdown, has_code_blocks, headings_json, modified_at, category_names_json, is_person = row

    outbound = con.execute(
        """
        SELECT DISTINCT p.slug, p.title, p.backlink_count, p.category_names_json
        FROM backlinks b
        JOIN pages p ON p.slug = b.target_slug
        WHERE b.source_file = ?
        """,
        (file,),
    ).fetchall()

    inbound = con.execute(
        """
        SELECT DISTINCT p.slug, p.title, p.backlink_count, p.category_names_json
        FROM backlinks b
        JOIN pages p ON p.file = b.source_file
        WHERE b.target_slug = ?
        """,
        (slug,),
    ).fetchall()

    neighbor_map: dict[str, dict[str, Any]] = {}
    for neighbor_slug, neighbor_title, backlink_count, neighbor_categories in [*outbound, *inbound]:
        if neighbor_slug != slug:
            neighbor_map[neighbor_slug] = {
                "slug": neighbor_slug,
                "title": neighbor_title,
                "backlinkCount": backlink_count,
                "categories": parse_json_array(neighbor_categories),
            }

    neighbors = sorted(neighbor_map.values(), key=lambda neighbor: -neighbor["backlinkCount"])

    return {
        "slug": slug,
        "title": title,
        "fileName": file,
        "contentMarkdown": content_markdown,
        "hasCodeBlocks": has_code_blocks == 1,
        "headings": parse_json_array(headings_json),
        "modifiedAt": modified_at,
        "categories": parse_json_array(category_names_json),
        "neighbors": neighbors,
        "isPerson": is_person == 1,
        "personOverride": person_overrides.get(file, None),
    }
