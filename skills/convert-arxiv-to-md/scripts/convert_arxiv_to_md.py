#!/usr/bin/env python3
r"""Convert arXiv papers to Markdown by fetching the LaTeX source and running
pandoc on it -- the quality path for arXiv papers, where MarkItDown-style PDF
scraping mangles headings, tables, math, and rotated text.

Usage:
    python convert_arxiv_to_md.py <input> [<input> ...] [-o OUTPUT] [--keep-source]

Each <input> may be:
  - an arXiv identifier (2511.12490, 2511.12490v1, hep-th/9901001)
  - an arXiv URL (https://arxiv.org/abs/2511.12490 or /pdf/...)
  - a local .pdf of an arXiv paper (the identifier is extracted from the
    document text -- most arXiv PDFs carry the ID in the margin stamp)
  - a local .tar.gz / .zip / .gz containing LaTeX source

Output (for each input), mirroring the sibling convert-pdf-to-md layout:

    <name>/
        <name>.md
        media/          figures referenced by the markdown
        latex-src/      original LaTeX source (only with --keep-source)

<name> is a slug of the paper title when one can be extracted from the
source, else "arxiv-<id>".

The pandoc invocation emits pandoc markdown tuned for pipe tables and $...$
math (both render in Obsidian/GitHub), with citations kept as [@bibtex-key]
so they remain traceable to the References section. A post-processing pass
then cleans pandoc artifacts: fenced-div markers, image attribute blocks,
unresolved \ref links (resolved to real numbers via the source's \label
order), heading numbering, and stray metadata. Exit codes mirror the
sibling skill:
    0 - all requested conversions succeeded
    1 - one or more conversions failed (partial success in batch mode)
    2 - a required dependency ("pandoc") is not installed
    3 - invalid input (path not found, unidentifiable input, no arXiv ID
        found in a PDF)
"""
import argparse
import gzip
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

EXIT_OK = 0
EXIT_CONVERSION_FAILED = 1
EXIT_MISSING_DEPENDENCY = 2
EXIT_INVALID_INPUT = 3

# New-style ( YYMM.NNNNN ) and old-style ( category/NNNNNNN ) identifiers.
ARXIV_ID_RE = re.compile(
    r"\b(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?\b", re.IGNORECASE
)
ARXIV_OLD_ID_RE = re.compile(
    r"\b(?:arxiv:)?([a-z-]+/\d{7})(v\d+)?\b", re.IGNORECASE
)

PANDOC_TO = (
    "markdown+tex_math_dollars+pipe_tables"
    "-simple_tables-multiline_tables-grid_tables-smart"
)


def _check_pandoc():
    """Locate pandoc, failing with a clear, actionable message if absent."""
    exe = shutil.which("pandoc")
    if exe is None:
        print(
            "ERROR: The 'pandoc' binary is not installed.\n"
            "See references/setup.md for this skill.",
            file=sys.stderr,
        )
        sys.exit(EXIT_MISSING_DEPENDENCY)
    return exe


def _strip_comments(text: str) -> str:
    """Drop LaTeX % comments (unescaped) so commented markup isn't parsed."""
    return re.sub(r"(?<!\\)%.*", "", text)


def _resolve_input_files(main_tex: Path) -> list[Path]:
    """Return [main_tex] plus every .tex reachable via \\input/\\include."""
    seen, order, stack = set(), [], [main_tex.resolve()]
    while stack:
        cur = stack.pop()
        if cur in seen or not cur.exists():
            continue
        seen.add(cur)
        order.append(cur)
        try:
            text = cur.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rel in re.findall(r"\\(?:input|include)\{([^}]+)\}", text):
            candidate = cur.parent / rel
            for path in (candidate, candidate.with_suffix(".tex")):
                if path.exists():
                    stack.append(path.resolve())
                    break
    return order


def extract_arxiv_id_from_pdf(pdf_path: Path) -> str:
    """Pull the arXiv identifier out of a PDF's text (margin stamp usually
    carries it). Tries pymupdf, then pdftotext; errors if neither is
    available or no identifier is found."""
    candidates: list[str] = []

    try:
        import pymupdf as fitz  # 'fitz' is the legacy alias

        with fitz.open(str(pdf_path)) as doc:
            for page in doc:
                candidates.append(page.get_text())
                if len(candidates) >= 4:
                    break
    except ImportError:
        if shutil.which("pdftotext"):
            proc = subprocess.run(
                ["pdftotext", "-l", "4", str(pdf_path), "-"],
                capture_output=True, text=True, check=False,
            )
            candidates.append(proc.stdout)
        else:
            print(
                "ERROR: cannot read PDF text to find the arXiv ID. Install "
                "'pymupdf' (pip install pymupdf) or 'pdftotext'.",
                file=sys.stderr,
            )
            sys.exit(EXIT_MISSING_DEPENDENCY)

    for text in candidates:
        match = ARXIV_ID_RE.search(text) or ARXIV_OLD_ID_RE.search(text)
        if match:
            return "".join(match.groups())

    print(
        f"ERROR: no arXiv identifier found in {pdf_path.name}. If this paper "
        "is not from arXiv, use the convert-pdf-to-md skill instead.",
        file=sys.stderr,
    )
    sys.exit(EXIT_INVALID_INPUT)


def normalize_input(value: str) -> tuple[str, Path | None]:
    """Classify an input argument. Returns (arxiv_id, local_source_path);
    exactly one of the two is set."""
    if re.fullmatch(ARXIV_ID_RE, value.strip()):
        return value.strip(), None
    if re.fullmatch(ARXIV_OLD_ID_RE, value.strip()):
        return value.strip(), None
    if "arxiv.org" in value:
        match = ARXIV_ID_RE.search(value) or ARXIV_OLD_ID_RE.search(value)
        if not match:
            print(f"ERROR: could not parse an arXiv ID from URL: {value}", file=sys.stderr)
            sys.exit(EXIT_INVALID_INPUT)
        return "".join(g or "" for g in match.groups()), None
    path = Path(value)
    if not path.exists():
        print(f"ERROR: Input not found and not an arXiv ID/URL: {value}", file=sys.stderr)
        sys.exit(EXIT_INVALID_INPUT)
    if path.suffix.lower() == ".pdf":
        return extract_arxiv_id_from_pdf(path), path
    if path.suffix.lower() in (".gz", ".tgz", ".tar", ".zip"):
        return "", path
    print(
        f"ERROR: Unsupported input '{value}'. Use an arXiv ID, arXiv URL, "
        "a local arXiv .pdf, or a LaTeX source archive.",
        file=sys.stderr,
    )
    sys.exit(EXIT_INVALID_INPUT)


