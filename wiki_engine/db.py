"""SQLite index layer — port of wiki-os src/lib/wiki-db.ts (MIT), including the
fork's bare-wikilink resolution patch (trgordonb/wiki-os bc4e7fe): wikilinks
reference bare note names ("[[overfitting]]") while page slugs are vault paths
("concepts/overfitting"), so backlink targets and rendered /wiki/ hrefs are
resolved against the indexed file list. Exact file matches win over
same-stem matches in subfolders; unresolvable targets keep their bare slug.
Both resolution passes are idempotent — resolved values re-resolve to themselves.
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Iterator
from urllib.parse import unquote

DEFAULT_WIKI_INDEX_CACHE_VERSION = 4
REQUIRED_INDEX_TABLES = ("pages", "backlinks", "categories", "pages_fts")

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS pages (
      file TEXT PRIMARY KEY,
      slug TEXT NOT NULL UNIQUE,
      title TEXT NOT NULL,
      title_lower TEXT NOT NULL,
      markdown TEXT NOT NULL,
      content_markdown TEXT NOT NULL,
      content_lower TEXT NOT NULL,
      word_count INTEGER NOT NULL,
      has_code_blocks INTEGER NOT NULL CHECK (has_code_blocks IN (0, 1)),
      headings_json TEXT NOT NULL,
      modified_at REAL NOT NULL,
      summary TEXT NOT NULL,
      is_person INTEGER NOT NULL CHECK (is_person IN (0, 1)),
      kind TEXT NOT NULL CHECK (kind IN ('page', 'source', 'raw')),
      category_names_json TEXT NOT NULL,
      backlink_count INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS backlinks (
      source_file TEXT NOT NULL REFERENCES pages(file) ON DELETE CASCADE,
      target_raw TEXT NOT NULL,
      target_slug TEXT NOT NULL,
      occurrence_count INTEGER NOT NULL,
      PRIMARY KEY (source_file, target_slug)
    );

    CREATE INDEX IF NOT EXISTS idx_pages_kind ON pages(kind);
    CREATE INDEX IF NOT EXISTS idx_pages_modified ON pages(modified_at DESC);
    CREATE INDEX IF NOT EXISTS idx_pages_backlink ON pages(backlink_count DESC, modified_at DESC);
    CREATE INDEX IF NOT EXISTS idx_backlinks_target_slug ON backlinks(target_slug);

    CREATE TABLE IF NOT EXISTS categories (
      name TEXT PRIMARY KEY,
      emoji TEXT NOT NULL,
      sort_order INTEGER NOT NULL
    );

    CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
      file UNINDEXED,
      slug UNINDEXED,
      title,
      content
    );
"""


def apply_db_pragmas(db: sqlite3.Connection) -> None:
    # Python's sqlite3 has no pragma() helper — execute each statement.
    for pragma in (
        "journal_mode = WAL",
        "synchronous = NORMAL",
        "foreign_keys = ON",
        "busy_timeout = 5000",
        "temp_store = MEMORY",
        "cache_size = -32768",
        "mmap_size = 268435456",
        "wal_autocheckpoint = 4000",
        "journal_size_limit = 67108864",
        "optimize = 0x10002",
    ):
        db.execute(f"PRAGMA {pragma}")


def open_index_db(index_db_path: str) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI runs sync routes on a threadpool; the
    # engine serializes writes behind its own lock. isolation_level=None gives
    # explicit transaction control (BEGIN/COMMIT), matching better-sqlite3.
    db = sqlite3.connect(index_db_path, check_same_thread=False, isolation_level=None)
    try:
        apply_db_pragmas(db)
    except Exception:
        db.close()
        raise
    return db


