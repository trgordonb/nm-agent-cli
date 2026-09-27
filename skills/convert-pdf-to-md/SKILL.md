---
name: convert-pdf-to-md
description: 'Converts PDF (.pdf) documents into Markdown so their contents can be accurately analyzed, summarized, searched, or extracted from. Use this skill whenever the user shares, references, or asks about a .pdf file — even if they don''t say "convert" or "markdown" explicitly. This includes requests to "read", "summarize", "review", "extract data from", "compare", or "analyze" a PDF report, paper, invoice, form, contract, or scanned document. Always run the bundled conversion script to produce Markdown first; do not attempt to parse PDF content directly or write ad-hoc extraction code. Also use this skill for batch requests involving a whole folder of PDF documents. IMPORTANT: When the user references a folder or set of documents containing multiple file types (.pdf, .docx, .xlsx), invoke ALL three sibling skills — convert-pdf-to-md, convert-word-to-md, and convert-excel-to-md — so no file type is silently skipped. IMPORTANT: For arXiv papers (arXiv ID, arXiv URL, or a PDF bearing an arXiv stamp), use the convert-arxiv-to-md skill instead — it converts from the LaTeX source and preserves headings, math, and tables far better.'
---

# Convert PDF to Markdown

## When to use this skill

Trigger this skill any time there is a `.pdf` file that needs to be
understood or processed — for example, a user attaches a PDF and asks
questions about it, wants a summary, wants specific data or tables pulled
out, or wants multiple PDFs in a folder processed together. PDF is a
layout/print format, not reliably readable as plain text, so always convert
it to Markdown first using the script in this skill rather than trying to
open or parse the file directly.

This skill only supports `.pdf` — there's no legacy format to worry about
here (unlike Word's `.doc` or Excel's `.xls`).

**Not for arXiv papers:** when a PDF carries an arXiv stamp (arXiv:YYMM.NNNNN)
or the user gives an arXiv ID/URL, use the `convert-arxiv-to-md` skill
instead — it converts from the paper's LaTeX source and produces far better
headings, tables, and math than any PDF-to-markdown pipeline.

**Mixed file types:** When the user references a folder or set of documents
containing multiple supported file types (`.pdf`, `.docx`, `.xlsx`), this
skill handles only `.pdf` files. The agent MUST also invoke the sibling
skills in parallel:
- `convert-word-to-md` for any `.docx` files
- `convert-excel-to-md` for any `.xlsx` files

Never process a folder and silently skip a supported file type. All three
skills must be invoked together when mixed types are present.

## Setup (once per environment)

Before the first conversion in a given environment, follow
[`references/setup.md`](references/setup.md) step by step to ensure Python,
pip, `pymupdf4llm` (primary engine), and `markitdown` (fallback engine) are
installed. Do this proactively rather than guessing whether the environment
is ready — the script itself will also fail with a clear pointer back to
that file if no engine turns out to be importable, so it's safe to just try
the conversion first if you're reasonably confident setup was already done.

## How the conversion works

The script runs two engines, chosen by `--engine` (default `auto`):

- **pymupdf4llm (primary):** layout-aware extraction — heading detection,
  real pipe tables, reading-order text, and per-page OCR decisions (RapidOCR
  ships bundled; Tesseract is used when provisioned, see setup.md). Figures
  and page images are written to `img/` and linked **inline** at their
  original positions. The script post-processes its output to strip OCR
  highlight markup (`<mark>`) and bold-in-heading noise.
- **markitdown (fallback):** used automatically when pymupdf4llm is not
  importable or fails on a document. It extracts text and tables only —
  embedded images are extracted separately via PyMuPDF and appended as a
  `## Extracted Images` section at the end, because MarkItDown's text has no
  reliable per-page markers for inline placement.

Output structure (both engines):

```
<name>/
    <name>.md
    img/            images referenced inline (primary engine), or
                    appended in an "Extracted Images" section (fallback)
```

## Usage