def download_source(arxiv_id: str, dest: Path) -> None:
    """Fetch the LaTeX e-print from arXiv into dest."""
    url = f"https://arxiv.org/e-print/{arxiv_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "convert-arxiv-to-md/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            dest.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001 - network errors surface to caller
        raise RuntimeError(
            f"could not download https://arxiv.org/e-print/{arxiv_id}: {exc}. "
            "If arXiv is rate-limiting you, wait a moment and retry."
        ) from exc


def unpack_source(archive: Path, dest_dir: Path) -> None:
    """Extract an e-print archive of any of arXiv's layouts: gzipped tar,
    plain tar, zip, gzipped single .tex file, or an already-plain .tex."""
    data = archive.read_bytes()
    html_head = data[:300].decode("utf-8", errors="replace").lower()
    if "<!doctype html" in html_head or "<html" in html_head:
        raise RuntimeError(
            "arXiv returned an HTML error page instead of the e-print (most "
            "often rate limiting). Wait a few seconds and retry."
        )
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
        return
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    if data[:262][257:262] == b"ustar" or tarfile.is_tarfile(io.BytesIO(data)):
        with tarfile.open(fileobj=io.BytesIO(data)) as tf:
            members = [
                m for m in tf.getmembers()
                if not m.name.startswith(("/", "..")) and ".." not in Path(m.name).parts
            ]
            tf.extractall(dest_dir, members=members)  # noqa: S202 - members validated
        return
    # Not an archive: a single gzipped (or raw) TeX file.
    text = data.decode("utf-8", errors="replace")
    if "\\documentclass" in text or "\\begin{document}" in text:
        (dest_dir / "main.tex").write_text(text, encoding="utf-8")
        return
    raise RuntimeError("e-print payload is not a tar/zip archive or a TeX file")


def find_main_tex(src_dir: Path) -> Path | None:
    """Pick the top-level .tex: 00README.json hint first, then the file with
    \\documentclass (preferring conventional names, else the largest)."""
    hint = src_dir / "00README.json"
    if hint.exists():
        try:
            import json

            for entry in json.loads(hint.read_text()).get("sources", []):
                if entry.get("usage") == "toplevel":
                    candidate = src_dir / entry["filename"]
                    if candidate.exists():
                        return candidate
        except (ValueError, KeyError, OSError):
            pass

    doc_class = [
        p for p in src_dir.rglob("*.tex")
        if re.search(r"^\s*\\documentclass", p.read_text(encoding="utf-8", errors="replace"), re.M)
    ]
    if not doc_class:
        return None
    if len(doc_class) == 1:
        return doc_class[0]
    for name in ("main.tex", "paper.tex", "article.tex", "ms.tex"):
        for p in doc_class:
            if p.name == name:
                return p
    return max(doc_class, key=lambda p: p.stat().st_size)


def _strip_tex_commands(text: str) -> str:
    r"""Best-effort removal of zero-argument commands and \cmd{...} wrappers
    so a \title{...} value can be slugified."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\\[A-Za-z]+\*?(\[[^\]]*\])?\{([^{}]*)\}", r"\2", text)
        text = re.sub(r"\\[A-Za-z]+\*?", " ", text)
    return re.sub(r"[{}~$]", " ", text)


def derive_title_slug(tree_text: str, arxiv_id: str) -> str:
    """Folder name: slug of the paper's \title, else arxiv-<id>."""
    match = re.search(r"\\title\{", tree_text)
    title = ""
    if match:
        start = match.end() - 1
        depth, end = 0, None
        for i in range(start, len(tree_text)):
            if tree_text[i] == "{":
                depth += 1
            elif tree_text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end:
            title = _strip_tex_commands(tree_text[start + 1:end])
    words = re.findall(r"[A-Za-z0-9]+", title)
    slug = "-".join(words)[:64].rstrip("-")
    return slug or f"arxiv-{arxiv_id.replace('/', '-')}"


