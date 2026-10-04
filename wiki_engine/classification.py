"""Classification + search scoring — port of wiki-os src/lib/wiki-classification.ts (MIT).

Faithful algorithm port: category derivation, person detection, FTS query
building, and the deterministic re-scoring that decides final search order
(bm25 only picks the candidate pool, exactly as upstream).
"""

from __future__ import annotations

import re
from typing import Any

from .config import format_topic_label, get_topic_label, normalize_topic_key
from .markdown import WIKILINK_RE
from .shared import normalize_relative_path, slug_from_file_name

CONTENT_STOPWORDS = {
    "about", "after", "also", "because", "been", "being", "between", "could",
    "every", "first", "from", "have", "into", "local", "many", "more", "most",
    "note", "notes", "obsidian", "page", "their", "there", "these", "this",
    "through", "using", "what", "when", "where", "which", "wiki", "with", "your",
}

PERSON_BIOGRAPHY_KEYWORDS = [
    "born", "author", "writer", "engineer", "founder", "entrepreneur",
    "businessman", "businesswoman", "philosopher", "scientist", "mathematician",
    "physicist", "inventor", "emperor", "king", "queen", "president",
    "strategist", "scholar", "teacher", "coach", "artist", "actor", "actress",
    "comedian", "creator", "youtuber", "podcaster", "minister", "prophet",
    "imam", "saint", "poet", "historian", "essayist", "investor", "operator",
    "athlete", "runner", "soldier", "monk", "ceo", "doctor", "physician",
    "programmer", "researcher", "ruler", "revolutionary", "statesman",
]

PERSON_SECTION_HEADINGS = {
    "origin", "personal", "early life", "career", "ventures", "family",
    "legacy", "works", "biography", "life",
}

STRUCTURAL_FOLDER_TOPICS = {
    "topic", "topics", "note", "notes", "docs", "documents", "source", "sources",
}

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]{2,}")


def extract_summary(markdown: str) -> str:
    for line in markdown.split("\n"):
        trimmed = line.strip()
        if (
            len(trimmed) > 30
            and not trimmed.startswith("#")
            and not trimmed.startswith("-")
            and not trimmed.startswith("*")
            and not trimmed.startswith("[")
            and not trimmed.startswith("!")
        ):
            return trimmed[:180] + "..." if len(trimmed) > 180 else trimmed
    return ""


def to_string_array(value: Any) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(to_string_array(item))
        return [item for item in out if item]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def frontmatter_entries(frontmatter: dict[str, Any]) -> list[tuple[str, Any]]:
    return [(normalize_topic_key(key), value) for key, value in frontmatter.items()]


def collect_frontmatter_topics(frontmatter: dict[str, Any], config: dict[str, Any]) -> list[str]:
    matched: list[str] = []
    for key, value in frontmatter_entries(frontmatter):
        if key not in config["categories"]["frontmatterKeys"]:
            continue
        matched.extend(to_string_array(value))
    return matched


def collect_folder_topics(file: str, config: dict[str, Any]) -> list[str]:
    parts = [
        part
        for part in normalize_relative_path(file).split("/")[:-1]
        if (normalized := normalize_topic_key(part)) and normalized not in STRUCTURAL_FOLDER_TOPICS
    ]
    return parts[: config["categories"]["folderDepth"]]


def collect_heuristic_topics(title: str, markdown: str) -> list[str]:
    frequencies: dict[str, int] = {}
    for word in WORD_RE.findall(title) + WORD_RE.findall(markdown):
        normalized = normalize_topic_key(word)
        if (
            not normalized
            or len(normalized) < 4
            or normalized in CONTENT_STOPWORDS
            or re.fullmatch(r"\d+", normalized)
        ):
            continue
        frequencies[normalized] = frequencies.get(normalized, 0) + 1

    qualifying = [(key, count) for key, count in frequencies.items() if count >= 2]
    qualifying.sort(key=lambda item: (-item[1], item[0]))
    return [key for key, _ in qualifying[:3]]