The conversion script lives at `scripts/convert_pdf_to_md.py`.

**Single file:**

```powershell
python scripts\convert_pdf_to_md.py "C:\path\to\document.pdf"
```

This creates a `document\` folder next to the source file (containing
`document.md` and, if present, `document\img\`). To control the destination
folder explicitly:

```powershell
python scripts\convert_pdf_to_md.py "C:\path\to\document.pdf" -o "C:\path\to\output_folder"
```

**A folder of PDFs (batch mode):**

```powershell
python scripts\convert_pdf_to_md.py "C:\path\to\folder"
```

Add `--recursive` to also include subfolders:

```powershell
python scripts\convert_pdf_to_md.py "C:\path\to\folder" --recursive
```

Each `.pdf` found gets its own `<name>\` output folder next to it by
default. Pass `-o "C:\path\to\output_parent"` to collect all the generated
`<name>\` folders under a separate parent directory instead (subfolder
structure is preserved when combined with `--recursive`).

**Engine override:** pass `--engine markitdown` to force the fast fallback
(useful for very large documents where OCR-driven layout analysis is too
slow and layout fidelity matters less), or `--engine pymupdf4llm` to forbid
the fallback. Default `auto` is right for almost every case.

After conversion, read the resulting `.md` file(s) to perform the actual
analysis the user asked for — the script's job is only to produce accurate
Markdown (and images), not to interpret the content. The script's report
line tells you which engine ran and how many images were written; mention
the engine in your summary if the user cares about fidelity.

## Deciding where output goes

**Default — always output next to the source file.** The `<name>/` folder
is created in the same directory as the source `.pdf`. This is the required
default for every case. Do NOT override it unless the user explicitly asks
for a different location.

**Only use `-o` when** the user explicitly provides an output path (e.g.,
"save the output to `C:\output`", "put the results in `D:\work`"). Do NOT
pass `-o` based on the agent's current working directory, the session state
folder, or any implied location.

**`-o` is always a PARENT directory** (single-file and batch mode alike,
matching the convert-arxiv-to-md skill): the `<name>/` folder is created
under it. Converting several named files with a shared `-o <parent>` is
therefore safe — each document gets its own `<parent>/<name>/` folder with
its own `img/`.

**If the source file path cannot be fully resolved** — for example, the
user provides only a filename with no directory, or the path is ambiguous —
use `ask_user` to confirm the full absolute path before running the
conversion. Never guess or assume the directory.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| exit code 2, "Neither 'pymupdf4llm' nor 'markitdown' is installed" | No engine installed | Follow `references/setup.md` |
| `engine 'pymupdf4llm' failed; falling back to 'markitdown'` in output | The layout pipeline rejected the document | Expected — check the output quality and mention the fallback in your summary |
| `ERROR: Unsupported file type '...'` / exit code 3 | Not a `.pdf` file | Ask the user for the correct file, or if it's `.doc`/`.docx`/`.xlsx`, use the matching sibling skill instead |
| `ERROR: Input path not found` / exit code 3 | Wrong path, or file moved | Confirm the correct path with the user |
| `FAILED <file> -> ...` in batch output | That specific file is corrupt, password-protected, or otherwise unreadable | Report which file(s) failed; other files in the batch still succeed |
| `NOTE: skipped N non-.pdf file(s)` | Folder contains non-PDF files | Expected — those files are intentionally ignored |
| OCR quality looks poor on a scanned PDF | Low-quality scan, or OCR misread | Cross-check suspicious passages against the page images in `img/`; mention uncertainty to the user |
| Conversion is slow on a large document | The primary engine OCRs pages to drive layout analysis (~1-3s/page) | Expected; use `--engine markitdown` when speed matters more than table/layout fidelity |
| Images appear in an appendix instead of inline with the text | The fallback engine ran (MarkItDown text has no reliable per-page markers) | Expected for the fallback; cross-reference the `### Page N` heading with the surrounding text context if needed |
