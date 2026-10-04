"""Indexing pipeline — port of wiki-os src/lib/wiki-indexer.ts (MIT).

Functions take the engine object (duck-typed: wiki_root, config, overrides,
db, mark_revision_changed) instead of upstream's dependency-injection bags.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from . import db as wiki_db
from .classification import (
    derive_category_names,
    detect_person_page,
    extract_backlink_references,
    extract_summary,
)
from .markdown import parse_wiki_frontmatter, prepare_wiki_markdown
from .shared import (
    is_ignored_directory_name,
    normalize_relative_path,
    should_index_relative_file,
    slug_from_file_name,
    title_from_file_name,
)


def stat_mtime_ms(path: Path) -> float:
    # Matches Node's fs.stat().mtimeMs bit-for-bit (mtime seconds as double ×
    # 1000); st_mtime_ns/1e6 rounds the last ulp differently, which shows up
    # in API JSON.
    return path.stat().st_mtime * 1000.0


def collect_markdown_files(root: Path) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # prune ignored directories (deterministic order; final list is sorted anyway)
        dirnames[:] = sorted(d for d in dirnames if not is_ignored_directory_name(d))
        for name in sorted(filenames):
            full_path = Path(dirpath) / name
            if not full_path.is_file():
                continue
            relative = normalize_relative_path(full_path.relative_to(root).as_posix())
            if should_index_relative_file(relative):
                files.append(relative)
    return files


def load_indexed_wiki_page(
    engine: Any,
    file: str,
    modified_at_override: float | None = None,
) -> dict[str, Any] | None:
    wiki_root: Path = engine.wiki_root
    file_path = wiki_root / file

    try:
        markdown = file_path.read_text(encoding="utf-8")
        modified_at = stat_mtime_ms(file_path) if modified_at_override is None else modified_at_override
    except (FileNotFoundError, NotADirectoryError):
        return None

    config = engine.config
    title = title_from_file_name(file)
    frontmatter, body = parse_wiki_frontmatter(markdown)
    prepared = prepare_wiki_markdown(body)
    content_markdown: str = prepared["contentMarkdown"]
    category_names = derive_category_names(file, title, content_markdown, frontmatter, config)
    override = engine.overrides.get(file)
    is_person = detect_person_page(file, title, content_markdown, frontmatter, config, override)

    return {
        "file": file,
        "slug": slug_from_file_name(file),
        "title": title,
        "titleLower": title.lower(),
        "markdown": body,
        "contentMarkdown": content_markdown,
        "contentLower": content_markdown.lower(),
        # JS: contentMarkdown.split(/\s+/).filter(Boolean).length
        "wordCount": len(content_markdown.split()),
        "backlinkReferences": extract_backlink_references(body),
        "categoryNames": category_names,
        "hasCodeBlocks": prepared["hasCodeBlocks"],
        "headings": prepared["headings"],
        "modifiedAt": modified_at,
        "summary": extract_summary(content_markdown),
        "isPerson": is_person,
    }


def has_existing_index_artifacts(index_db_path: Path) -> bool:
    return any(
        path.exists()
        for path in (index_db_path, Path(f"{index_db_path}-wal"), Path(f"{index_db_path}-shm"))
    )


def quarantine_corrupt_index_files(index_db_path: Path, timestamp_ms: int) -> None:
    for file_path in (index_db_path, Path(f"{index_db_path}-wal"), Path(f"{index_db_path}-shm")):
        for attempt in range(5):
            try:
                file_path.rename(f"{file_path}.corrupt-{timestamp_ms}")
                break
            except FileNotFoundError:
                break
            except OSError:
                if attempt < 4:
                    time.sleep(0.05 * (2**attempt))
                    continue
                if file_path != index_db_path:
                    break
                raise


def sync_single_path(engine: Any, relative_path: str) -> bool:
    con = engine.db
    wiki_root: Path = engine.wiki_root
    normalized = normalize_relative_path(relative_path)
    if not normalized or not normalized.endswith(".md"):
        return False

    if not should_index_relative_file(normalized):
        return wiki_db.delete_page_by_file(con, normalized)

    absolute_path = wiki_root / normalized
    try:
        mtime_ms = stat_mtime_ms(absolute_path)
    except (FileNotFoundError, NotADirectoryError):
        return wiki_db.delete_page_by_file(con, normalized)
    if not absolute_path.is_file():
        return wiki_db.delete_page_by_file(con, normalized)

    existing_modified_at = wiki_db.select_page_modified_at(con, normalized)
    if existing_modified_at is not None and abs(existing_modified_at - mtime_ms) < 0.5:
        return False

    page = load_indexed_wiki_page(engine, normalized, mtime_ms)
    if page is None:
        return wiki_db.delete_page_by_file(con, normalized)

    wiki_db.upsert_page_record(con, page)
    wiki_db.resolve_backlink_targets(con)
    wiki_db.resolve_page_content_links(con)
    return True


def reconcile_index_with_disk(engine: Any, force_all: bool = False) -> dict[str, int]:
    wiki_root: Path = engine.wiki_root
    if not wiki_root.is_dir():
        raise NotADirectoryError(f"WIKI_ROOT is not a directory: {wiki_root}")

    con = engine.db
    files = sorted(collect_markdown_files(wiki_root))
    file_set = set(files)
    existing_map = dict(wiki_db.list_indexed_pages(con))

    upserted = 0
    deleted = 0

    for file in files:
        full_path = wiki_root / file
        mtime_ms = stat_mtime_ms(full_path)
        modified_at = existing_map.get(file)
        needs_update = force_all or modified_at is None or abs(modified_at - mtime_ms) >= 0.5
        if not needs_update:
            continue

        page = load_indexed_wiki_page(engine, file, mtime_ms)
        if page is None:
            continue

        wiki_db.upsert_page_record(con, page)
        upserted += 1

    for existing_file in existing_map:
        if existing_file in file_set:
            continue
        if wiki_db.delete_page_by_file(con, existing_file):
            deleted += 1

    if upserted > 0 or deleted > 0:
        wiki_db.resolve_backlink_targets(con)
        wiki_db.resolve_page_content_links(con)
        engine.mark_revision_changed()

    return {"upserted": upserted, "deleted": deleted}
