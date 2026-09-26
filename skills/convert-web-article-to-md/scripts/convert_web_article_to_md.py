#!/usr/bin/env python3
"""Convert a math/code-heavy web article into AI-agent-readable Markdown.

Why this exists: fetched-markdown services (web readers, one-shot URL->MD
converters) routinely DESTROY math and code on technical blogs. Math is often
authored as raw LaTeX in loose HTML text (``\\begin{eqnarray}...\\end{eqnarray}``
between <p> tags, ``\\( ... \\)`` inline) which those converters drop, and
Prism/Pygments code blocks get stripped or left as highlighted HTML soup.
This script works from the raw HTML instead and recovers both.

Pipeline:
  fetch (or read) raw HTML -> isolate the article body -> drop site chrome ->
  recover math (loose TeX, MathJax v2 scripts, KaTeX annotations) into
  $...$ / $$...$$ -> protect math + code behind placeholder tokens ->
  markdownify the rest -> substitute tokens back -> download content images
  to media/ -> verification report.

Depends only on beautifulsoup4, markdownify, requests (already project deps).

Usage:
  python convert_web_article_to_md.py <url-or-html-file> [more...] [-o PARENT]
                                      [--no-media]

Output (per input): <parent>/<slug>/<slug>.md + media/ + raw.html, and a
report with counts and warnings. Warnings are the contract: anything listed
under "Needs human/agent attention" must be fixed by hand (see
../references/math-and-code-rules.md) before the result is called done.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import markdownify as md

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
TIMEOUT = 30

# Class/id/url substrings that mark site chrome rather than article content.
CHROME_PAT = re.compile(
    r"advert|\bad[-_s]|[-_]ads?\b|banner|sponsor|sidebar|share|social-"
    r"|newsletter|subscribe|cookie|related[-_]?posts?|recommended|trending"
    r"|popup|modal|breadcrumb|pagination|post-nav(igation)?|site-header"
    r"|site-footer|nav\b|navbar|menu\b|widget|promo|author-box|author-bio"
    r"|byline|comments?(\b|-list|-section)|disqus|giscus|utterances|search"
    r"|footer|header\b|masthead|skip-|scroll-top|back-to-top|cta\b|optin",
    re.I,
)
IMG_JUNK_PAT = re.compile(
    r"advert|\bad[-_/.]|[-_]ad\.|banner|sponsor|sidebar|avatar|logo|icon"
    r"|emoji|badge|pixel|track|share|social|button|flag|rating|placeholder"
    r"|spinner|loading|blank\.|1x1", re.I,
)

# Environments that may appear as loose TeX text nodes between block elements.
MATH_ENV_RE = re.compile(
    r"^\\begin\{(equation\*?|align\*?|alignat\*?|flalign\*?|gather\*?"
    r"|multline\*?|eqnarray\*?|split|cases|dcases|aligned|gathered"
    r"|array|[bpvBV]matrix)\}"
)
EXT_BY_TYPE = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
               "image/gif": ".gif", "image/svg+xml": ".svg"}
SKIP_MATH_ANCESTORS = ("pre", "code", "script", "style", "textarea", "kbd", "samp")

DISPLAY_TEX_RE = re.compile(r"\\\[(.+?)\\\]", re.S)
INLINE_TEX_RE = re.compile(r"\\\((.+?)\\\)", re.S)
DISPLAY_DOLLAR_RE = re.compile(r"(?<!\\)\$\$(.+?)\$\$", re.S)
INLINE_DOLLAR_RE = re.compile(r"(?<!\\)(?<!\$)\$([^$\n]+?)\$(?!\$)")
# Every bare _ and ^ in prose text is protected verbatim. Sites that author
# math as plain text rely on these characters, and renderers split text into
# multiple nodes (around literal *, <em>, entities...), so a subscript can be
# orphaned at a node boundary (")_{ik}" starting a node) where prefix-matching
# regexes can't see it. markdownify normalises _-emphasis pairs to * and
# escapes the rest (\_), mangling subscripts either way — observed:
# (b b^T)_{ik} -> (b b^T)*{ik}. Token-restore is verbatim, so over-matching
# is lossless; <pre>/<code> and $-math are excluded (already fenced/tokenized).
MATHISH_RE = re.compile(r"(?<!\\)[_^]")

# Tail-of-article CTA chrome. Modern sites (Tailwind-style utility classes)
# embed sign-up boxes inside the article container with no semantic class, so
# class-based removal can't see them. These markers are only truncated when
# followed by explicit CTA vocabulary, and never for # headings.
CTA_MARKER_RE = re.compile(
    r"^(want to go deeper|next step\b|final step\b|keep reading|"
    r"related (articles?|posts?)|continue reading|sign up\b|subscribe\b|"
    r"join (our|the)\b|get started)\b", re.I,
)
CTA_VOCAB_RE = re.compile(
    r"sign[ -]?in\b|sign[ -]?up\b|subscribe\b|newsletter\b|create (your|a) "
    r"(free )?account|start (your )?free|open your free|for free\b|"
    r"free (workspace|lesson|course|plan|trial|account|prep)|prep workspace|"
    r"get started", re.I,
)
# Headings that are always CTA chrome, never article sections ("Next steps"
# and "Related work" ARE real sections, so only these explicit phrases may
# match when heading-formatted).
ALWAYS_CTA_HEAD_RE = re.compile(
    r"^#{1,6}\s*(want to go deeper|keep reading|continue reading)\b", re.I)

LANG_PATTERNS = [
    re.compile(r"language-([\w+#.-]+)", re.I),
    re.compile(r"lang-([\w+#.-]+)", re.I),
    re.compile(r"highlight-source-([\w+#.-]+)", re.I),
    re.compile(r"brush:\s*([\w+#.-]+)", re.I),
    re.compile(r"highlight(?:\s+highlight)?-([\w+#.-]+)", re.I),
]
LANG_ALIAS = {
    "py": "python", "python3": "python", "rb": "ruby", "sh": "bash",
    "shell": "bash", "zsh": "bash", "console": "bash", "terminal": "bash",
    "js": "javascript", "node": "javascript", "ts": "typescript",
    "golang": "go", "c++": "cpp", "csharp": "csharp", "cs": "csharp",
    "yml": "yaml", "md": "markdown", "r": "r", "text": "", "plain": "",
    "plaintext": "", "none": "", "tex": "latex",
}


class ConversionError(Exception):
    pass


# --------------------------------------------------------------------------
# Fetching / input
# --------------------------------------------------------------------------

def fetch_url(url: str) -> str:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ConversionError(f"fetch failed: {exc}") from exc
    if resp.status_code in (401, 403, 429, 503):
        raise ConversionError(
            f"HTTP {resp.status_code} from {url} — the site is blocking scripts. "
            "Open the page in a real browser (or the browser-use skill), save the "
            "rendered DOM to an .html file, and convert the file instead."
        )
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value.strip(), re.I))


# --------------------------------------------------------------------------
# Metadata (read from the full page before chrome is stripped)
# --------------------------------------------------------------------------

def strip_title_suffix(title: str, site: str) -> str:
    """Drop a trailing "| Site Name" / "– Site" separator baked into page titles."""
    if not title or not site:
        return title
    site_core = re.sub(r"^www\.", "", site.lower())
    site_core = site_core.split(".")[0]
    parts = re.split(r"\s+[|–—·]\s+|\s+-\s+", title)
    if len(parts) > 1:
        last = re.sub(r"[^a-z0-9]", "", parts[-1].lower())
        if len(last) >= 3 and (last in site_core or site_core.startswith(last)):
            parts.pop()
            return " ".join(parts)
    return title


def extract_meta(soup: BeautifulSoup, source_url: str | None) -> dict[str, str]:
    def meta(*selectors: str) -> str:
        for sel in selectors:
            tag = soup.select_one(sel)
            if tag:
                value = tag.get("content") or tag.get("datetime") or tag.get_text(strip=True)
                if value:
                    return value.strip()
        return ""

    site = meta('meta[property="og:site_name"]')
    title = meta('meta[property="og:title"]', "title")
    canonical = ""
    link_canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    if link_canon and link_canon.get("href"):
        canonical = urljoin(source_url or "", link_canon["href"])
    if source_url:
        parsed = urlparse(source_url)
        if not site:
            site = parsed.netloc.removeprefix("www.")
    return {
        "title": strip_title_suffix(title, site),
        "source": canonical or (source_url or ""),
        "site": site,
        "author": meta('meta[name="author"]', 'meta[property="article:author"]'),
        "published": meta(
            'meta[property="article:published_time"]', 'meta[name="date"]',
            'meta[name="pubdate"]', "time[datetime]",
        ),
        "description": meta('meta[name="description"]', 'meta[property="og:description"]'),
    }


# --------------------------------------------------------------------------
# Body isolation and chrome removal
# --------------------------------------------------------------------------

def drop_useless_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "template", "svg",
                              "form", "button", "input", "select", "video", "audio"]):
        # MathJax v2 stores the original TeX in script[type=math/tex] — keep it.
        if tag.name == "script" and re.match(r"^math/tex", tag.get("type") or ""):
            continue
        tag.decompose()
    for frame in soup.find_all("iframe"):
        src = frame.get("src", "")
        if src:
            frame.replace_with(NavigableString(f" [embedded content: {src}] "))
        else:
            frame.decompose()


def find_container(soup: BeautifulSoup) -> Tag:
    candidates: list[Tag] = []
    for sel in ("article", '[role="main"]', "main",
                '[class*="post-content"]', '[class*="article-content"]',
                '[class*="entry-content"]', '[class*="post-body"]',
                '[class*="article-body"]', '[class*="markdown-body"]',
                '[id*="post-content"]', '[id*="content"]'):
        candidates.extend(tag for tag in soup.select(sel) if isinstance(tag, Tag))
    if not candidates:
        candidates = [soup.body or soup]

    best, best_score = None, -1.0
    for cand in candidates:
        text = cand.get_text(" ", strip=True)
        score = len(text) + 1000 * len(cand.find_all("pre"))
        # Prefer the smallest container that still holds nearly all the text:
        # deeper matches (e.g. article inside main) score similarly, so prefer
        # the more specific tag by discounting wrappers whose text is 95%+ of
        # their parent's — handled implicitly because parents score slightly
        # higher while children win on specificity order. Keep it simple:
        if score > best_score:
            best, best_score = cand, score
    return best


def remove_chrome(container: Tag) -> int:
    """Remove nav/ads/related/cookie blocks. Returns number of removed nodes."""
    removed = 0
    total_text = len(container.get_text(" ", strip=True))
    for tag in container.find_all(["nav", "aside", "footer", "header"]):
        if len(tag.get_text(" ", strip=True)) <= total_text * 0.5:
            tag.decompose()
            removed += 1
    for tag in container.find_all(True):
        marker = " ".join(filter(None, [" ".join(tag.get("class", [])), tag.get("id", "")]))
        if marker and CHROME_PAT.search(marker):
            # Safety valve: never remove something that holds half the article.
            if len(tag.get_text(" ", strip=True)) <= total_text * 0.5:
                tag.decompose()
                removed += 1
    return removed


# --------------------------------------------------------------------------
# Math recovery
# --------------------------------------------------------------------------

def in_math_free_zone(node: Tag) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.name in SKIP_MATH_ANCESTORS:
            return True
        parent = parent.parent
    return False


def eqnarray_to_aligned(tex: str) -> str:
    tex = re.sub(r"\\begin\{eqnarray\*?\}", r"\\begin{aligned}", tex)
    tex = re.sub(r"\\end\{eqnarray\*?\}", r"\\end{aligned}", tex)
    return tex


def convert_mathjax_scripts(soup: BeautifulSoup) -> int:
    """MathJax v2 leaves the original TeX in <script type="math/tex"> tags."""
    count = 0
    for script in soup.find_all("script", attrs={"type": re.compile(r"^math/tex")}):
        tex = script.get_text(strip=True)
        if not tex:
            script.decompose()
            continue
        display = "mode=display" in (script.get("type") or "")
        tex = eqnarray_to_aligned(tex)
        script.replace_with(NavigableString(f"$$\n{tex}\n$$" if display else f"${tex}$"))
        count += 1
    return count


def convert_katex(soup: BeautifulSoup) -> int:
    """KaTeX keeps the source TeX in an <annotation encoding="application/x-tex">."""
    count = 0
    for span in soup.select("span.katex"):
        ann = span.select_one('annotation[encoding="application/x-tex"]')
        tex = ann.get_text() if ann else ""
        if not tex:
            continue
        display = span.find_parent(class_="katex-display") is not None
        tex = eqnarray_to_aligned(tex.strip())
        span.replace_with(NavigableString(f"$$\n{tex}\n$$" if display else f"${tex}$"))
        count += 1
    return count


def loose_display_math(container: Tag) -> int:
    """Convert loose \\begin{env}...\\end{env} text nodes into $$ blocks.

    This is the QuantStart pattern: authors wrote raw TeX between <p> tags and
    let MathJax render it client-side. HTML->text converters drop these nodes
    entirely because they are not inside any block element.
    """
    count = 0
    for node in list(container.find_all(string=True)):
        if in_math_free_zone(node):
            continue
        text = str(node).strip()
        if not text or not MATH_ENV_RE.match(text):
            continue
        tex = eqnarray_to_aligned(text)
        p = soup_new_p(container, f"$$\n{tex}\n$$")
        node.replace_with(p)
        count += 1
    return count


def soup_new_p(container: Tag, text: str) -> Tag:
    p = container.new_tag("p")
    p.string = text
    return p


def inline_tex_to_dollars(container: Tag) -> int:
    r"""Rewrite \( ... \) -> $ ... $ and \[ ... \] -> $$ ... $$ in text nodes."""
    count = 0
    for node in list(container.find_all(string=True)):
        if in_math_free_zone(node):
            continue
        text = str(node)
        new = DISPLAY_TEX_RE.sub(lambda m: f"$$\n{m.group(1).strip()}\n$$", text)
        new = INLINE_TEX_RE.sub(lambda m: f"${m.group(1).strip()}$", new)
        if new != text:
            node.replace_with(NavigableString(new))
            count += 1
    return count


# --------------------------------------------------------------------------
# Placeholder protection (math + code survive markdownify untouched)
# --------------------------------------------------------------------------

class TokenBank:
    """Alphanumeric placeholders markdownify cannot mangle (it escapes _ * etc.)."""

    def __init__(self, haystack: str):
        salt = 0
        while f"ZQ{salt}MQZ0MQZQ" in haystack:
            salt += 1
        self.salt = salt
        self.items: list[tuple[str, str]] = []  # (token, replacement text)

    def add(self, replacement: str) -> str:
        token = f"ZQ{self.salt}MQZ{len(self.items)}MQZQ"
        self.items.append((token, replacement))
        return token


def protect_code_and_math(container: Tag, bank: TokenBank) -> dict[str, int]:
    stats = {"code": 0, "display_math": 0, "inline_math": 0, "currency_escaped": 0}

    # 1. Code blocks first so their contents are never math-scanned.
    for pre in list(container.find_all("pre")):
        code_tag = pre.find("code") or pre
        lang = detect_language(pre, code_tag)
        text = code_tag.get_text().rstrip("\n")
        # Recover the text of highlighted copies (Prism spans) but keep the
        # original entities that bs4 already decoded — get_text() did that.
        fence = "```"
        while fence in text:
            fence += "`"
        replacement = f"{fence}{lang}\n{text}\n{fence}"
        token = bank.add(replacement)
        p = soup_new_p(container, token)
        pre.replace_with(p)
        stats["code"] += 1

    # 2. Scan remaining text nodes for dollar math (raw $...$/$$...$$ that the
    #    page already used, plus output of the recovery steps above).
    for node in list(container.find_all(string=True)):
        if in_math_free_zone(node):
            continue
        text = str(node)
        if "$" not in text:
            continue
        pieces: list = []
        pos = 0
        changed = False
        for match in _math_span_iter(text, stats):
            start, end, replacement = match
            if start > pos:
                pieces.append(NavigableString(text[pos:start]))
            pieces.append(_token_holder_tag(container, bank.add(replacement)))
            pos = end
            changed = True
        if changed:
            if pos < len(text):
                pieces.append(NavigableString(text[pos:]))
            node.replace_with(*pieces)
    return stats


def _token_holder_tag(container: Tag, token: str) -> Tag:
    span = container.new_tag("span")
    span.string = token
    return span


def _math_span_iter(text: str, stats: dict[str, int]):
    """Yield (start, end, markdown_replacement) for each math span in text.

    $$...$$ (any newline) is display math; $...$ on one line is inline math.
    Disambiguation against prose dollars ("$5 to $10") is positional: content
    with TeX syntax (\\ ^ _ {) is always math, content starting with a digit
    or currency symbol is money and gets escaped to \\$...\\$, anything else
    (single-letter variables like $t$, $N$) is math.
    """
    spans = [(m.start(), m.end(), f"$$\n{m.group(1).strip()}\n$$", "display")
             for m in DISPLAY_DOLLAR_RE.finditer(text)]
    taken = [(s, e) for s, e, _, _ in spans]
    for m in INLINE_DOLLAR_RE.finditer(text):
        if any(s <= m.start() < e or s < m.end() <= e for s, e in taken):
            continue
        inner = m.group(1).strip()
        if re.search(r"[\\^_{}]", inner):
            spans.append((m.start(), m.end(), f"${inner}$", "inline"))
        elif re.match(r"^[€£]?\d", inner):
            # Keep the raw inner: stripping whitespace would glue the escaped
            # closing $ to the next word ("$5,000 to $10,000" -> "to\$10,000").
            spans.append((m.start(), m.end(), f"\\${m.group(1)}\\$", "currency"))
        else:
            spans.append((m.start(), m.end(), f"${inner}$", "inline"))
    stats_order = {"display": "display_math", "inline": "inline_math", "currency": "currency_escaped"}
    for s, e, repl, kind in sorted(spans):
        stats[stats_order[kind]] += 1
        yield (s, e, repl)


def detect_language(pre: Tag, code_tag: Tag) -> str:
    for tag in (code_tag, pre, pre.parent):
        if not isinstance(tag, Tag):
            continue
        classes = " ".join(filter(None, [*(tag.get("class") or []), tag.get("id", "")]))
        for pat in LANG_PATTERNS:
            hit = pat.search(classes)
            if hit:
                lang = hit.group(1).lower()
                return LANG_ALIAS.get(lang, lang)
    return ""


def protect_mathish(container: Tag, bank: TokenBank) -> int:
    """Protect bare _ and ^ characters (math punctuation) verbatim.

    Runs after dollar-math protection. Protection is lossless (token swapped
    back after conversion), so over-matching only bypasses markdownify's
    underscore-emphasis normalisation and escaping — which is exactly what
    plain-text math needs.
    """
    count = 0
    for node in list(container.find_all(string=True)):
        if in_math_free_zone(node):
            continue
        text = str(node)
        matches = list(MATHISH_RE.finditer(text))
        if not matches:
            continue
        pieces: list = []
        pos = 0
        for match in matches:
            if match.start() > pos:
                pieces.append(NavigableString(text[pos:match.start()]))
            pieces.append(_token_holder_tag(container, bank.add(match.group(0))))
            pos = match.end()
            count += 1
        if pos < len(text):
            pieces.append(NavigableString(text[pos:]))
        node.replace_with(*pieces)
    return count


def truncate_trailing_chrome(md_text: str) -> tuple[str, str | None]:
    """Cut CTA/related-post boxes that sites embed at the end of the article.

    A marker line only truncates when ALL of: it is not a markdown heading,
    CTA vocabulary appears within the following window, and it sits in the
    last 30% of the document. Returns (text, report note or None).
    """
    lines = md_text.splitlines()
    cutoff = int(len(lines) * 0.7)
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or idx < cutoff:
            continue
        if not CTA_MARKER_RE.match(stripped) and not ALWAYS_CTA_HEAD_RE.match(stripped):
            continue
        if stripped.startswith("#") and not ALWAYS_CTA_HEAD_RE.match(stripped):
            continue
        window = "\n".join(lines[idx + 1:idx + 16])
        if CTA_VOCAB_RE.search(window):
            removed = len("\n".join(lines[idx:])) + 1
            note = (f"trailing CTA chrome truncated at {stripped[:50]!r} "
                    f"({removed} chars removed) — verify against raw.html "
                    f"that no real content followed it")
            return "\n".join(lines[:idx]).rstrip() + "\n", note
    return md_text, None


# --------------------------------------------------------------------------
# Links and images
# --------------------------------------------------------------------------

def download_image(url: str, media_dir: Path, seen_names: set[str]) -> str | None:
    """Download one image into media/; returns the local filename or None."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        ctype = resp.headers.get("content-type", "").split(";")[0].strip()
        if not (resp.ok and ctype.startswith("image/") and len(resp.content) > 1024):
            return None
        ext = EXT_BY_TYPE.get(ctype, Path(urlparse(url).path).suffix or ".png")
        stem = re.sub(r"[\W_]+", "-", Path(urlparse(url).path).stem or "image").strip("-")[:60] or "image"
        name = f"{stem}{ext}"
        n = 2
        while name in seen_names or (media_dir / name).exists():
            name = f"{stem}-{n}{ext}"
            n += 1
        media_dir.mkdir(parents=True, exist_ok=True)
        (media_dir / name).write_bytes(resp.content)
        seen_names.add(name)
        return name
    except requests.RequestException:
        return None


def absolutize_links(container: Tag, base_url: str | None) -> int:
    if not base_url:
        return 0
    count = 0
    for a in container.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        if not urlparse(href).netloc:
            a["href"] = urljoin(base_url, href)
            count += 1
    return count


def handle_images(container: Tag, base_url: str | None, media_dir: Path,
                  no_media: bool) -> tuple[int, int, list[str]]:
    """Download content images into media/; drop ads/chrome images."""
    saved, dropped = 0, 0
    notes: list[str] = []
    seen_names: set[str] = set()
    media_dir.mkdir(parents=True, exist_ok=True)

    for img in list(container.find_all("img")):
        src = img.get("src") or img.get("data-src") or ""
        img_attrs = " ".join(filter(None, [
            " ".join(img.get("class") or []), img.get("alt", ""), src, img.get("id", ""),
        ]))
        width = img.get("width") or ""
        height = img.get("height") or ""
        tiny = (width.isdigit() and int(width) <= 64) or (height.isdigit() and int(height) <= 64)
        if src.startswith("data:"):
            img.decompose()
            dropped += 1
            continue
        if IMG_JUNK_PAT.search(img_attrs) or tiny or not src:
            img.decompose()
            dropped += 1
            continue

        abs_src = urljoin(base_url or "", src)
        if no_media or not abs_src.startswith("http"):
            img["src"] = abs_src
            img.attrs = {"src": abs_src, "alt": img.get("alt", "")}
            continue

        stem_ok = False
        name = download_image(abs_src, media_dir, seen_names)
        if name:
            img["src"] = f"media/{name}"
            img.attrs = {"src": img["src"], "alt": img.get("alt", "")}
            saved += 1
            stem_ok = True
        if not stem_ok:
            img["src"] = abs_src
            img.attrs = {"src": abs_src, "alt": img.get("alt", "")}
            notes.append(f"image download failed, kept absolute URL: {abs_src}")
    return saved, dropped, notes


# --------------------------------------------------------------------------
# Hydration markdown blob (author's markdown embedded by SSR frameworks)
# --------------------------------------------------------------------------

JS_STRING_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
JS_NOISE_RE = re.compile(
    r"function\s*\(|=>|self\.__|__NEXT_DATA__|window\.|document\.|:undefined|:null")
# Signals that a string is (part of) an article markdown source.
MD_HEADING_RE = re.compile(r"(?m)^#{1,6} \S")
MD_LIST_RE = re.compile(r"(?m)^[-*+] \S")
IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK_MD_RE = re.compile(r"(?<!\\)(?<!!)\[([^\]\n]+)\]\(([^)\s]+)\)")


def unescape_js_string(s: str) -> str:
    """One JSON/JS-style unescape pass, left-to-right.

    Properly encoded blobs double LaTeX backslashes (\\\\frac in the raw
    payload), so after one pass TeX macros survive intact; unknown escapes
    like \\( pass through unchanged. Never iterate passes on TeX-bearing
    text — a second pass would corrupt \\theta into tab+"heta" etc.
    """
    simple = {"n": "\n", "t": "\t", "r": "", '"': '"', "'": "'",
              "\\": "\\", "/": "/", "`": "`", "b": "\b", "f": "\f"}
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in simple:
                out.append(simple[nxt])
                i += 2
                continue
            if nxt == "u" and i + 6 <= len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
        out.append(c)
        i += 1
    return "".join(out)


def markdown_chunk_score(text: str) -> int:
    """How much a candidate string looks like article markdown (0 = no)."""
    if len(text) < 120:
        return 0
    if text.lstrip()[:1] in ("{", "[", "<"):
        return 0
    body = re.sub(r"```.*?```", "", text, flags=re.S)  # code fences may hold JS
    if len(JS_NOISE_RE.findall(body)) >= 2:
        return 0
    score = (len(MD_HEADING_RE.findall(text)) + len(MD_LIST_RE.findall(text))
             + text.count("**") // 2 + text.count("\\(") + text.count("\\[")
             + text.count("```") // 2)
    return score


def find_hydration_markdown(soup: BeautifulSoup, meta: dict[str, str]) -> str | None:
    """Extract the article's markdown source from SSR hydration script blobs.

    Next.js-style frameworks embed the markdown the site itself rendered, as
    JSON-escaped strings inside self.__next_f.push(...) calls. That source is
    strictly more faithful than the rendered DOM (whose renderer may have
    eaten equation underscores into <em> tags), so when a valid blob exists
    the caller prefers it. Chunks are concatenated in document order.
    """
    chunks: list[str] = []
    seen: set[str] = set()
    for script in soup.find_all("script"):
        if script.get("src"):
            continue
        text = script.string or script.get_text()
        if not text or len(text) < 200:
            continue
        for match in JS_STRING_RE.finditer(text):
            raw = match.group(1)
            if len(raw) < 120 or raw in seen:
                continue
            cand = unescape_js_string(raw)
            if markdown_chunk_score(cand) < 1:
                continue
            seen.add(raw)
            chunks.append(cand)
    if not chunks:
        return None
    md = "\n\n".join(chunks)
    # Validation: real article structure, not UI strings or leftover props.
    if len(md) < 1200 or len(MD_HEADING_RE.findall(md)) < 3:
        return None
    words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", meta.get("title", ""))][:8]
    if words and sum(1 for w in words if w in md.lower()) < min(2, len(words)):
        return None
    return md


def convert_markdown_source(md: str, meta: dict[str, str], base_url: str | None,
                            media_dir: Path, no_media: bool) -> tuple[str, dict[str, int], list[str]]:
    """Convert author markdown (hydration source) to the final document.

    No markdownify involved — the text is already markdown, so subscripts,
    pseudo-math and fences pass through verbatim. Only markers, currency,
    links and images are normalized.
    """
    notes: list[str] = []
    md = html.unescape(md)  # CMS entities (&amp;); TeX \& is untouched

    n_display_tex = 0

    def display_repl(m: re.Match) -> str:
        nonlocal n_display_tex
        n_display_tex += 1
        return f"\n\n$$\n{m.group(1).strip()}\n$$\n\n"

    n_inline_tex = 0

    def inline_repl(m: re.Match) -> str:
        nonlocal n_inline_tex
        n_inline_tex += 1
        return f"${m.group(1).strip()}$"

    md = DISPLAY_TEX_RE.sub(display_repl, md)
    md = INLINE_TEX_RE.sub(inline_repl, md)
    md = eqnarray_to_aligned(md)

    # Loose \begin{env} paragraphs -> $$ blocks
    n_loose = 0
    rebuilt = []
    for para in re.split(r"\n\s*\n", md):
        stripped = para.strip()
        if stripped and MATH_ENV_RE.match(stripped):
            rebuilt.append(f"$$\n{eqnarray_to_aligned(stripped)}\n$$")
            n_loose += 1
        else:
            rebuilt.append(para)
    md = "\n\n".join(rebuilt)

    # Prose dollars vs inline math, per line outside fences
    stats = {"display_math": 0, "inline_math": 0, "currency_escaped": 0}
    lines = md.split("\n")
    in_fence = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or "$" not in line or "$$" in line:
            continue
        pieces: list[str] = []
        pos = 0
        for start, end, repl in _math_span_iter(line, stats):
            pieces.append(line[pos:start])
            pieces.append(repl)
            pos = end
        if pos:
            pieces.append(line[pos:])
            lines[i] = "".join(pieces)
    md = "\n".join(lines)

    # Links: make relative URLs absolute
    if base_url:
        def link_repl(m: re.Match) -> str:
            label, url = m.group(1), m.group(2)
            if url.startswith(("http://", "https://", "mailto:", "#")):
                return m.group(0)
            return f"[{label}]({urljoin(base_url, url)})"

        md = LINK_MD_RE.sub(link_repl, md)

    # Images: download content images, keep the rest as URLs
    media_dir.mkdir(parents=True, exist_ok=True)
    seen_names: set[str] = set()
    n_saved = 0

    def img_repl(m: re.Match) -> str:
        nonlocal n_saved
        alt, url = m.group(1), m.group(2)
        if not url.startswith(("http://", "https://")):
            url = urljoin(base_url or "", url)
        if no_media or not url.startswith("http"):
            return f"![{alt}]({url})"
        name = download_image(url, media_dir, seen_names)
        if name:
            n_saved += 1
            return f"![{alt}](media/{name})"
        notes.append(f"image download failed, kept absolute URL: {url}")
        return f"![{alt}]({url})"

    md = IMG_MD_RE.sub(img_repl, md)

    # Drop the blob's own H1 title if it duplicates the meta title
    lines = md.split("\n")
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if line.startswith("# "):
            heading_words = set(re.findall(r"[a-z]{4,}", line.lower()))
            title_words = set(re.findall(r"[a-z]{4,}", (meta.get("title") or "").lower()))
            if title_words and len(heading_words & title_words) >= min(3, len(title_words)):
                md = "\n".join(lines[idx + 1:])
        break

    stats["display_tex"] = n_display_tex + n_loose
    stats["inline_tex"] = n_inline_tex
    return md, stats, notes


# --------------------------------------------------------------------------
# Markdown assembly
# --------------------------------------------------------------------------

def wrap_loose_strings(container: Tag) -> None:
    # Only wrap inside div/section/article. Wrapping inside <li>/<td> would
    # turn inline article text into separate block paragraphs.
    for node in list(container.find_all(string=True)):
        if in_math_free_zone(node):
            continue
        if not str(node).strip():
            continue
        parent = node.parent
        if parent and parent.name in ("div", "section", "article"):
            node.wrap(container.new_tag("p"))


def to_markdown(container: Tag, bank: TokenBank) -> str:
    html = str(container)
    text = md(html, heading_style="ATX", bullets="-")
    for token, replacement in bank.items:
        text = text.replace(token, replacement)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip() + "\n"


def front_matter(meta: dict[str, str]) -> str:
    fields = {
        "title": meta.get("title") or "Untitled article",
        "source": meta.get("source"),
        "site": meta.get("site"),
        "author": meta.get("author"),
        "published": meta.get("published"),
        # Metadata is plain text: strip math delimiters so the verifier never
        # flags the description as unconverted math.
        "description": re.sub(r"\\[()\[\]]", "", meta.get("description") or ""),
        "converted": date.today().isoformat(),
        "converter": "convert-web-article-to-md",
    }
    lines = ["---"]
    for key, value in fields.items():
        if value:
            lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def assemble(md_body: str, meta: dict[str, str]) -> str:
    title = meta.get("title") or "Untitled article"
    return f"{front_matter(meta)}\n\n# {title}\n\n{md_body}"


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

TOKEN_LEFTOVER_RE = re.compile(r"ZQ\d+MQZ\d+MQZQ")
ENTITY_RE = re.compile(r"&(amp|lt|gt|quot|#39);")
# A whole-line bold span that is really an ASCII-authored equation
# (<p><strong>d(log S_t) = ... dt + sigma dW_t</strong></p>). Content may
# hold markdownify's \* escapes, hence the lookahead rather than [^*].
PSEUDOMATH_RE = re.compile(r"^\*\*((?:(?!\*\*).){10,400})\*\*:?$")
# Emphasis-mangled math: some sites' own markdown renderers eat the
# underscores of ASCII equations into <em> tags, so the delivered HTML has
# "*{ik}"-style fragments where "_{ik}" belongs. Unrecoverable from the DOM —
# but the original markdown is often embedded in a hydration <script> blob.
MANGLED_EMPH_RE = re.compile(r"\*[A-Za-z0-9]{0,4}\{[^}\n]*\}")


def verify(text: str) -> list[str]:
    warnings: list[str] = []
    in_fence = False
    in_display = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.count("$$") % 2 == 1:
            in_display = not in_display
            continue
        if in_display:
            continue
        if re.search(r"\\\(|\\\[", line):
            warnings.append(f"line {lineno}: unconverted \\( / \\[ math remains: {line[:70]!r}")
        if MATH_ENV_RE.match(stripped) or re.search(r"\\begin\{(?!aligned|cases|matrix|array|alignedat|gathered|split)", line):
            warnings.append(f"line {lineno}: raw LaTeX environment outside $$: {line[:70]!r}")
        dollars = len(re.findall(r"(?<!\\)\$", line))
        if dollars % 2 == 1:
            warnings.append(f"line {lineno}: odd number of unescaped '$' — unbalanced math delimiters")
        if ENTITY_RE.search(line):
            warnings.append(f"line {lineno}: HTML entity leftover: {line[:70]!r}")
        pm = PSEUDOMATH_RE.match(stripped)
        if pm and "=" in pm.group(1) and re.search(r"[_^\\]|dt\b|dW\b", pm.group(1)):
            warnings.append(
                f"line {lineno}: bold ASCII pseudo-math (site authors equations as "
                f"bold text, not LaTeX) — transcribe to native $$ math, see "
                f"references/math-and-code-rules.md: {line[:60]!r}")
        line_wo_inline_math = INLINE_DOLLAR_RE.sub("", line)
        if MANGLED_EMPH_RE.search(line_wo_inline_math):
            warnings.append(
                f"line {lineno}: emphasis-mangled math (*{{...}} fragment — the "
                f"site's renderer consumed underscores into <em>; recover the "
                f"original equation from the markdown hydration blob in raw.html: "
                f"{line[:55]!r}")
        if TOKEN_LEFTOVER_RE.search(line):
            warnings.append(f"line {lineno}: unfilled placeholder token (internal bug — report it)")
    return warnings[:20]


def count_math_spans(document: str) -> tuple[int, int]:
    """Count unique (display $$ blocks, inline $...$ spans) in final markdown.

    Conversion-event counters double-report spans that were normalized from
    \( \\) markers and then re-matched as dollar math; this counts the actual
    output, fence- and display-aware, so the report is honest.
    """
    display = inline = 0
    in_fence = False
    in_display = False
    for line in document.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if in_display:
            if "$$" in line:
                in_display = False
            continue
        if "$$" not in line:
            inline += len(re.findall(r"(?<!\\)\$([^$\n]+?)\$(?!\$)", line))
            continue
        pairs = stripped.count("$$")
        display += pairs // 2
        if pairs % 2 == 1:
            display += 1
            in_display = True
        remainder = re.sub(r"\$\$.*?\$\$", "", stripped)
        inline += len(re.findall(r"(?<!\\)\$([^$\n]+?)\$(?!\$)", remainder))
    return display, inline


def check_media(text: str, out_dir: Path) -> list[str]:
    missing = []
    for match in re.finditer(r"!\[[^\]]*\]\((media/[^)]+)\)", text):
        if not (out_dir / match.group(1)).exists():
            missing.append(match.group(1))
    return missing


# --------------------------------------------------------------------------
# Slug / output
# --------------------------------------------------------------------------

def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[\W_]+", "-", value).strip("-")
    return value[:70] or "article"


def derive_slug(source: str, title: str) -> str:
    if is_url(source):
        path = urlparse(source).path
        parts = [p for p in path.split("/") if p]
        if parts:
            leaf = parts[-1]
            if leaf.endswith((".html", ".htm", ".php", ".asp", ".aspx")):
                leaf = leaf.rsplit(".", 1)[0]
            if leaf not in ("index", ""):
                return slugify(leaf)
        return slugify(title or "article")
    if source.endswith((".html", ".htm")):
        return slugify(Path(source).stem)
    return slugify(title or "article")


# --------------------------------------------------------------------------
# Per-article driver
# --------------------------------------------------------------------------

def convert_one(source: str, parent_dir: Path, no_media: bool, source_mode: str = "auto") -> int:
    is_remote = is_url(source)
    if is_remote:
        raw_html = fetch_url(source)
        base_url = source
    else:
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise ConversionError(f"input file not found: {path}")
        raw_html = path.read_text(encoding="utf-8", errors="replace")
        base_url = None

    soup = BeautifulSoup(raw_html, "html.parser")
    meta = extract_meta(soup, source if is_remote else (soup.select_one('link[rel="canonical"]') and soup.select_one('link[rel="canonical"]')["href"]) or "")

    slug = derive_slug(source if is_remote else meta.get("source") or source, meta.get("title", ""))
    out_dir = parent_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw.html").write_text(raw_html, encoding="utf-8")

    warnings: list[str] = []
    img_notes: list[str] = []
    cta_note = None

    # ---- Preferred path: the site's own markdown (hydration blob) ----
    blob = find_hydration_markdown(soup, meta) if source_mode in ("auto", "blob") else None
    if source_mode == "blob" and not blob:
        raise ConversionError("no hydration markdown blob found (--source blob)")
    if blob:
        (out_dir / "hydration.md").write_text(blob, encoding="utf-8")
        body, stats, img_notes = convert_markdown_source(
            blob, meta, base_url, out_dir / "media", no_media)
        document = assemble(body, meta)
        document, cta_note = truncate_trailing_chrome(document)
        md_path = out_dir / f"{slug}.md"
        md_path.write_text(document, encoding="utf-8")
        src_note = ("hydration markdown blob (author source; DOM used for "
                    "front matter only)")
        n_currency = stats["currency_escaped"]
        n_code = len(re.findall(r"(?m)^```", document)) // 2
        saved_imgs = sum(1 for m in re.findall(r"!\[[^\]]*\]\(media/[^)]+\)", document))
        dropped_imgs = 0
        removed_chrome = 0
        n_mathish = 0
    else:
        if source_mode == "blob":
            raise ConversionError("no hydration markdown blob found (--source blob)")
        src_note = "rendered DOM"

        drop_useless_tags(soup)
        container = find_container(soup)
        removed_chrome = remove_chrome(container)

        # Article title: prefer the h1 inside the body over og:title.
        h1 = container.find("h1")
        if h1:
            h1_text = h1.get_text(" ", strip=True)
            if h1_text:
                meta["title"] = strip_title_suffix(h1_text, meta.get("site", ""))
                h1.decompose()

        n_mathjax = convert_mathjax_scripts(soup)
        n_katex = convert_katex(soup)
        n_mathjax_scripts_used = n_mathjax + n_katex
        n_loose = loose_display_math(container)
        inline_tex_to_dollars(container)

        bank = TokenBank(str(container))
        code_stats = protect_code_and_math(container, bank)
        n_mathish = protect_mathish(container, bank)
        absolutize_links(container, base_url)
        saved_imgs, dropped_imgs, img_notes = handle_images(
            container, base_url, out_dir / "media", no_media)
        wrap_loose_strings(container)

        md_body = to_markdown(container, bank)
        document = assemble(md_body, meta)
        document, cta_note = truncate_trailing_chrome(document)
        md_path = out_dir / f"{slug}.md"
        md_path.write_text(document, encoding="utf-8")
        n_currency = code_stats["currency_escaped"]
        n_code = code_stats["code"]

    warnings = verify(document)
    warnings.extend(f"missing media file: {m}" for m in check_media(document, out_dir))
    warnings.extend(img_notes)

    # ---- report ----
    n_display, n_inline = count_math_spans(document)
    print("=" * 72)
    print(f"Converted: {meta.get('title') or source}")
    print(f"Output:    {md_path}")
    print(f"Source:    {src_note}")
    print(f"Raw HTML:  {out_dir / 'raw.html'} (kept for re-parsing / audit)")
    print(f"Math:      {n_display} display ($$...$$), "
          f"{n_inline} inline ($...$), "
          f"{n_currency} currency-$ escaped, "
          f"{n_mathish} _/^ math chars protected")
    print(f"Code:      {n_code} fenced block(s)")
    print(f"Images:    {saved_imgs} saved to media/, {dropped_imgs} chrome/ads dropped")
    print(f"Chrome:    {removed_chrome} boilerplate block(s) removed")
    if cta_note:
        print(f"           {cta_note}")
    if warnings:
        print("Needs attention:")
        for w in warnings:
            print(f"  ! {w}")
        print("  Fix these by hand in the .md (see references/math-and-code-rules.md),")
        print("  or at minimum re-check them against raw.html before delivering.")
    else:
        print("Verification: no leftover markers, delimiters balanced, media resolves.")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Convert math/code-heavy web articles to agent-readable Markdown.")
    parser.add_argument("inputs", nargs="+",
                        help="article URL(s) or local .html file(s)")
    parser.add_argument("-o", "--output", default=None,
                        help="parent directory for <slug>/ output folders "
                             "(default: current directory for URLs, the file's "
                             "directory for local .html inputs)")
    parser.add_argument("--no-media", action="store_true",
                        help="skip downloading images (keep absolute URLs)")
    parser.add_argument("--source", choices=("auto", "dom", "blob"), default="auto",
                        help="conversion source: auto prefers the site's embedded "
                             "hydration markdown and falls back to the rendered DOM "
                             "(default); dom forces the DOM pipeline; blob requires "
                             "a hydration markdown blob and fails without one")
    args = parser.parse_args(argv)

    failures = 0
    for source in args.inputs:
        if is_url(source):
            parent = Path(args.output or ".").expanduser()
        else:
            parent = Path(args.output or Path(source).expanduser().resolve().parent).expanduser()
        parent.mkdir(parents=True, exist_ok=True)
        try:
            convert_one(source, parent, args.no_media, args.source)
        except ConversionError as exc:
            failures += 1
            print(f"ERROR converting {source}: {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — report and keep going in batch mode
            failures += 1
            print(f"ERROR converting {source}: {exc.__class__.__name__}: {exc}", file=sys.stderr)
    return 1 if failures == len(args.inputs) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
