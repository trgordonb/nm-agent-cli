"""Pure path/slug helpers — port of wiki-os src/lib/wiki-shared.ts + wiki-file-utils.ts (MIT).

slug encoding must match JS `encodeURIComponent` exactly: it leaves
A-Za-z0-9 and `-_.!~*'()` unescaped, escapes everything else (including `/`).
"""

from __future__ import annotations

import re
from urllib.parse import quote

# quote() already treats letters/digits/`_.-~` as safe; JS additionally
# leaves !'()* untouched.
def encode_uri_component(value: str) -> str:
    return quote(value, safe="!'()*")


def normalize_relative_path(value: str) -> str:
    return re.sub(r"^\.?/", "", value.replace("\\", "/")).strip()


def slug_parts_from_file_name(file_name: str) -> list[str]:
    without_extension = re.sub(r"\.md$", "", file_name, flags=re.IGNORECASE)
    return [encode_uri_component(part) for part in without_extension.split("/")]


def slug_from_file_name(file_name: str) -> str:
    return "/".join(slug_parts_from_file_name(file_name))


def title_from_file_name(file_name: str) -> str:
    without_extension = re.sub(r"\.md$", "", file_name, flags=re.IGNORECASE)
    parts = without_extension.split("/")
    return parts[-1] if parts else without_extension


def decode_slug_parts(parts: list[str]) -> list[str]:
    from urllib.parse import unquote

    decoded = []
    for part in parts:
        trimmed = unquote(part).strip()
        if trimmed:
            decoded.append(trimmed)
    return decoded


def is_ignored_directory_name(name: str) -> bool:
    return name.startswith("_") or name.startswith(".")


def should_index_relative_file(file: str) -> bool:
    if not file.endswith(".md"):
        return False

    normalized = normalize_relative_path(file)
    if not normalized:
        return False

    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return False

    base_name = parts[-1]
    if base_name.startswith("_") or base_name.startswith("."):
        return False

    return not any(is_ignored_directory_name(directory) for directory in parts[:-1])
