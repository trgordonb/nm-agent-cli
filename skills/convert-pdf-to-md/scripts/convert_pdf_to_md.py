#!/usr/bin/env python3
"""Convert PDF documents to Markdown using pymupdf4llm's layout-aware
pipeline (headings, pipe tables, OCR where needed), with MarkItDown as a
fallback engine for environments where pymupdf4llm is unavailable.

Usage:
    python convert_pdf_to_md.py <input> [-o OUTPUT] [--recursive]
                                [--engine {auto,pymupdf4llm,markitdown}]

<input> may be either:
  - a path to a single .pdf file, or
  - a path to a directory (batch mode: every .pdf file directly inside it
    is converted; pass --recursive to also descend into subdirectories).

Output:
  For each source .pdf (named "<name>.pdf"), a folder is created containing
  the Markdown and its images, in this layout:

      <name>/
          <name>.md
          img/            figures and page images referenced by the md

  - Single file mode: the "<name>/" folder is created next to the source
    file, or under -o/--output (treated as a parent directory, created if
    missing) when given.
  - Batch/directory mode: a "<name>/" folder is created next to each source
    file, or under -o/--output (treated as a parent directory, created if
    missing) when given, preserving relative subfolder structure when
    --recursive is used.

Engines ("--engine", default "auto"):
  - pymupdf4llm (primary): layout-aware extraction with table detection
    and built-in OCR (RapidOCR ships with it; Tesseract is used when
    present). Page images are written to img/ and linked inline.
  - markitdown (fallback): Microsoft MarkItDown text/tables extraction.
    Chosen automatically when pymupdf4llm is not installed or raises;
    force it with --engine markitdown.

Exit codes:
  0 - all requested conversions succeeded
  1 - one or more conversions failed (partial success in batch mode)
  2 - no conversion engine is importable
  3 - invalid input (path not found, or single-file input is not .pdf)
"""
import argparse
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_CONVERSION_FAILED = 1
EXIT_MISSING_DEPENDENCY = 2
EXIT_INVALID_INPUT = 3

TESSDATA_CANDIDATES = (
    Path.home() / ".local" / "share" / "tessdata",
    Path("/tmp/tessdata"),
)


def _ensure_tessdata() -> None:
    """Point TESSDATA_PREFIX at a directory that actually contains eng
    language data, if the system default lacks it and we can find one.
    Without this, Tesseract-backed OCR fails on some systems; RapidOCR
    (bundled with pymupdf4llm) does not need it."""
    if os.environ.get("TESSDATA_PREFIX"):
        return
    for candidate in TESSDATA_CANDIDATES:
        if (candidate / "eng.traineddata").exists():
            os.environ["TESSDATA_PREFIX"] = str(candidate)
            return
    for pattern in ("/usr/share/tesseract-ocr/*/tessdata", "/usr/share/tessdata"):
        import glob

        for candidate in glob.glob(pattern):
            if (Path(candidate) / "eng.traineddata").exists():
                os.environ["TESSDATA_PREFIX"] = candidate
                return


def _import_pymupdf4llm():
    try:
        import pymupdf4llm

        return pymupdf4llm
    except ImportError:
        return None


def _import_markitdown():
    try:
        from markitdown import MarkItDown

        return MarkItDown
    except ImportError:
        return None