def build_label_map(tex_files: list[Path]) -> dict[str, str]:
    r"""Map \label names to display numbers the way LaTeX would: sections
    N / N.M, independent numeric counters per label family (figures, tables,
    definitions, theorems, ...), and equations numbered per numbered
    display-math row (equation/align/gather, honoring \nonumber) -- not per
    \label, since unlabeled numbered equations would otherwise skew the
    count. Papers pick their own prefix spellings (eq vs eqn, fig vs
    figure), so families are matched loosely and unknown prefixes still get
    their own counter rather than being left unresolvable."""
    text = "\n".join(_strip_comments(p.read_text(encoding="utf-8", errors="replace")) for p in tex_files)
    labels: dict[str, str] = {}

    def _family(prefix: str) -> str:
        if prefix in ("fig", "figure", "subfig", "subfigure"):
            return "figure"
        if prefix in ("tab", "table"):
            return "table"
        if prefix in ("eq", "eqn", "equation"):
            return "equation"
        if prefix in ("sec", "sect", "section", "subsec", "subsection",
                      "app", "appendix", "chap", "chapter"):
            return "section"
        return prefix  # def, thm, rem, alg, ... each count independently

    # Pass 1 (line-based): sections and non-float label families.
    section_counter = {"sec": 0, "sub": 0}
    family_counters: dict[str, int] = {}
    for line in text.splitlines():
        if re.match(r"\s*\\(?:sub)*section\*?\s*[{\[]", line):
            if re.match(r"\s*\\subsection", line):
                section_counter["sub"] += 1
            else:
                section_counter["sec"] += 1
                section_counter["sub"] = 0
        for label in re.findall(r"\\label\{([^}]+)\}", line):
            if label in labels or ":" not in label:
                # colon-less labels are ambiguous - they take the number of
                # whatever environment contains them (passes 1.5 / 2)
                continue
            prefix = label.split(":", 1)[0]
            family = _family(prefix)
            if family in ("equation", "figure", "table"):
                continue  # numbered per environment below
            if family == "section":
                labels[label] = (
                    str(section_counter["sec"]) if section_counter["sub"] == 0
                    else f"{section_counter['sec']}.{section_counter['sub']}"
                )
            else:
                family_counters[family] = family_counters.get(family, 0) + 1
                labels[label] = str(family_counters[family])

    # Pass 1.5: figures and tables are numbered per float environment, not
    # per label - unlabeled floats still consume a number in LaTeX, so
    # counting only labels would shift every later number.
    for env_name, family in (("figure", "figure"), ("table", "table"),
                             ("sidewaysfigure", "figure"),
                             ("sidewaystable", "table")):
        n = 0
        for m in re.finditer(
            r"\\begin\{(" + env_name + r"\*?)\}(.*?)\\end\{\1\}", text, re.S
        ):
            n += 1
            for label in re.findall(r"\\label\{([^}]+)\}", m.group(2)):
                prefix = label.split(":", 1)[0] if ":" in label else label
                if (_family(prefix) == family or ":" not in label) and label not in labels:
                    labels[label] = str(n)

    # Pass 2 (environment-aware): display-math rows are numbered 1..N like
    # LaTeX, splitting rows only at nesting depth 0 so \\ inside pmatrix
    # and friends is not treated as a row break.
    env_re = re.compile(
        r"\\begin\{(equation\*?|align\*?|gather\*?|eqnarray\*?|multline\*?)\}"
        r"(.*?)\\end\{\1\}", re.S,
    )
    eq = 0
    for m in env_re.finditer(text):
        body = m.group(2)
        depth = 0
        row_start = 0
        pos = 0
        rows: list[str] = []
        while pos < len(body):
            begin = body.find("\\begin{", pos)
            end = body.find("\\end{", pos)
            brk = body.find("\\\\", pos)
            if begin != -1 and (begin < end or end == -1) and (begin < brk or brk == -1):
                depth += 1
                pos = begin + 7
            elif end != -1 and (end < brk or brk == -1):
                depth -= 1
                pos = end + 5
            elif brk != -1:
                if depth <= 0:
                    rows.append(body[row_start:brk])
                    row_start = brk + 2
                pos = brk + 2
            else:
                rows.append(body[row_start:])
                pos = len(body)
        starred = m.group(1).endswith("*")
        for row in rows:
            numbered = not starred and not re.search(r"\\nonumber|\\notag", row)
            if numbered:
                eq += 1
            for label in re.findall(r"\\label\{([^}]+)\}", row):
                prefix = label.split(":", 1)[0] if ":" in label else label
                if _family(prefix) == "equation" or ":" not in label:
                    labels[label] = str(eq)

    # Pass 3: labels outside every recognized environment (custom floats
    # like algorithm envs) count in their own family, in first-appearance
    # order - a single-use label then resolves to its true number.
    fallback_counters: dict[str, int] = {}
    for line in text.splitlines():
        for label in re.findall(r"\\label\{([^}]+)\}", line):
            if label not in labels:
                fallback_counters[label] = fallback_counters.get(label, 0) + 1
                labels[label] = str(fallback_counters[label])
    return labels


def inline_inputs(main_tex: Path) -> str:
    r"""Flatten \input/\include into one TeX document. Pandoc resolves
    includes against its working directory rather than --resource-path, so
    multi-file papers lose every section body unless we pre-merge them."""
    text = main_tex.read_text(encoding="utf-8", errors="replace")

    def _inline(match: re.Match) -> str:
        rel = match.group(1)
        candidate = main_tex.parent / rel
        for path in (candidate, candidate.with_suffix(".tex")):
            if path.exists():
                return inline_inputs(path)
        return match.group(0)  # unresolvable: leave it, pandoc will warn

    return re.sub(r"\\(?:input|include)\{([^}]+)\}", _inline, text)


