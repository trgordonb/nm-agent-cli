"""UI/runtime config — port of wiki-os src/lib/wiki-config.ts + the fork's
wiki-os.config.ts (MIT).

The fork's shipped config equals the defaults (`people.mode: "explicit"` is
the TS default too), so DEFAULT_CONFIG is what the engine serves. An optional
JSON override file (~/.wiki-os-py/ui-config.json) is merged through the same
resolve logic upstream used for wiki-os.config.ts.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HOMEPAGE_SECTION_KEYS = ["featured", "topConnected", "people", "recentPages"]

DEFAULT_CONFIG: dict[str, Any] = {
    "siteTitle": "WikiOS",
    "tagline": "Plug-and-play Obsidian wiki for search, browsing, and local knowledge graphs.",
    "searchPlaceholder": "Search notes, ideas, and people...",
    "navigation": {
        "graphLabel": "Graph",
        "statsLabel": "Stats",
        "backToWikiLabel": "Back to wiki",
        "articlesLabel": "articles",
        "conceptsLabel": "concepts",
        "connectionsLabel": "connections",
    },
    "homepage": {
        "sectionOrder": list(HOMEPAGE_SECTION_KEYS),
        "labels": {
            "featured": "Discover",
            "topConnected": "Most Connected",
            "people": "People",
            "recentPages": "Recently Added",
            "spotlightBadge": "Spotlight",
            "statsEyebrow": "Wiki Snapshot",
            "statsDescription": "A live view of the Obsidian wiki index and backlink graph.",
        },
    },
    "theme": {"variables": {}},
    "categories": {
        "aliases": {},
        "hidden": [],
        "maxTopics": 6,
        "folderDepth": 2,
        "frontmatterKeys": ["tags", "topics", "topic", "category", "categories"],
    },
    "people": {
        "enabled": True,
        "mode": "explicit",
        "frontmatterKeys": ["person", "people", "type", "kind", "entity"],
        "folderNames": ["people", "person", "biographies", "biography"],
        "tagNames": ["person", "people", "biography", "biographies"],
    },
}


def normalize_topic_key(value: str) -> str:
    # TS: value.trim().toLowerCase().replace(/^#/, "").replace(/[_-]+/g, " ")
    #        .replace(/\s+/g, " ")  — note: no final trim.
    value = value.strip().lower()
    value = re.sub(r"^#", "", value, count=1)
    value = re.sub(r"[_-]+", " ", value)
    return re.sub(r"\s+", " ", value)


def format_topic_label(value: str) -> str:
    # TS: trim → strip one leading '#' → [\\/]+ → ' ' → [_-]+ → ' ' → \s+ → ' '
    normalized = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", re.sub(r"[/\\]+", " ", re.sub(r"^#", "", value.strip(), count=1))))
    if not normalized:
        return ""
    words = normalized.split(" ")
    out = []
    for word in words:
        if word == word.upper() or re.fullmatch(r"\d+", word):
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def get_topic_alias(topic: str, aliases: dict[str, Any]) -> dict[str, Any] | None:
    return aliases.get(normalize_topic_key(topic))


def get_topic_label(topic: str, aliases: dict[str, Any]) -> str:
    alias = get_topic_alias(topic, aliases)
    label = alias.get("label") if alias else None
    return label if isinstance(label, str) and label else format_topic_label(topic)


TOPIC_COLOR_PALETTE = [
    "#85b9c9", "#f4b183", "#c4a7e7", "#9cc5a6",
    "#d4a55c", "#e28c8c", "#7db7a1", "#8aa7e1",
]

TOPIC_EMOJI_PALETTE = ["🧠", "📚", "🧭", "⚙️", "🌱", "🔬", "✨", "🗂️"]


def hash_string(value: str) -> int:
    # JS: hash = (hash * 31 + charCodeAt(0)) >>> 0 — 32-bit unsigned wrap
    hash_value = 0
    for character in value:
        hash_value = (hash_value * 31 + ord(character)) & 0xFFFFFFFF
    return hash_value


def get_topic_color(topic: str, aliases: dict[str, Any]) -> str:
    alias = get_topic_alias(topic, aliases)
    if alias and isinstance(alias.get("color"), str) and alias["color"]:
        return alias["color"]
    key = normalize_topic_key(topic) or topic
    return TOPIC_COLOR_PALETTE[hash_string(key) % len(TOPIC_COLOR_PALETTE)]


def get_topic_emoji(topic: str, aliases: dict[str, Any]) -> str:
    alias = get_topic_alias(topic, aliases)
    if alias and isinstance(alias.get("emoji"), str) and alias["emoji"]:
        return alias["emoji"]
    key = normalize_topic_key(topic) or topic
    return TOPIC_EMOJI_PALETTE[hash_string(key) % len(TOPIC_EMOJI_PALETTE)]


def is_topic_hidden(topic: str, hidden_topics: list[str]) -> bool:
    return normalize_topic_key(topic) in hidden_topics


def _unique_strings(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values or []:
        trimmed = str(value).strip()
        if trimmed and trimmed not in seen:
            seen.add(trimmed)
            out.append(trimmed)
    return out


def resolve_config(input_config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Same merge semantics as resolveWikiOsConfig in the TS engine."""
    cfg = input_config or {}

    def pick(section: str, key: str) -> str:
        raw = cfg.get(section, {}).get(key) if isinstance(cfg.get(section), dict) else None
        trimmed = raw.strip() if isinstance(raw, str) else ""
        return trimmed or DEFAULT_CONFIG[section][key]

    def pick_root(key: str) -> str:
        raw = cfg.get(key)
        trimmed = raw.strip() if isinstance(raw, str) else ""
        return trimmed or DEFAULT_CONFIG[key]

    section_order = [
        s
        for s in (cfg.get("homepage", {}).get("sectionOrder") or [])
        if s in HOMEPAGE_SECTION_KEYS
    ] or list(DEFAULT_CONFIG["homepage"]["sectionOrder"])

    labels_in = cfg.get("homepage", {}).get("labels") or {}
    homepage_labels = {
        key: (
            labels_in.get(key, "").strip()
            if isinstance(labels_in.get(key), str)
            else ""
        )
        or DEFAULT_CONFIG["homepage"]["labels"][key]
        for key in DEFAULT_CONFIG["homepage"]["labels"]
    }

    aliases_in = cfg.get("categories", {}).get("aliases") or {}
    aliases = {
        normalize_topic_key(k): v
        for k, v in aliases_in.items()
        if normalize_topic_key(k)
    }

    people_mode = cfg.get("people", {}).get("mode")
    if people_mode not in ("explicit", "hybrid", "off"):
        people_mode = "off" if cfg.get("people", {}).get("enabled") is False else DEFAULT_CONFIG["people"]["mode"]

    return {
        "siteTitle": pick_root("siteTitle"),
        "tagline": pick_root("tagline"),
        "searchPlaceholder": pick_root("searchPlaceholder"),
        "navigation": {key: pick("navigation", key) for key in DEFAULT_CONFIG["navigation"]},
        "homepage": {
            "sectionOrder": section_order,
            "labels": homepage_labels,
        },
        "theme": {
            "variables": {
                **DEFAULT_CONFIG["theme"]["variables"],
                **(cfg.get("theme", {}).get("variables") or {}),
            }
        },
        "categories": {
            "aliases": aliases,
            "hidden": _unique_strings(
                [normalize_topic_key(t) for t in (cfg.get("categories", {}).get("hidden") or DEFAULT_CONFIG["categories"]["hidden"])]
            ),
            "maxTopics": max(1, int(cfg.get("categories", {}).get("maxTopics") or DEFAULT_CONFIG["categories"]["maxTopics"])),
            "folderDepth": max(0, int(cfg.get("categories", {}).get("folderDepth") if cfg.get("categories", {}).get("folderDepth") is not None else DEFAULT_CONFIG["categories"]["folderDepth"])),
            "frontmatterKeys": _unique_strings(
                cfg.get("categories", {}).get("frontmatterKeys") or DEFAULT_CONFIG["categories"]["frontmatterKeys"]
            ),
        },
        "people": {
            "enabled": people_mode != "off",
            "mode": people_mode,
            "frontmatterKeys": [
                normalize_topic_key(t)
                for t in _unique_strings(
                    cfg.get("people", {}).get("frontmatterKeys") or DEFAULT_CONFIG["people"]["frontmatterKeys"]
                )
            ],
            "folderNames": [
                normalize_topic_key(t)
                for t in _unique_strings(
                    cfg.get("people", {}).get("folderNames") or DEFAULT_CONFIG["people"]["folderNames"]
                )
            ],
            "tagNames": [
                normalize_topic_key(t)
                for t in _unique_strings(
                    cfg.get("people", {}).get("tagNames") or DEFAULT_CONFIG["people"]["tagNames"]
                )
            ],
        },
    }


# --- deployment paths -------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_state_dir() -> Path:
    # Read lazily (not at import) so tests can redirect state per-test via env.
    return Path(os.getenv("WIKI_ENGINE_STATE_DIR", str(Path.home() / ".wiki-os-py")))


def resolve_wiki_root() -> Path:
    """Vault location: WIKI_ROOT env wins; default <repo>/wiki (start.sh used
    to export exactly this before booting the Node engine)."""
    raw = os.getenv("WIKI_ROOT")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return REPO_ROOT / "wiki"


def resolve_index_db_path(wiki_root: Path) -> Path:
    raw = os.getenv("WIKI_ENGINE_DB")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    import hashlib

    digest = hashlib.sha1(str(wiki_root).encode("utf-8")).hexdigest()
    return get_state_dir() / "indexes" / f"{digest}.sqlite"


def resolve_overrides_path() -> Path:
    raw = os.getenv("WIKI_ENGINE_CONFIG")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return get_state_dir() / "config.json"


def load_ui_config() -> dict[str, Any]:
    """Optional cosmetic override file (same shape as wiki-os.config.ts)."""
    path = get_state_dir() / "ui-config.json"
    try:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}