def clean_pymupdf4llm_markdown(md: str) -> str:
    """Strip the layout pipeline's OCR highlight markup and heading noise
    while keeping everything that renders (sup, sub, u, br)."""
    md = md.replace("<mark>", "").replace("</mark>", "")
    # Heading text wrapped in bold: "# **Title**" -> "# Title"
    md = re.sub(r"(?m)^(#{1,6}) \*\*(.+?)\*\*\s*$", r"\1 \2", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md


def convert_with_pymupdf4llm(pymupdf4llm, source: Path, dest_dir: Path) -> tuple[str, list[str]]:
    """Primary engine. Runs with cwd=dest_dir so write_images' image_path
    ('img') emits relative links that resolve next to the markdown.
    Returns (markdown, notes)."""
    notes: list[str] = []
    img_dir = dest_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    cwd = os.getcwd()
    try:
        os.chdir(dest_dir)
        md = pymupdf4llm.to_markdown(
            str(source.resolve()),
            show_progress=False,
            write_images=True,
            image_path="img",
            image_format="png",
        )
    finally:
        os.chdir(cwd)
    return clean_pymupdf4llm_markdown(md), notes


def convert_with_markitdown(source: Path, dest_dir: Path) -> tuple[str, list[str]]:
    """Fallback engine: MarkItDown for text/tables (its converter has no
    image support), plus PyMuPDF for embedded images appended as an
    'Extracted Images' section. Returns (markdown, notes)."""
    import fitz
    from markitdown import MarkItDown

    notes: list[str] = []
    result = MarkItDown().convert(str(source))
    text = result.text_content.rstrip("\n")

    img_dir = dest_dir / "img"
    written_by_page = extract_images_fitz(source, img_dir)
    if written_by_page:
        lines = ["", "## Extracted Images", ""]
        for page_num in sorted(written_by_page):
            lines.append(f"### Page {page_num}")
            lines.append("")
            for name in written_by_page[page_num]:
                lines.append(f"![{name}](img/{name})")
            lines.append("")
        text += "\n".join(lines).rstrip() + "\n"
        notes.append(f"{sum(len(v) for v in written_by_page.values())} embedded image(s) appended")
    return text, notes


def extract_images_fitz(source: Path, img_dir: Path) -> dict[int, list[str]]:
    """Extract embedded raster images grouped by 1-based page number,
    deduplicated by content hash (same behavior as the previous pipeline)."""
    import fitz

    written_by_page: dict[int, list[str]] = {}
    doc = fitz.open(str(source))
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_label = page_index + 1
            seen_hashes: set = set()
            raw_images: list[tuple[bytes, str]] = []

            try:
                for img in page.get_images(full=True):
                    base = doc.extract_image(img[0])
                    if base.get("image"):
                        raw_images.append((base["image"], (base.get("ext") or "png").lower()))
            except Exception:  # noqa: BLE001
                pass

            try:
                for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_IMAGES).get("blocks", []):
                    if block.get("type") == 1 and block.get("image"):
                        raw_images.append((block["image"], (block.get("ext") or "png").lower()))
            except Exception:  # noqa: BLE001
                pass

            page_files = []
            img_idx = 1
            for img_bytes, ext in raw_images:
                digest = hashlib.sha256(img_bytes).digest()
                if digest in seen_hashes:
                    continue
                seen_hashes.add(digest)
                name = f"page{page_label:03d}_img{img_idx:03d}.{ext}"
                img_dir.mkdir(parents=True, exist_ok=True)
                (img_dir / name).write_bytes(img_bytes)
                page_files.append(name)
                img_idx += 1
            if page_files:
                written_by_page[page_label] = page_files
    finally:
        doc.close()
    return written_by_page