def preprocess_source(tex_files: list[Path], workdir: Path) -> list[str]:
    r"""Adjust the extracted source in place for better pandoc output, and
    return warnings. Handles the common bibliography layouts:
    - \bibliography{key} with key.bbl but no key.bib (authors submitted only
      the compiled .bbl): inline the .bbl so references survive.
    - pandoc-style YAML metadata (bibliography: refs.bib): the .bib is
      usually absent from the payload, so inline any .bbl that is present
      and drop the dead metadata key.
    - inline \begin{thebibliography}: add a References heading, since pandoc
      renders the environment as bare paragraphs.

    Also rewrites figure*/table* to figure/table (pandoc's LaTeX reader
    silently drops starred-float captions) and removes spacing environments
    whose arguments would otherwise leak into the text."""
    warnings: list[str] = []
    for tex in tex_files:
        text = tex.read_text(encoding="utf-8", errors="replace")
        for env in ("figure", "table"):
            text = text.replace(f"\\begin{{{env}*}}", f"\\begin{{{env}}}")
            text = text.replace(f"\\end{{{env}*}}", f"\\end{{{env}}}")
        # setspace environments: pandoc emits their {0.5}-style arguments as text
        text = re.sub(r"\\(?:begin|end)\{(?:spacing|setspace)\}\s*(\{[^}]*\})?", "", text)
        # cmidrule range annotations leak into table headers as "2-5 (lr)" text
        text = re.sub(r"\\cmidrule(?:\([^)]*\))?\s*\{[^}]*\}", "", text)
        # \mathchardef\foo="2D defines a char via a TeX primitive pandoc
        # cannot expand; translate the printable-ASCII ones to \newcommand
        def _mathchardef(match: re.Match) -> str:
            code = int(match.group(2), 16)
            char = chr(code) if 32 < code < 127 else "-"
            return f"\\newcommand{{\\{match.group(1)}}}{{{char}}}"

        text = re.sub(r'\\mathchardef\\(\w+)=\s*"?([0-9A-Fa-f]+)', _mathchardef, text)
        # hyphenat defines \mhyphen in a .sty pandoc never loads
        if "\\mhyphen" in text and "hyphenat" in text and "\\newcommand{\\mhyphen}" not in text:
            text = re.sub(
                r"(\\documentclass[^\n]*\n)",
                r"\1\\newcommand{\\mhyphen}{-}\n",
                text, count=1,
            )
        tex.write_text(text, encoding="utf-8")

    # Sanitize .bbl files: they open with \newcommand/\def preamble (url, doi
    # shorthands) that pandoc renders as junk text, and the widest-label
    # argument of thebibliography leaks verbatim. The \ifx guard blocks that
    # follow \begin{thebibliography} render as bare macro names for the same
    # reason, so they go too.
    for bbl in workdir.rglob("*.bbl"):
        bbl_text = bbl.read_text(encoding="utf-8", errors="replace")
        start = bbl_text.find("\\begin{thebibliography}")
        if start > 0:
            bbl_text = bbl_text[start:]
        bbl_text = re.sub(
            r"(\\begin\{thebibliography\})\s*\{[^}]*\}", r"\1{}", bbl_text
        )
        bbl_text = re.sub(
            r"\\expandafter\\ifx\s*\\csname\s*\w+\s*\\endcsname\s*\\relax.*?\\fi",
            "",
            bbl_text,
            flags=re.S,
        )
        bbl.write_text(bbl_text, encoding="utf-8")
    all_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tex_files)

    def _reload() -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tex_files)

    bib_calls = re.findall(r"\\bibliography\{([^}]+)\}", all_text)
    yaml_bib = bool(re.search(r"(?m)^\s*bibliography\s*:", all_text))
    has_bib_files = bool(list(workdir.rglob("*.bib")))
    bbl_files = list(workdir.rglob("*.bbl"))

    needs_inline_bbl = (
        (bool(bib_calls) or yaml_bib)
        and bbl_files
        and "\\begin{thebibliography}" not in all_text
    )
    if needs_inline_bbl:
        # References were compiled to a .bbl that IS in the payload: splice it
        # in just before \end{document} so the references list survives.
        bbl_ref = bbl_files[0].relative_to(workdir).as_posix()
        for tex in tex_files:
            text = tex.read_text(encoding="utf-8", errors="replace")
            if "\\end{document}" in text:
                if bib_calls:
                    text = re.sub(r"\\bibliography\{[^}]*\}", "", text)
                text = text.replace(
                    "\\end{document}",
                    f"\\section*{{References}}\n\\input{{{bbl_ref}}}\n\\end{{document}}",
                )
                if yaml_bib:
                    # dead metadata: the .bib it names is not in the payload
                    text = re.sub(r"(?m)^\s*bibliography\s*:.*\n?", "", text)
                tex.write_text(text, encoding="utf-8")
                break
        all_text = _reload()

    if (
        (bib_calls or yaml_bib)
        and not has_bib_files
        and not bbl_files
        and "\\begin{thebibliography}" not in all_text
    ):
        warnings.append(
            "no .bib, .bbl, or inline thebibliography found - references will be missing"
        )

    # Recover figures pandoc can't load: LaTeX tries common extensions for
    # extension-less includegraphics targets, pandoc does not; and some
    # papers reference paths that don't match the upload's layout or the
    # on-disk casing (filesystems are case-sensitive, authors are not).
    # Try appending an extension in place first, then a unique stem match
    # that ignores case.
    media_files = [
        p for p in workdir.rglob("*")
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf", ".eps", ".gif")
    ]
    by_stem: dict[str, list[Path]] = {}
    for p in media_files:
        by_stem.setdefault(p.stem.lower(), []).append(p)

    for tex in tex_files:
        text = tex.read_text(encoding="utf-8", errors="replace")

        def _fix_graphic(match: re.Match) -> str:
            attrs, target = match.group(1) or "", match.group(2)
            if (tex.parent / target).exists():
                return match.group(0)
            for ext in (".png", ".pdf", ".jpg", ".jpeg", ".eps", ".gif"):
                if (tex.parent / (target + ext)).exists():
                    return f"\\includegraphics{attrs}{{{target + ext}}}"
            candidates = by_stem.get(Path(target).stem.lower(), [])
            if len(candidates) == 1:
                return (
                    f"\\includegraphics{attrs}"
                    f"{{{candidates[0].relative_to(workdir).as_posix()}}}"
                )
            return match.group(0)

        new_text = re.sub(
            r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}", _fix_graphic, text
        )
        if new_text != text:
            tex.write_text(new_text, encoding="utf-8")

    if "\\begin{thebibliography}" in all_text and "\\section*{References}" not in all_text:
        for tex in tex_files:
            text = tex.read_text(encoding="utf-8", errors="replace")
            if "\\begin{thebibliography}" in text:
                text = text.replace(
                    "\\begin{thebibliography}",
                    "\\section*{References}\n\\begin{thebibliography}",
                    1,
                )
                tex.write_text(text, encoding="utf-8")
                break

    tikz_count = all_text.count("\\begin{tikzpicture}")
    if tikz_count:
        warnings.append(
            f"{tikz_count} tikzpicture block(s) cannot be rendered by pandoc - "
            "those figures are dropped; consult the PDF for them"
        )
    return warnings


