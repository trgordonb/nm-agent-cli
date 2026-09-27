# Environment Setup for convert-arxiv-to-md

Follow these steps exactly, in order, before running
`scripts/convert_arxiv_to_md.py` for the first time in a given environment.
Don't skip steps or improvise alternatives — they're written to be
deterministic and safe to re-run.

## 1. Check Python is available (3.10+)

```bash
python --version
```

- If this fails (command not found), install Python 3.10 or newer:
  - Windows: `winget install --id Python.Python.3.12 -e`
  - macOS: `brew install python@3.12`
  - Linux (Debian/Ubuntu): `sudo apt-get update && sudo apt-get install -y python3 python-is-python3`

The script itself uses only the Python standard library — no pip packages
are required.

## 2. Check pandoc is available (2.11+)

```bash
pandoc --version
```

- If this fails, install pandoc:
  - Windows: `winget install --id JohnMacFarlane.Pandoc -e`
  - macOS: `brew install pandoc`
  - Linux (Debian/Ubuntu): `sudo apt-get install -y pandoc`
    (the distro version can be old; prefer the official `.deb` or a binary
    tarball from https://github.com/jgm/pandoc/releases if `apt` gives you
    something older than 2.11)
- Verify afterward that `pandoc --version` reports 2.11 or newer. The
  script's output format relies on flags and table behavior that are stable
  from 2.11 onward.

## 3. (Optional) Install PyMuPDF — recommended

```bash
python -m pip install "pymupdf>=1.24.0"
```

Two features use it when present, but the skill works without it:

- Reading a local arXiv PDF to extract its identifier (otherwise the script
  needs `pdftotext` from poppler, and errors clearly if neither exists).
- Rasterizing figures embedded as PDF files into PNGs so they display in
  markdown viewers. Without it, PDF figures are left as-is with a warning.

## 4. Verify the toolchain

```bash
python -c "print('python OK')" && pandoc --version | head -1
```

Both commands must succeed before you run the conversion script. If a paper
still fails after a verified setup, the cause is almost certainly the
paper's LaTeX (see "Known limitations" in SKILL.md), not the environment —
fall back to `convert-pdf-to-md` for that paper.