def convert_one(engine: str, source: Path, dest_dir: Path) -> tuple[bool, list[str]]:
    """Convert a single .pdf file into dest_dir/. Returns (success, notes)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    md_path = dest_dir / f"{source.stem}.md"

    if engine == "pymupdf4llm":
        pymupdf4llm = _import_pymupdf4llm()
        if pymupdf4llm is None:
            return False, ["pymupdf4llm not importable"]
        _ensure_tessdata()
        try:
            md, notes = convert_with_pymupdf4llm(pymupdf4llm, source, dest_dir)
        except Exception as exc:  # noqa: BLE001 - engine errors trigger the fallback
            return False, [f"pymupdf4llm raised: {exc}"]
    else:
        MarkItDown = _import_markitdown()
        if MarkItDown is None:
            return False, ["markitdown not importable"]
        try:
            md, notes = convert_with_markitdown(source, dest_dir)
        except Exception as exc:  # noqa: BLE001
            return False, [f"markitdown raised: {exc}"]

    if not md.strip():
        return False, notes + ["empty markdown output"]

    md_path.write_text(md, encoding="utf-8")
    img_count = len(list((dest_dir / "img").rglob("*"))) if (dest_dir / "img").exists() else 0
    print(
        f"OK      {source} -> {md_path} "
        f"(engine={engine}, {len(md.splitlines())} lines{f', {img_count} image file(s)' if img_count else ''})"
    )
    for note in notes:
        print(f"        note: {note}")
    return True, notes


def convert_one_auto(engine_pref: str, source: Path, dest_dir: Path) -> tuple[bool, list[str], str]:
    """Run the preferred engine; on failure fall back to the other one."""
    engines = [engine_pref] if engine_pref != "auto" else ["pymupdf4llm", "markitdown"]
    notes_all: list[str] = []
    for index, engine in enumerate(engines):
        ok, notes = convert_one(engine, source, dest_dir)
        if ok:
            return True, notes_all, engine
        notes_all += notes
        if index + 1 < len(engines):
            print(f"        engine '{engine}' failed; falling back to '{engines[index + 1]}'")
    return False, notes_all, engines[-1]


def find_pdf_files(root: Path, recursive: bool):
    """Return (pdf_files, skipped_count) for files directly/recursively under root."""
    pattern_iter = root.rglob("*") if recursive else root.iterdir()
    pdf_files, skipped = [], 0
    for entry in pattern_iter:
        if entry.is_dir():
            continue
        if entry.suffix.lower() == ".pdf":
            pdf_files.append(entry)
        else:
            skipped += 1
    return sorted(pdf_files), skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Path to a .pdf file or a directory of .pdf files")
    parser.add_argument(
        "-o", "--output",
        help="Parent directory under which the '<name>/' output folder(s) are "
             "created (single-file and batch mode alike); created if missing",
    )
    parser.add_argument(
        "--recursive", action="store_true",
        help="When input is a directory, also search subdirectories",
    )
    parser.add_argument(
        "--engine", choices=("auto", "pymupdf4llm", "markitdown"), default="auto",
        help="Conversion engine (default: auto = pymupdf4llm, falling back to markitdown)",
    )
    args = parser.parse_args()

    if _import_pymupdf4llm() is None and _import_markitdown() is None:
        print(
            "ERROR: Neither 'pymupdf4llm' nor 'markitdown' is installed.\n"
            "See references/setup.md for this skill, or run:\n"
            '    pip install -r scripts/requirements.txt',
            file=sys.stderr,
        )
        return EXIT_MISSING_DEPENDENCY

    source = Path(args.input)
    if not source.exists():
        print(f"ERROR: Input path not found: {source}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if source.is_file() and source.suffix.lower() != ".pdf":
        print(
            f"ERROR: Unsupported file type '{source.suffix}'. "
            "This skill only converts .pdf files.",
            file=sys.stderr,
        )
        return EXIT_INVALID_INPUT

    if source.is_file():
        # -o is the destination PARENT folder (matching batch mode and the
        # convert-arxiv-to-md skill): the '<name>/' folder is created under it.
        dest_dir = (Path(args.output) / source.stem) if args.output else source.parent / source.stem
        ok, _, _ = convert_one_auto(args.engine, source, dest_dir)
        return EXIT_OK if ok else EXIT_CONVERSION_FAILED

    # Directory / batch mode
    pdf_files, skipped = find_pdf_files(source, args.recursive)
    if skipped:
        print(f"NOTE: skipped {skipped} non-.pdf file(s) in {source}")
    if not pdf_files:
        print(f"ERROR: No .pdf files found under {source}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    out_dir = Path(args.output) if args.output else None
    success_count = 0
    for pdf_path in pdf_files:
        if out_dir is not None:
            rel = pdf_path.relative_to(source)
            dest_dir = out_dir / rel.parent / pdf_path.stem
        else:
            dest_dir = pdf_path.parent / pdf_path.stem
        ok, _, _ = convert_one_auto(args.engine, pdf_path, dest_dir)
        if ok:
            success_count += 1

    total = len(pdf_files)
    print(f"\nConverted {success_count}/{total} file(s).")
    return EXIT_OK if success_count == total else EXIT_CONVERSION_FAILED


if __name__ == "__main__":
    sys.exit(main())