@contextmanager
def transaction(db: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except Exception:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


def run_db_migrations(db: sqlite3.Connection, cache_version: int = DEFAULT_WIKI_INDEX_CACHE_VERSION) -> None:
    db.executescript(SCHEMA_SQL)
    db.execute(f"PRAGMA user_version = {cache_version}")


def seed_category_rules(db: sqlite3.Connection, category_seeds: Iterable[dict[str, Any]]) -> None:
    with transaction(db):
        db.execute("DELETE FROM categories")
        for seed in category_seeds:
            db.execute(
                """
                INSERT INTO categories (name, emoji, sort_order)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                  emoji = excluded.emoji,
                  sort_order = excluded.sort_order
                """,
                (seed["name"], seed["emoji"], seed["sort_order"]),
            )


def run_startup_integrity_check(
    db: sqlite3.Connection,
    cache_version: int = DEFAULT_WIKI_INDEX_CACHE_VERSION,
) -> tuple[bool, str | None]:
    try:
        placeholders = ", ".join("?" for _ in REQUIRED_INDEX_TABLES)
        rows = db.execute(
            f"SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({placeholders})",
            REQUIRED_INDEX_TABLES,
        ).fetchall()
        table_names = {row[0] for row in rows}
        for table_name in REQUIRED_INDEX_TABLES:
            if table_name not in table_names:
                return False, f"missing required index table: {table_name}"

        user_version = db.execute("PRAGMA user_version").fetchone()[0]
        if user_version != cache_version:
            return False, (
                f"index user_version {user_version} is incompatible with cache version {cache_version}"
            )

        quick_check_rows = [row[0] for row in db.execute("PRAGMA quick_check").fetchall()]
        quick_check_error = next((row for row in quick_check_rows if row != "ok"), None)
        if quick_check_error:
            return False, f"quick_check failed: {quick_check_error}"

        fk_rows = db.execute("PRAGMA foreign_key_check").fetchall()
        if fk_rows:
            first = fk_rows[0]
            return False, (
                f"foreign_key_check failed on {first[0]} row {first[1]} -> {first[2]} "
                f"({len(fk_rows)} issue(s))"
            )

        return True, None
    except Exception as exc:
        message = str(exc).strip() or "startup integrity check failed"
        return False, message


def get_source_targets(db: sqlite3.Connection, source_file: str) -> list[str]:
    rows = db.execute(
        "SELECT target_slug FROM backlinks WHERE source_file = ?", (source_file,)
    ).fetchall()
    return [row[0] for row in rows]


def recompute_backlink_counts_for_slugs(db: sqlite3.Connection, slugs: Iterable[str]) -> None:
    unique_slugs = list({slug for slug in slugs if slug})
    if not unique_slugs:
        return
    with transaction(db):
        for slug in unique_slugs:
            row = db.execute(
                "SELECT COALESCE(SUM(occurrence_count), 0) FROM backlinks WHERE target_slug = ?",
                (slug,),
            ).fetchone()
            db.execute(
                "UPDATE pages SET backlink_count = ? WHERE slug = ?",
                (row[0] if row else 0, slug),
            )


def _aggregate_backlink_references(references: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for reference in references:
        existing = targets.get(reference["targetSlug"])
        if existing:
            existing["count"] += 1
        else:
            targets[reference["targetSlug"]] = {"targetRaw": reference["targetRaw"], "count": 1}
    return targets


def upsert_page_record(db: sqlite3.Connection, page: dict[str, Any]) -> None:
    previous_row = db.execute("SELECT slug FROM pages WHERE file = ?", (page["file"],)).fetchone()
    previous_slug = previous_row[0] if previous_row else None
    previous_targets = get_source_targets(db, page["file"])
    backlink_targets = _aggregate_backlink_references(page["backlinkReferences"])

    with transaction(db):
        db.execute(
            """
            INSERT INTO pages (
              file, slug, title, title_lower, markdown, content_markdown,
              content_lower, word_count, has_code_blocks, headings_json,
              modified_at, summary, is_person, kind, category_names_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'page', ?)
            ON CONFLICT(file) DO UPDATE SET
              slug = excluded.slug,
              title = excluded.title,
              title_lower = excluded.title_lower,
              markdown = excluded.markdown,
              content_markdown = excluded.content_markdown,
              content_lower = excluded.content_lower,
              word_count = excluded.word_count,
              has_code_blocks = excluded.has_code_blocks,
              headings_json = excluded.headings_json,
              modified_at = excluded.modified_at,
              summary = excluded.summary,
              is_person = excluded.is_person,
              kind = 'page',
              category_names_json = excluded.category_names_json
            """,
            (
                page["file"],
                page["slug"],
                page["title"],
                page["titleLower"],
                page["markdown"],
                page["contentMarkdown"],
                page["contentLower"],
                page["wordCount"],
                1 if page["hasCodeBlocks"] else 0,
                json.dumps(page["headings"]),
                page["modifiedAt"],
                page["summary"],
                1 if page["isPerson"] else 0,
                json.dumps(page["categoryNames"]),
            ),
        )

        db.execute("DELETE FROM backlinks WHERE source_file = ?", (page["file"],))
        for target_slug, target in backlink_targets.items():
            db.execute(
                "INSERT INTO backlinks (source_file, target_raw, target_slug, occurrence_count) VALUES (?, ?, ?, ?)",
                (page["file"], target["targetRaw"], target_slug, target["count"]),
            )

        db.execute("DELETE FROM pages_fts WHERE file = ?", (page["file"],))
        db.execute(
            "INSERT INTO pages_fts (file, slug, title, content) VALUES (?, ?, ?, ?)",
            (page["file"], page["slug"], page["title"], page["contentMarkdown"]),
        )

    affected_slugs = {page["slug"], *previous_targets, *backlink_targets.keys()}
    if previous_slug:
        affected_slugs.add(previous_slug)
    recompute_backlink_counts_for_slugs(db, affected_slugs)


def _resolve_wiki_link_slug(db: sqlite3.Connection, target_slug: str) -> str | None:
    file = f"{target_slug}.md"
    row = db.execute(
        """
        SELECT slug FROM pages
        WHERE file = ? OR file LIKE '%/' || ? || '.md'
        ORDER BY (CASE WHEN file = ? THEN 0 ELSE 1 END), slug
        LIMIT 1
        """,
        (file, target_slug, file),
    ).fetchone()
    return row[0] if row else None


def resolve_backlink_targets(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT rowid, source_file, target_raw, target_slug, occurrence_count FROM backlinks"
    ).fetchall()

    merged: dict[str, dict[str, Any]] = {}
    changed = False
    for row in rows:
        _rowid, source_file, target_raw, target_slug, occurrence_count = row
        resolved = _resolve_wiki_link_slug(db, target_slug) or target_slug
        if resolved != target_slug:
            changed = True
        key = f"{source_file}\x00{resolved}"
        existing = merged.get(key)
        if existing:
            existing["occurrence_count"] += occurrence_count
        else:
            merged[key] = {
                "source_file": source_file,
                "target_raw": target_raw,
                "target_slug": resolved,
                "occurrence_count": occurrence_count,
            }
    if not changed:
        return

    with transaction(db):
        db.execute("DELETE FROM backlinks")
        for row in merged.values():
            db.execute(
                "INSERT INTO backlinks (source_file, target_raw, target_slug, occurrence_count) VALUES (?, ?, ?, ?)",
                (row["source_file"], row["target_raw"], row["target_slug"], row["occurrence_count"]),
            )

    # Resolved targets change which pages receive backlinks; refresh all counts.
    db.execute(
        """
        UPDATE pages SET backlink_count = (
          SELECT COALESCE(SUM(occurrence_count), 0) FROM backlinks WHERE target_slug = pages.slug
        )
        """
    )


def resolve_page_content_links(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT file, slug, title, content_markdown FROM pages").fetchall()
    for file, slug, title, content_markdown in rows:
        if "](/wiki/" not in content_markdown:
            continue

        def repl(match: re.Match[str]) -> str:
            resolved = _resolve_wiki_link_slug(db, unquote(match.group(1)))
            return f"](/wiki/{resolved})" if resolved else match.group(0)

        rewritten = re.sub(r"\]\(/wiki/([^)\s]+)\)", repl, content_markdown)
        if rewritten != content_markdown:
            db.execute(
                "UPDATE pages SET content_markdown = ?, content_lower = lower(?) WHERE file = ?",
                (rewritten, rewritten.lower(), file),
            )
            db.execute("DELETE FROM pages_fts WHERE file = ?", (file,))
            db.execute(
                "INSERT INTO pages_fts (file, slug, title, content) VALUES (?, ?, ?, ?)",
                (file, slug, title, rewritten),
            )


def delete_page_by_file(db: sqlite3.Connection, file: str) -> bool:
    existing_row = db.execute("SELECT slug FROM pages WHERE file = ?", (file,)).fetchone()
    if not existing_row:
        return False

    previous_slug = existing_row[0]
    previous_targets = get_source_targets(db, file)

    with transaction(db):
        db.execute("DELETE FROM pages_fts WHERE file = ?", (file,))
        # backlinks rows cascade via the FK
        db.execute("DELETE FROM pages WHERE file = ?", (file,))

    recompute_backlink_counts_for_slugs(db, [previous_slug, *previous_targets])
    return True


def select_page_modified_at(db: sqlite3.Connection, file: str) -> float | None:
    row = db.execute("SELECT modified_at FROM pages WHERE file = ?", (file,)).fetchone()
    return row[0] if row else None


def list_indexed_pages(db: sqlite3.Connection) -> list[tuple[str, float]]:
    return db.execute("SELECT file, modified_at FROM pages").fetchall()
