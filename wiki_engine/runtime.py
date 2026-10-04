"""Engine runtime — collapses wiki-os wiki.ts + wiki-state.ts + wiki-watcher.ts
(MIT) into one class.

Replaces the fs.watch/debounce/crash-backoff machinery with a background
mtime-poll thread (default 10 s) + POST /api/admin/reindex for forced rebuilds
— functionally equivalent at personal-vault scale. All public methods take a
single lock (the data is small; queries are sub-millisecond), so FastAPI's
threadpool can share one connection safely.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any

from . import db as wiki_db
from . import indexer as wiki_indexer
from . import queries as wiki_queries
from .config import (
    DEFAULT_CONFIG,
    get_topic_emoji,
    get_topic_label,
    load_ui_config,
    resolve_config,
    resolve_index_db_path,
    resolve_overrides_path,
    resolve_wiki_root,
)


class WikiSetupRequired(Exception):
    """Mapped to 409 {error, code: "SETUP_REQUIRED"} by routes."""


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    tmp.replace(path)


def _build_category_seeds(config: dict[str, Any]) -> list[dict[str, Any]]:
    configured_topics = sorted(
        {
            label
            for topic in config["categories"]["aliases"]
            if (label := get_topic_label(topic, config["categories"]["aliases"]))
        }
    )
    return [
        {
            "name": topic,
            "emoji": get_topic_emoji(topic, config["categories"]["aliases"]),
            "sortOrder": index,
        }
        for index, topic in enumerate(configured_topics)
    ]


class WikiEngine:
    def __init__(self) -> None:
        self.wiki_root = resolve_wiki_root()
        self.db_path = resolve_index_db_path(self.wiki_root)
        self.overrides_path = resolve_overrides_path()
        self.config = resolve_config(load_ui_config())
        self.overrides: dict[str, str] = {}
        self._load_overrides()

        poll_env = os.getenv("WIKI_ENGINE_POLL_SECS")
        try:
            self.poll_secs = max(1.0, float(poll_env)) if poll_env else 10.0
        except ValueError:
            self.poll_secs = 10.0

        self._lock = threading.RLock()
        self._db: Any = None
        self._ready = False
        self._revision = 0
        self._cache_revision = -1
        self._derived_cache: dict[str, Any] | None = None
        self._rng = random.Random()
        self._integrity_ok: bool | None = None
        self._integrity_error: str | None = None
        self._last_sync_at_ms: float | None = None
        self._last_sync_error: str | None = None
        self._stop = threading.Event()
        self._poller: threading.Thread | None = None

    # --- overrides ---------------------------------------------------------------

    def _load_overrides(self) -> None:
        try:
            if self.overrides_path.is_file():
                with open(self.overrides_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                raw = data.get("person_overrides", {})
                if isinstance(raw, dict):
                    self.overrides = {
                        str(file): value
                        for file, value in raw.items()
                        if value in ("person", "not-person")
                    }
        except (OSError, json.JSONDecodeError):
            self.overrides = {}

    def set_person_override(self, file: str, override: str | None) -> dict[str, Any]:
        with self._lock:
            self._require_configured()
            if override is None:
                self.overrides.pop(file, None)
            elif override in ("person", "not-person"):
                self.overrides[file] = override
            else:
                raise ValueError("Invalid override value")

            _atomic_write_json(self.overrides_path, {"person_overrides": self.overrides})
            # is_person is baked into indexed rows; upstream does a full reindex too
            self.reindex()
            return {"ok": True, "file": file, "override": override}

    # --- lifecycle ----------------------------------------------------------------

    @property
    def db(self) -> Any:
        """Connection accessor used by indexer/queries (engine.db)."""
        return self._db

    def is_configured(self) -> bool:
        return self.wiki_root.is_dir()

    def _require_configured(self) -> None:
        if not self.is_configured():
            raise WikiSetupRequired("Vault setup required")

    def ensure_ready(self) -> None:
        with self._lock:
            self._require_configured()
            if self._ready and self._db is not None:
                return

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            fresh = not wiki_indexer.has_existing_index_artifacts(self.db_path)
            con = wiki_db.open_index_db(str(self.db_path))

            if fresh:
                wiki_db.run_db_migrations(con)
                wiki_db.seed_category_rules(con, _build_category_seeds(self.config))
                self._integrity_ok, self._integrity_error = True, None
            else:
                ok, error = wiki_db.run_startup_integrity_check(con)
                self._integrity_ok, self._integrity_error = ok, error
                if not ok:
                    con.close()
                    wiki_indexer.quarantine_corrupt_index_files(
                        self.db_path, int(time.time() * 1000)
                    )
                    con = wiki_db.open_index_db(str(self.db_path))
                    wiki_db.run_db_migrations(con)
                    wiki_db.seed_category_rules(con, _build_category_seeds(self.config))

            self._db = con
            try:
                wiki_indexer.reconcile_index_with_disk(self, force_all=fresh)
                self._last_sync_at_ms = time.time() * 1000
                self._last_sync_error = None
            except Exception as exc:
                self._last_sync_error = str(exc)
            self._ready = True

            if self._poller is None and not self._stop.is_set():
                self._poller = threading.Thread(
                    target=self._poll_loop, name="wiki-engine-poll", daemon=True
                )
                self._poller.start()

    def close(self) -> None:
        with self._lock:
            self._stop.set()
            if self._db is not None:
                self._db.close()
                self._db = None
            self._ready = False

    # --- revision / cache -----------------------------------------------------------

    def mark_revision_changed(self) -> None:
        self._revision += 1

    def _maybe_scan(self) -> None:
        """Incremental mtime reconcile — the poller's job; cheap no-op when
        nothing changed on disk."""
        try:
            wiki_indexer.reconcile_index_with_disk(self, force_all=False)
            self._last_sync_at_ms = time.time() * 1000
            self._last_sync_error = None
        except Exception as exc:
            self._last_sync_error = str(exc)

    def scan_now(self) -> None:
        with self._lock:
            self._require_configured()
            self.ensure_ready()
            self._maybe_scan()

    def _poll_loop(self) -> None:
        while not self._stop.wait(self.poll_secs):
            try:
                with self._lock:
                    if self._db is None:
                        continue
                    self._maybe_scan()
            except Exception:
                pass  # keep polling; the index stays usable

    def reindex(self) -> dict[str, Any]:
        with self._lock:
            self._require_configured()
            self.ensure_ready()
            wiki_indexer.reconcile_index_with_disk(self, force_all=True)
            self._last_sync_at_ms = time.time() * 1000
            self._last_sync_error = None
            derived = self._derived()
            return {
                "ok": True,
                "rebuiltAt": wiki_queries.to_iso_string(self._last_sync_at_ms),
                "totalPages": derived["stats"]["total_pages"],
                "totalWords": derived["stats"]["total_words"],
            }

    # --- reads ----------------------------------------------------------------------

    def _derived(self) -> dict[str, Any]:
        if self._derived_cache is not None and self._cache_revision == self._revision:
            return self._derived_cache
        derived = wiki_queries.get_derived_data(self._db, self.config, self._rng)
        self._derived_cache = derived
        self._cache_revision = self._revision
        return derived

    def get_config(self) -> dict[str, Any]:
        return self.config

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            self.ensure_ready()
            return self._derived()["stats"]

    def get_home(self) -> dict[str, Any]:
        with self._lock:
            self.ensure_ready()
            return self._derived()["homepage"]

    def search(self, query: str) -> list[dict[str, Any]]:
        with self._lock:
            self.ensure_ready()
            return wiki_queries.search_wiki(self._db, query)

    def graph(self) -> dict[str, Any]:
        with self._lock:
            self.ensure_ready()
            return wiki_queries.get_graph_data(self._db, self.config)

    def page(self, slug_parts: list[str]) -> dict[str, Any]:
        with self._lock:
            self.ensure_ready()
            return wiki_queries.get_wiki_page(self._db, slug_parts, self.overrides)

    def health(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_configured():
                raise WikiSetupRequired("Vault setup required")
            self.ensure_ready()
            pages_count = None
            fts_count = None
            try:
                row = self._db.execute(
                    "SELECT (SELECT COUNT(*) FROM pages), (SELECT COUNT(*) FROM pages_fts)"
                ).fetchone()
                pages_count, fts_count = row
                if pages_count == fts_count:
                    self._integrity_ok, self._integrity_error = True, None
                else:
                    self._integrity_ok = False
                    self._integrity_error = (
                        f"Page/FTS count mismatch: pages={pages_count}, fts={fts_count}"
                    )
            except Exception as exc:
                self._integrity_ok = False
                self._integrity_error = str(exc)

            return {
                "sync": {
                    "lastSyncAtMs": self._last_sync_at_ms,
                    "lastSyncAt": wiki_queries.to_iso_string(self._last_sync_at_ms),
                    "lastSyncError": self._last_sync_error,
                    "pollSecs": self.poll_secs,
                    "revision": self._revision,
                    "cacheRevision": self._cache_revision,
                },
                "integrity": {
                    "ok": self._integrity_ok,
                    "error": self._integrity_error,
                    "dbReady": self._db is not None,
                    "pagesCount": pages_count,
                    "ftsCount": fts_count,
                },
            }


_engine: WikiEngine | None = None
_engine_lock = threading.Lock()


def get_engine() -> WikiEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = WikiEngine()
    return _engine


def reset_engine() -> None:
    """Used by tests to point the engine at a different temp vault."""
    global _engine
    with _engine_lock:
        if _engine is not None:
            _engine.close()
        _engine = None