def dedupe_topics(values: list[str], aliases: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    labels: list[str] = []
    for value in values:
        normalized = normalize_topic_key(value)
        if not normalized:
            continue
        label = get_topic_label(value, aliases)
        label_key = normalize_topic_key(label)
        if not label_key or label_key in seen:
            continue
        seen.add(label_key)
        labels.append(label)
    return labels


def derive_category_names(
    file: str,
    title: str,
    content_markdown: str,
    frontmatter: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    frontmatter_topics = collect_frontmatter_topics(frontmatter, config)
    folder_topics = collect_folder_topics(file, config)
    heuristic_topics = (
        []
        if frontmatter_topics or folder_topics
        else collect_heuristic_topics(title, content_markdown)
    )

    resolved = dedupe_topics(
        [format_topic_label(v) for v in [*frontmatter_topics, *folder_topics, *heuristic_topics]],
        config["categories"]["aliases"],
    )
    return resolved[:5]


def frontmatter_has_truthy_value(frontmatter: dict[str, Any], keys: list[str]) -> bool:
    for key, value in frontmatter_entries(frontmatter):
        if key not in keys:
            continue
        if isinstance(value, bool):
            if value:
                return True
            continue
        for item in to_string_array(value):
            if normalize_topic_key(item) in ("person", "people", "biography"):
                return True
    return False


def frontmatter_has_configured_person_tag(frontmatter: dict[str, Any], config: dict[str, Any]) -> bool:
    tag_names = config["people"]["tagNames"]
    return any(normalize_topic_key(topic) in tag_names for topic in collect_frontmatter_topics(frontmatter, config))


def detect_explicit_person_page(file: str, frontmatter: dict[str, Any], config: dict[str, Any]) -> bool:
    folder_names = [normalize_topic_key(part) for part in normalize_relative_path(file).split("/")[:-1]]
    if any(name in config["people"]["folderNames"] for name in folder_names):
        return True
    if frontmatter_has_truthy_value(frontmatter, config["people"]["frontmatterKeys"]):
        return True
    return frontmatter_has_configured_person_tag(frontmatter, config)


def escape_regex(value: str) -> str:
    # Same character set semantics as the TS escapeRegex (escaping extra
    # literal chars is harmless — an escaped '&' still matches '&').
    return re.escape(value)


def has_likely_person_name_title(title: str) -> int:
    tokens = [token for token in title.strip().split() if token]
    if not tokens or len(tokens) > 4:
        return 0
    valid_name_token = re.compile(r"^(?:[A-Z][a-z]+|[A-Z][a-z]+[-'][A-Za-z]+|[A-Z]\.|[A-Z][a-z]+\.)$")
    if not all(valid_name_token.match(token) for token in tokens):
        return 0
    return 2 if len(tokens) >= 2 else 1


def extract_lead_sentence(markdown: str) -> str:
    lines = [
        line.strip()
        for line in markdown.split("\n")
        if line.strip()
        and not line.strip().startswith("#")
        and not line.strip().startswith("-")
        and not line.strip().startswith("*")
        and not line.strip().startswith("[[")
    ]
    merged = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if not merged:
        return ""
    first_sentence = re.split(r"(?<=[.!?])\s+", merged)[0]
    return first_sentence[:240].lower()


def has_biography_summary_cue(title: str, markdown: str) -> bool:
    lead_sentence = extract_lead_sentence(markdown)
    if not lead_sentence:
        return False

    normalized_title = title.lower()
    lead_window = lead_sentence[:120]
    direct_biography_pattern = None
    if has_likely_person_name_title(title) >= 2:
        direct_biography_pattern = re.compile(
            rf"^{re.escape(normalized_title)}(?:\s*\([^)]*\))?\s+was\b"
        )

    if lead_sentence.startswith("born ") or (
        direct_biography_pattern is not None and direct_biography_pattern.search(lead_sentence)
    ):
        return True

    return any(
        re.search(rf"\b{re.escape(keyword)}\b", lead_window)
        for keyword in PERSON_BIOGRAPHY_KEYWORDS
    )


def has_biography_section_cue(markdown: str) -> bool:
    headings = re.findall(r"^#+\s+(.+)$", markdown, flags=re.MULTILINE)
    return any(
        normalize_topic_key(re.sub(r"^#+\s+", "", heading_line)) in PERSON_SECTION_HEADINGS
        for heading_line in headings
    )


def detect_person_from_content_heuristics(title: str, markdown: str) -> bool:
    score = has_likely_person_name_title(title)
    if has_biography_summary_cue(title, markdown):
        score += 2
    if has_biography_section_cue(markdown):
        score += 1
    return score >= 3


def detect_person_page(
    file: str,
    title: str,
    content_markdown: str,
    frontmatter: dict[str, Any],
    config: dict[str, Any],
    person_override: str | None = None,
) -> bool:
    if config["people"]["mode"] == "off":
        return False
    if person_override == "person":
        return True
    if person_override == "not-person":
        return False

    is_explicit_person = detect_explicit_person_page(file, frontmatter, config)
    if is_explicit_person or config["people"]["mode"] == "explicit":
        return is_explicit_person

    return detect_person_from_content_heuristics(title, content_markdown)


def count_term_occurrences(content: str, term: str) -> int:
    if not term:
        return 0
    count = 0
    start = 0
    while True:
        index = content.find(term, start)
        if index == -1:
            return count
        count += 1
        start = index + len(term)


def extract_backlink_references(markdown: str) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for match in WIKILINK_RE.finditer(markdown):
        raw_target = re.sub(r"^sources/", "", match.group(1).strip(), count=1)
        if not raw_target:
            continue
        target_file = raw_target if raw_target.endswith(".md") else raw_target + ".md"
        references.append({
            "targetRaw": raw_target,
            "targetSlug": slug_from_file_name(target_file),
        })
    return references


def aggregate_backlink_references(references: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for reference in references:
        existing = targets.get(reference["targetSlug"])
        if existing:
            existing["count"] += 1
        else:
            targets[reference["targetSlug"]] = {"targetRaw": reference["targetRaw"], "count": 1}
    return targets


def build_search_matches(markdown: str, title: str, terms: list[str]) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    current_heading = title

    for line in markdown.split("\n"):
        heading_match = re.match(r"^#+\s+(.+)", line)
        if heading_match:
            current_heading = heading_match.group(1)
            continue

        snippet = line.strip()
        if len(snippet) <= 10:
            continue

        line_lower = line.lower()
        if not any(term in line_lower for term in terms):
            continue

        key = f"{current_heading}\x00{snippet}"
        if key in seen:
            continue

        matches.append({"heading": current_heading, "snippet": snippet})
        seen.add(key)
        if len(matches) >= 3:
            break

    return matches


def build_fts_query(terms: list[str]) -> str:
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"*' for term in terms)