def run_pandoc(pandoc: str, main_tex: Path, workdir: Path, out_dir: Path, md_path: Path) -> str:
    """Run the conversion. Executed with cwd=out_dir so --extract-media=media
    writes links as 'media/...', which resolve correctly relative to the
    finished markdown; --resource-path lets pandoc find the source images."""
    command = [
        pandoc, str(main_tex.resolve()),
        "-f", "latex",
        "-t", PANDOC_TO,
        "--wrap=none",
        "--standalone",
        "--extract-media=media",
        f"--resource-path={workdir}",
        "-o", str(md_path.resolve()),
    ]
    proc = subprocess.run(command, cwd=out_dir, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not md_path.exists():
        raise RuntimeError(f"pandoc failed (exit {proc.returncode}): {proc.stderr.strip()[:500]}")
    return proc.stderr.strip()


def postprocess(md_text: str, label_map: dict[str, str], arxiv_id: str, drop_date: bool) -> str:
    """Clean pandoc's markdown artifacts that would otherwise appear as noise
    in Obsidian/GitHub rendering."""
    text = md_text

    # Split off YAML front matter for metadata fixes, then rejoin.
    meta, body = "", text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta, body = text[:end] + "\n", text[end + 5:]

    meta = re.sub(r"\\\n", "\n", meta)  # LaTeX \\ line breaks inside author field
    if drop_date and re.search(rf"(?m)^date: '?{_today_iso()}'?\s*$", meta):
        meta = re.sub(r"(?m)^date: .*\n?", "", meta)
    if meta and not meta.endswith("\n"):
        meta += "\n"
    if arxiv_id:
        meta += f"arxiv: '{arxiv_id}'\nsource: https://arxiv.org/abs/{arxiv_id}\n"

    # Fenced-div markers (::: {#tab:...} / ::: figure* / :::) are pandoc-only.
    body = re.sub(r"(?m)^:::.*$", "", body)

    # HTML placeholder comments pandoc inserts as spacing glue in cells.
    body = body.replace("`<!-- -->`{=html}", " ")

    # Image attribute blocks: ![](media/x.png){#fig:... width="95%"}. Keep a
    # map of image -> figure id first: a paper's figure counter includes
    # figures that produce no image (TikZ), so caption numbers must come
    # from the source's own counter via the id, not from image order.
    fig_ids: dict[str, str] = {}

    def _strip_img_attr(match: re.Match) -> str:
        fig_ids[match.group(1)] = match.group(2)
        return match.group(1)

    body = re.sub(
        r"(\]\([^)]+\))\{[^}]*?#(fig:[\w:.\-+]+)[^}]*\}", _strip_img_attr, body
    )
    body = re.sub(r"(\]\([^)]+\))\{[^}]*\}", r"\1", body)

    # Cross-references: [\[name:label\]](#name:label){reference-type=...} -> "1".
    # The prefix is whatever the authors chose (fig, eqn, def, ...) and some
    # labels have no prefix at all; the label_map covers every label that
    # appears in the source.
    def _ref(match: re.Match) -> str:
        return label_map.get(match.group(1), "??")

    body = re.sub(
        r"\[\\\[([\w:.\-+]*)\\\]\]\([^)]*\)(?:\{[^}]*\})?",
        _ref,
        body,
    )
    body = re.sub(r"\[\\\[([\w:.\-+]*)\\\]\]", _ref, body)
    body = re.sub(r"\s*\{reference-type=\"[^\"]*\"[^}]*\}", "", body)

    # Heading attribute blocks: "# Intro {#sec:intro}" / "{.unnumbered}".
    # Attr blocks start with # (id) or . (class), which never collides with
    # math like $\mathcal{W}_p$ appearing inside the heading.
    body = re.sub(r"(?m)^(#{1,6} .+?)\s*\{[#.][^}]*\}\s*$", r"\1", body)

    # Restore figure/table numbers that LaTeX auto-generated and the source
    # never spells out, so in-text "Fig. 1" has something to point at.
    # Tables: pandoc writes their caption as a ': ...' line under the table.
    # Figures: pandoc puts the caption into the image alt text, and the
    # image's {#fig:...} id (captured above) resolves to the paper's own
    # number via label_map; images without an id fall back to counting.
    fig_n = 0
    tab_n = 0
    restored: list[str] = []
    prev_was_table_row = False
    prev_was_refs_heading = False
    pending_fig_caption: str | None = None
    for line in body.splitlines():
        caption = re.match(r"^: (.+)$", line)
        image = re.match(r"^!\[(.+)\]\((media/[^)]+)\)\s*$", line)
        if prev_was_refs_heading and re.fullmatch(r"\d{1,4}", line.strip()):
            # \begin{thebibliography}{99} leaks its widest-label argument
            continue
        fig_open = re.match(r'\s*<figure id="(fig:[\w:.\-+]+)"', line)
        if fig_open:
            pending_fig_caption = label_map.get(fig_open.group(1))
        elif line.strip().startswith("<figcaption>") and pending_fig_caption:
            # pandoc falls back to HTML figures when captions carry
            # attributes; number them from the source's counter too
            line = line.replace(
                "<figcaption>", f"<figcaption>Figure {pending_fig_caption}: ", 1
            )
            pending_fig_caption = None
        elif "</figure>" in line:
            pending_fig_caption = None
        if caption and prev_was_table_row:
            tab_n += 1
            line = f"**Table {tab_n}:** {caption.group(1).strip()}"
        elif image and image.group(1).strip() not in ("", "image") and len(image.group(1).strip()) > 15:
            fid = fig_ids.get(f"]({image.group(2)})")
            mapped = int(label_map[fid]) if fid and fid in label_map and str(label_map[fid]).isdigit() else None
            if mapped is not None:
                fig_n = max(fig_n, mapped)
            else:
                fig_n += 1
            line = f"![Figure {fig_n}: {image.group(1).strip()}]({image.group(2)})"
        restored.append(line)
        if line.strip():
            prev_was_table_row = line.strip().startswith("|")
        # blank lines carry the flag: pandoc puts one between table and caption
        prev_was_refs_heading = re.match(r"^#{1,6} References\s*$", line) is not None
    body = "\n".join(restored)

    # Number headings like the PDF (1, 1.1, ...); References stays unnumbered.
    h1 = h2 = h3 = 0
    numbered: list[str] = []
    for line in body.splitlines():
        heading = re.match(r"^(#{1,3}) (.+)$", line)
        if heading and heading.group(2).strip() != "References":
            level, title = len(heading.group(1)), heading.group(2)
            if level == 1:
                h1 += 1
                h2 = h3 = 0
                line = f"# {h1} {title}"
            elif level == 2:
                h2 += 1
                h3 = 0
                line = f"## {h1}.{h2} {title}"
            else:
                h3 += 1
                line = f"### {h1}.{h2}.{h3} {title}"
        numbered.append(line)
    body = "\n".join(numbered)

    body = re.sub(r"\n{3,}", "\n\n", body)
    return f"{meta}---\n{body}" if meta else body


def _today_iso() -> str:
    import datetime

    return datetime.date.today().isoformat()


def rasterize_pdf_figures(out_dir: Path, md_path: Path) -> list[str]:
    """arXiv figures are often PDFs; markdown/Obsidian can't display those.
    Rasterize linked media/**/*.pdf to .png via pymupdf when available and
    rewrite the links (both markdown ![...](...) and pandoc's HTML fallbacks
    <embed>/<img> for figures with subfigures). Returns notes."""
    try:
        import pymupdf as fitz  # 'fitz' is the legacy alias
    except ImportError:
        text = md_path.read_text(encoding="utf-8")
        pdf_count = len(set(re.findall(r"media/([^\"')]+\.pdf)", text)))
        return (
            [f"{pdf_count} figure(s) are PDF files and will not display in "
             "markdown viewers - install pymupdf to rasterize them"]
            if pdf_count else []
        )

    notes = []
    text = md_path.read_text(encoding="utf-8")
    for pdf_name in sorted(set(re.findall(r"media/([^\"')]+\.pdf)", text))):
        pdf_path = out_dir / "media" / pdf_name
        if not pdf_path.exists():
            continue
        png_name = Path(pdf_name).with_suffix(".png").name
        png_path = pdf_path.with_suffix(".png")
        try:
            with fitz.open(str(pdf_path)) as doc:
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                pix.save(str(png_path))
            text = text.replace(f"media/{pdf_name}", f"media/{pdf_name.replace('.pdf', '.png')}")
            notes.append(f"rasterized {pdf_name} -> {png_name}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"could not rasterize {pdf_name}: {exc}")
    md_path.write_text(text, encoding="utf-8")
    return notes


def verify_output(md_text: str) -> list[str]:
    """Quality gate: a conversion that lost structure should look wrong here
    rather than pass silently."""
    notes = []
    if md_text.count("\n# ") + md_text.startswith("# ") + md_text.count("\n## ") == 0:
        notes.append("WARNING: no markdown headings in output - conversion may be broken")
    unresolved = len(re.findall(r"\?\?", md_text))
    if unresolved:
        notes.append(f"WARNING: {unresolved} cross-reference(s) unresolved (shown as ??)")
    return notes


# --- Bibliography rendering for papers that ship .bib without a .bbl ---------
# Pandoc never runs bibtex/biber, so such papers lose every reference while
# keeping [@key] citations. These helpers render the cited entries straight
# from the .bib source.

_BIB_ACCENTS = {
    "\\'a": "á", "\\'e": "é", "\\'i": "í", "\\'o": "ó", "\\'u": "ú",
    "\\'A": "Á", "\\'E": "É", "\\'I": "Í", "\\'O": "Ó", "\\'U": "Ú",
    '\\"o': "ö", '\\"u': "ü", '\\"a': "ä", '\\"O': "Ö", '\\"U': "Ü", '\\"A': "Ä",
    "\\~n": "ñ", "\\~N": "Ñ", "\\c{c}": "ç", "\\c{C}": "Ç",
    "{\\aa}": "å", "{\\AA}": "Å", "\\o{}": "ø", "\\O{}": "Ø", "\\ss{}": "ß",
    "\\l{}": "ł", "\\v{c}": "č", "\\v{s}": "š", "\\v{z}": "ž",
}


def _bib_clean(s: str) -> str:
    s = s.strip()
    for k, v in _BIB_ACCENTS.items():
        s = s.replace(k, v)
    s = re.sub(r"\\['`^\"~cuv=.]\s*\{?([a-zA-Z])\}?", r"\1", s)
    s = s.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$")
    s = s.replace("\\emph", "").replace("\\textit", "").replace("\\textbf", "")
    s = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\url\{([^}]*)\}", r"\1", s)
    s = s.replace("{", "").replace("}", "")
    s = re.sub(r"\\[a-zA-Z]+", "", s)  # drop any remaining latex macros
    return re.sub(r"\s+", " ", s).strip(" .,~")


def _bib_split_entries(text: str):
    """Yield (etype, key, body) for each @type{key, ...} entry."""
    for m in re.finditer(r"@(\w+)\s*\{", text):
        etype = m.group(1).lower()
        if etype in ("string", "comment", "preamble"):
            continue
        start = m.end() - 1
        depth, i = 0, start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start + 1:i]
        if "," not in body:
            continue
        key, rest = body.split(",", 1)
        yield etype, key.strip(), rest


