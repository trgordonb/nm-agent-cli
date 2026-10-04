"""Markdown prep — line-exact port of wiki-os src/lib/markdown.ts (MIT).

No markdown library: frontmatter, wikilink transforms, heading extraction and
summaries are the same hand-rolled line/regex logic as upstream, so index
contents (and therefore search/graph behavior) match byte-for-byte.
"""

from __future__ import annotations

import re
from typing import Any

from .shared import slug_from_file_name

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def wikilink_href(target: str) -> str:
    return f"/wiki/{slug_from_file_name(target + '.md')}"


def transform_obsidian_links(markdown: str) -> str:
    def repl(match: re.Match[str]) -> str:
        raw_target = match.group(1)
        raw_label = match.group(2)
        target = raw_target.strip()
        label = (raw_label if raw_label is not None else raw_target).strip()
        return f"[{label}]({wikilink_href(target)})"

    return WIKILINK_RE.sub(repl, markdown)


def _parse_frontmatter_scalar(value: str) -> Any:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (
        trimmed.startswith("'") and trimmed.endswith("'")
    ):
        return trimmed[1:-1]
    if trimmed == "true":
        return True
    if trimmed == "false":
        return False
    if trimmed == "null":
        return None
    if re.fullmatch(r"-?\d+(?:\.\d+)?", trimmed):
        return float(trimmed) if "." in trimmed else int(trimmed)
    if trimmed.startswith("[") and trimmed.endswith("]"):
        inner = trimmed[1:-1]
        parts = [_parse_frontmatter_scalar(part) for part in inner.split(",")]
        return [part for part in parts if part != ""]
    return trimmed


def parse_wiki_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    normalized = markdown.replace("\r\n", "\n")

    if not normalized.startswith("---\n"):
        return {}, normalized

    lines = normalized.split("\n")
    frontmatter_lines: list[str] = []
    closing_index = -1

    for index in range(1, len(lines)):
        if lines[index] in ("---", "..."):
            closing_index = index
            break
        frontmatter_lines.append(lines[index])

    if closing_index == -1:
        return {}, normalized

    data: dict[str, Any] = {}

    index = 0
    while index < len(frontmatter_lines):
        line = frontmatter_lines[index]
        if re.match(r"^\s*-\s+", line):
            index += 1
            continue

        key_only = re.match(r"^([A-Za-z0-9_-]+):\s*$", line)
        if key_only:
            key = key_only.group(1)
            values: list[Any] = []
            next_index = index + 1
            while next_index < len(frontmatter_lines):
                list_item = re.match(r"^\s*-\s+(.+)$", frontmatter_lines[next_index])
                if not list_item:
                    break
                values.append(_parse_frontmatter_scalar(list_item.group(1)))
                next_index += 1
            data[key] = values
            index = next_index
            continue

        pair = re.match(r"^([A-Za-z0-9_-]+):\s*(.+)$", line)
        if not pair:
            index += 1
            continue

        data[pair.group(1)] = _parse_frontmatter_scalar(pair.group(2))
        index += 1

    body = "\n".join(lines[closing_index + 1:]).lstrip()
    return data, body


def strip_leading_markdown_title(markdown: str) -> str:
    return re.sub(r"^#\s+.+\n?", "", markdown, count=1).lstrip()


def create_heading_id(text: str) -> str:
    # JS \w is ASCII-only -> re.ASCII
    stripped = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.ASCII)
    return re.sub(r"\s+", "-", stripped)


def extract_markdown_headings(markdown: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for line in markdown.split("\n"):
        match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if not match:
            continue
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(2).replace("**", "")).strip()
        headings.append({"text": text, "id": create_heading_id(text), "level": len(match.group(1))})
    return headings


def prepare_wiki_markdown(markdown: str) -> dict[str, Any]:
    _, body = parse_wiki_frontmatter(markdown)
    content_markdown = strip_leading_markdown_title(transform_obsidian_links(body))
    return {
        "contentMarkdown": content_markdown,
        "hasCodeBlocks": "```" in content_markdown,
        "headings": extract_markdown_headings(content_markdown),
    }
