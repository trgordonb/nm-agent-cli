# Environment Setup for convert-pdf-to-md

Follow these steps exactly, in order, before running `scripts/convert_pdf_to_md.py`
for the first time in a given environment. Don't skip steps or improvise
alternatives — they're written to be deterministic and safe to re-run.

## 1. Check Python is available (3.10+)

```powershell
python --version
```

- If this fails (command not found), install Python 3.10 or newer:
  - Windows: `winget install --id Python.Python.3.12 -e`
  - macOS: `brew install python@3.12`
  - Linux (Debian/Ubuntu): `sudo apt-get update && sudo apt-get install -y python3 python3-pip python-is-python3`
- If the reported version is older than 3.10, install a newer Python using
  the same command above (pymupdf4llm requires 3.10+).

## 2. Check pip is available

```powershell
python -m pip --version
```

- If this fails, bootstrap pip:

```powershell
python -m ensurepip --upgrade
```

## 3. Install the conversion engines

Use the `scripts/requirements.txt` file bundled with this skill to install
pinned, known-good versions of the dependencies:

```powershell
python -m pip install -r scripts/requirements.txt
```

This installs, in priority order:

- `pymupdf4llm` — the **primary** engine (layout-aware extraction: heading
  detection, pipe tables, per-page OCR decisions). Its OCR backend
  (RapidOCR) ships with models bundled in the wheel, so no separate model
  downloads are needed.
- `markitdown[pdf]` — the **fallback** engine, used automatically when
  pymupdf4llm is unavailable or fails on a document.
- `pymupdf` — the underlying PDF library (also used by the fallback engine
  to extract embedded images).

## 4. Verify the install

```powershell
python -c "import pymupdf4llm; from markitdown import MarkItDown; print('engines OK')"
```

Expect to see `engines OK` printed with no errors. If you see a
`ModuleNotFoundError`, repeat step 3 — pip may be installing into a
different Python environment than the one being invoked (check
`python -m pip --version` shows the same path as `python --version`'s
interpreter).

## 5. (Optional, Linux) Tesseract language data

On some Linux systems, pymupdf4llm's Tesseract backend needs `eng`
language data that the distro package omits. The script handles this
automatically when `eng.traineddata` exists in one of:

- `$TESSDATA_PREFIX` (if already set)
- `~/.local/share/tessdata/`
- `/usr/share/tesseract-ocr/*/tessdata/`

To provision it:

```powershell
mkdir -p ~/.local/share/tessdata
curl -L -o ~/.local/share/tessdata/eng.traineddata \
  https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata
```

This step is optional: when Tesseract data is missing, the bundled
RapidOCR backend takes over, which needs no setup at all.

## Notes

- This setup only needs to be done once per environment/virtual environment,
  not once per conversion.
- `convert_pdf_to_md.py` itself checks both engines at startup and prints a
  pointer back to this file if neither is importable, so re-running setup
  is safe and idempotent.
- Only `.pdf` is supported by this skill — there's no legacy-format
  equivalent to worry about (unlike Word's `.doc` or Excel's `.xls`).
- **Academic arXiv papers should NOT go through this skill** — for those,
  the `convert-arxiv-to-md` skill converts from the LaTeX source and
  preserves headings, math, and tables far better than any PDF-to-markdown
  pipeline can.
- Scanned/image-only PDFs (no embedded text layer) work through the primary
  engine's OCR, but accuracy depends on scan quality — mention residual
  uncertainty to the user if a scan looks noisy.
- The primary engine OCRs pages to drive its layout analysis, so large
  documents take time (roughly 1-3 seconds per page on a modern CPU).
  Force the faster fallback with `--engine markitdown` when speed matters
  more than layout fidelity.