def _bib_parse_fields(body: str) -> dict:
    fields, i, n = {}, 0, len(body)
    while i < n:
        m = re.compile(r"([A-Za-z]+)\s*=\s*").search(body, i)
        if not m:
            break
        name = m.group(1).lower()
        j = m.end()
        if j < n and body[j] == "{":
            depth, k = 0, j
            while k < n:
                if body[k] == "{":
                    depth += 1
                elif body[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            val = body[j + 1:k]
            i = k + 1
        elif j < n and body[j] == '"':
            k = body.find('"', j + 1)
            val = body[j + 1:k] if k != -1 else body[j + 1:]
            i = (k + 1) if k != -1 else n
        else:
            k = body.find(",", j)
            val = body[j:k if k != -1 else n]
            i = (k if k != -1 else n)
        fields[name] = _bib_clean(val)
    return fields


def _bib_fmt_author(a: str) -> str:
    if a.lower() in ("others", "and others"):
        return "et al."
    out = []
    for name in re.split(r"\s+and\s+", a):
        name = name.strip()
        if not name:
            continue
        if "," in name:
            last, first = [p.strip() for p in name.split(",", 1)]
        else:
            parts = name.split()
            last, first = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
        initials = ". ".join(p[0] for p in first.split() if p) + "." if first else ""
        out.append(f"{last}, {initials}" if initials else last)
    if out and out[-1] == "et al.":
        out = out[:-1] + ["et al."]
    if len(out) > 1:
        return ", ".join(out[:-1]) + " & " + out[-1]
    return out[0] if out else ""


def _bib_fmt_entry(etype: str, key: str, fields: dict) -> str:
    authors = _bib_fmt_author(fields.get("author", fields.get("editor", ""))) or "—"
    year = fields.get("year", "n.d.")
    title = fields.get("title", "")
    venue = (fields.get("journal") or fields.get("booktitle")
             or fields.get("publisher") or fields.get("school") or "")
    vol, num = fields.get("volume", ""), fields.get("number", "")
    pages = fields.get("pages", "").replace("--", "–")
    tail = ""
    if venue:
        tail += f" *{venue}*"
        if vol:
            tail += f", {vol}" + (f"({num})" if num else "")
        elif num:
            tail += f", {num}"
        if pages:
            tail += f", {pages}"
    elif vol or pages:
        tail += ", " + ", ".join(b for b in (vol, num, pages) if b)
    if fields.get("doi"):
        tail += f". doi:{fields['doi']}"
    elif fields.get("url"):
        tail += f". {fields['url']}"
    if etype == "phdthesis" and fields.get("school"):
        tail += f" PhD thesis, {fields['school']}"
    return f"- `@{key}` — {authors} ({year}). {title}.{tail}"


def render_bibliography(bib_text: str, cited_keys: list[str]) -> str:
    """Format the cited entries of a .bib file as a markdown References
    section, preserving first-appearance order of the citations."""
    entries: dict[str, tuple[str, dict]] = {}
    for etype, key, body in _bib_split_entries(bib_text):
        entries[key] = (etype, _bib_parse_fields(body))
    lines = ["# References", ""]
    for key in cited_keys:
        if key in entries:
            etype, fields = entries[key]
            lines.append(_bib_fmt_entry(etype, key, fields))
        else:
            lines.append(f"- `@{key}` — *(entry not found in the .bib file)*")
    return "\n".join(lines) + "\n"


def extract_cited_keys(md_text: str) -> list[str]:
    """Citation keys in first-appearance order, including multi-key groups
    like [@a; @b]."""
    cited: list[str] = []
    for group in re.findall(r"\[@([^\]]+)\]", md_text):
        for key in group.split(";"):
            key = key.strip().lstrip("@")
            if key and key not in cited:
                cited.append(key)
    return cited


def _text_brace_balance(text: str) -> int:
    """Net unclosed `{` in prose, ignoring comments and math spans (math has
    its own brace balance; a stray `$` in prose must not skew the count)."""
    t = _strip_comments(text)
    t = re.sub(r"\\begin\{((?:equation|align|gather|eqnarray|multline)\*?)\}.*?\\end\{\1\}", " ", t, flags=re.S)
    t = re.sub(r"\$\$.*?\$\$", " ", t, flags=re.S)
    t = re.sub(r"\\\[.*?\\\]", " ", t, flags=re.S)
    t = re.sub(r"\\\(.*?\\\)", " ", t, flags=re.S)
    t = re.sub(r"(?<!\\)\$[^$]*(?<!\\)\$", " ", t, flags=re.S)
    return t.count("{") - t.count("}")


def repair_source(tex_files: list[Path], src_dir: Path) -> list[str]:
    r"""Content-preserving surgery for malformed arXiv sources that pandoc
    rejects. Invoked ONLY after a failed conversion, so well-formed papers
    are never touched. Applies the failure modes seen in the wild: raw TeX
    spacing primitives, tabulars nested inside tabulars, rotating
    environments, dangling `{` groups, and whitespace inside
    includegraphics paths. Returns descriptions of what was changed."""
    repairs: list[str] = []
    for tex in tex_files:
        text = tex.read_text(encoding="utf-8", errors="replace")
        original = text

        # Raw TeX vertical-space primitive pandoc cannot parse.
        n = text.count("\\vskip\\baselineskip")
        if n:
            text = text.replace("\\vskip\\baselineskip", "")
            repairs.append(f"removed {n} \\vskip\\baselineskip primitive(s)")

        # tabular[t]{...} wrappers nested inside outer tabulars collapse to
        # one-line cell content. Only innermost wrappers are flattened (a
        # body still containing \begin{tabular} is an outer float that must
        # stay intact); iterate for deeper nesting.
        flat_n = 0

        def _flatten(m: re.Match) -> str:
            body = m.group(1)
            if "\\begin{tabular}" in body:
                return m.group(0)
            return re.sub(r"\s*\\\\\s*", "; ",
                          re.sub(r"\s+", " ", body)).strip().rstrip(";").strip()

        while flat_n < 10:
            new_text = re.sub(
                r"\\begin\{tabular\}\[[^\]]*\]\{[^}]*\}(.*?)\\end\{tabular\}",
                _flatten, text, flags=re.S,
            )
            if new_text == text:
                break
            flat_n += 1
            text = new_text
        if flat_n:
            repairs.append(f"flattened {flat_n} nested tabular wrapper(s)")

        # rotating-package environments: layout-only, keep the content.
        turn_n = len(re.findall(r"\\begin\{turn\}", text))
        if turn_n:
            text = re.sub(r"\\(?:begin|end)\{turn\}\s*(\{[^}]*\})?", "", text)
            repairs.append(f"unwrapped {turn_n} turn environment(s)")

        # Whitespace inside includegraphics paths breaks file lookup.
        text = re.sub(
            r"(\\includegraphics(?:\[[^\]]*\])?\{)\s*([^}]*?)\s*(\})",
            r"\1\2\3", text,
        )

        if text != original:
            tex.write_text(text, encoding="utf-8")

    # Dangling `{` groups swallow the rest of the document and surface as
    # "unexpected \end{document}". Close them at \end{document}, which keeps
    # the content and terminates the group where LaTeX would at EOF anyway.
    for tex in tex_files:
        text = tex.read_text(encoding="utf-8", errors="replace")
        if "\\end{document}" not in text:
            continue
        balance = _text_brace_balance(text)
        if 0 < balance <= 3:
            text = text.replace(
                "\\end{document}", "}" * balance + "\n\\end{document}"
            )
            tex.write_text(text, encoding="utf-8")
            repairs.append(
                f"closed {balance} dangling brace group(s) before \\end{{document}}"
            )
    return repairs


def convert_one(pandoc: str, spec: str, local_path: Path | None, out_dir: Path,
                keep_source: bool) -> bool:
    """Convert a single arXiv input into out_dir/<name>/. Returns success."""
    workdir = Path(tempfile.mkdtemp(prefix="arxiv2md-"))
    try:
        arxiv_id, source = spec, local_path
        if source is not None and source.suffix.lower() == ".pdf":
            source = None  # the PDF was only an ID carrier; the source is on arXiv
        if source is None:
            print(f"Downloading LaTeX source for {arxiv_id} ...")
            download_source(arxiv_id, workdir / "e-print.bin")
            source = workdir / "e-print.bin"
        src_dir = workdir / "src"
        src_dir.mkdir()
        unpack_source(source, src_dir)

        main_tex = find_main_tex(src_dir)
        if main_tex is None:
            raise RuntimeError("no .tex file with \\documentclass found in the source")
        tex_files = _resolve_input_files(main_tex)

        tree_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tex_files)
        warnings = preprocess_source(tex_files, src_dir)
        label_map = build_label_map(_resolve_input_files(main_tex))
        slug = derive_title_slug(tree_text, arxiv_id)

        dest_dir = out_dir / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        md_path = dest_dir / f"{slug}.md"

        inlined = src_dir / "__inlined_main__.tex"
        inlined.write_text(inline_inputs(main_tex), encoding="utf-8")
        try:
            pandoc_stderr = run_pandoc(pandoc, inlined, src_dir, dest_dir, md_path)
        except RuntimeError:
            # Malformed source: apply content-preserving surgery and retry
            # once before giving up.
            repairs = repair_source(tex_files, src_dir)
            if not repairs:
                raise
            for r in repairs:
                warnings.append(f"source repair: {r}")
            tex_files = _resolve_input_files(main_tex)
            tree_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in tex_files)
            label_map = build_label_map(_resolve_input_files(main_tex))
            inlined.write_text(inline_inputs(main_tex), encoding="utf-8")
            pandoc_stderr = run_pandoc(pandoc, inlined, src_dir, dest_dir, md_path)
        warnings += [
            f"pandoc: {line.strip()[len('[WARNING] '):]}"
            for line in pandoc_stderr.splitlines()
            if line.startswith("[WARNING]")
        ]
        drop_date = bool(
            re.search(r"\\date\*?\s*(\[[^\]]*\])?\s*\{[^}]*\\today", tree_text)
        )
        md_text = postprocess(md_path.read_text(encoding="utf-8"), label_map, arxiv_id, drop_date)

        # Papers that ship .bib without a compiled .bbl lose their references
        # entirely (pandoc never runs bibtex) while keeping [@key] citations.
        # Render the cited entries from the .bib ourselves.
        if (
            "# References" not in md_text
            and not list(src_dir.rglob("*.bbl"))
            and "\\begin{thebibliography}" not in tree_text
        ):
            bib_files: list[Path] = []
            for keys in re.findall(r"\\bibliography\{([^}]+)\}", tree_text):
                bib_files += [p for p in src_dir.rglob(f"{keys.split(',')[0].strip()}.b*")
                              if p.suffix == ".bib"]
            for yb in re.findall(r"(?m)^\s*bibliography\s*:\s*(.+)$", tree_text):
                name = yb.strip().strip("'\"").split(",")[0].strip()
                bib_files += [p for p in src_dir.rglob(name) if p.is_file()]
            if not bib_files and not re.search(r"\\begin\{thebibliography\}", tree_text):
                bib_files = list(src_dir.rglob("*.bib"))
            if bib_files:
                cited = extract_cited_keys(md_text)
                if cited:
                    bib_text = bib_files[0].read_text(encoding="utf-8", errors="replace")
                    md_text = md_text.rstrip("\n") + "\n\n" + render_bibliography(bib_text, cited)
                    warnings.append(
                        f"rendered {len(cited)} references from {bib_files[0].name} "
                        "(pandoc cannot run bibtex; paper shipped .bib without a .bbl)"
                    )
        md_path.write_text(md_text, encoding="utf-8")

        notes = warnings + rasterize_pdf_figures(dest_dir, md_path) + verify_output(md_text)
        if "\\begin{document}" not in tree_text or md_path.stat().st_size < 500:
            print(f"FAILED  {spec or arxiv_id}: output looks incomplete", file=sys.stderr)
            return False

        if keep_source:
            kept = dest_dir / "latex-src"
            shutil.rmtree(kept, ignore_errors=True)
            shutil.copytree(src_dir, kept)

        img_count = len(list((dest_dir / "media").rglob("*"))) if (dest_dir / "media").exists() else 0
        headings = len(re.findall(r"(?m)^#{1,6} ", md_text))
        citations = len(set(re.findall(r"\[@([^\]\s]+)", md_text)))
        print(f"OK      {arxiv_id or source.name} -> {md_path}")
        print(f"        {headings} headings, {citations} citation keys, {img_count} figure file(s)")
        for note in notes:
            print(f"        note: {note}")
        return True
    except Exception as exc:  # noqa: BLE001 - per-input isolation, like the sibling skill
        print(f"FAILED  {spec or local_path} -> {exc}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "inputs", nargs="+",
        help="arXiv ID, arXiv URL, local arXiv .pdf, or LaTeX source archive",
    )
    parser.add_argument(
        "-o", "--output",
        help="Destination folder for the '<name>/' output (single input), or "
        "parent directory under which each '<name>/' folder is created (batch)",
    )
    parser.add_argument(
        "--keep-source", action="store_true",
        help="Also save the extracted LaTeX source under latex-src/ in the output",
    )
    args = parser.parse_args()

    pandoc = _check_pandoc()

    base = Path(args.output) if args.output else Path.cwd()
    success_count = 0
    for value in args.inputs:
        arxiv_id, local_path = normalize_input(value)
        spec = arxiv_id
        if local_path is not None and arxiv_id:
            # A local PDF: convert beside the PDF like the sibling skill does.
            out_dir = local_path.parent if len(args.inputs) == 1 and not args.output else base
        else:
            out_dir = base
        if convert_one(pandoc, spec, local_path, out_dir, args.keep_source):
            success_count += 1

    total = len(args.inputs)
    if total > 1:
        print(f"\nConverted {success_count}/{total} input(s).")
    return EXIT_OK if success_count == total else EXIT_CONVERSION_FAILED


if __name__ == "__main__":
    sys.exit(main())
