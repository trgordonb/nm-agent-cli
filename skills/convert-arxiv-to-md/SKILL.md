---
name: convert-arxiv-to-md
description: 'Converts arXiv papers into clean, structured Markdown by fetching the paper''s LaTeX source from arXiv and converting it with pandoc — headings, real tables, native math ($...$), figures, and references all come out intact, unlike PDF text-scraping which mangles them. Use this skill whenever the user gives an arXiv ID or URL (e.g. arxiv.org/abs/2511.12490), a local PDF that carries an arXiv stamp (arXiv:YYMM.NNNNN), or asks to convert / read / summarize / review / extract tables, math, or data from any arXiv preprint — even if they just say "convert this paper to markdown" and never mention arXiv explicitly; check the PDF for the arXiv identifier first. For PDFs with no arXiv identifier, use the convert-pdf-to-md skill instead. When the user references a folder of papers, run this skill on every paper that has an arXiv ID and convert-pdf-to-md on the rest, so no file is silently skipped.'
---

# Convert arXiv Papers to Markdown

## When to use this skill

arXiv papers are submitted as LaTeX source, and arXiv serves that source to
anyone. Converting from the source with pandoc preserves everything that PDF
text extraction destroys: the heading hierarchy, real tables, native math
(`$...$`), figure placement, and cross-references. Always prefer this path
when the paper has an arXiv identifier, and only fall back to
`convert-pdf-to-md` when no source exists.

**Not for:** papers with no arXiv identifier, or PDF-only submissions (the
script will tell you when it can't find a source). Route those to
`convert-pdf-to-md`.

## Setup

Before first use in an environment, follow `references/setup.md` — in short:
pandoc must be on PATH (Python 3.10+ is required for the script itself).
Check quickly with:

```bash
pandoc --version
```

If it fails, read and follow `references/setup.md` before continuing. Do not
improvise alternate converters (pypdf, ad-hoc regex parsers, etc.) — they
reproduce exactly the mangling this skill exists to avoid.

## Usage

```bash
# From an arXiv ID or URL
python skills/convert-arxiv-to-md/scripts/convert_arxiv_to_md.py 2511.12490
python skills/convert-arxiv-to-md/scripts/convert_arxiv_to_md.py https://arxiv.org/abs/2511.12490

# From a local PDF that carries an arXiv stamp (ID is extracted automatically)
python skills/convert-arxiv-to-md/scripts/convert_arxiv_to_md.py "workspace/Some_ArXiv_Paper.pdf"

# Batch: any mix of IDs, URLs, and PDFs
python skills/convert-arxiv-to-md/scripts/convert_arxiv_to_md.py 1706.03762 2005.14165 ./paper.pdf

# Keep the LaTeX source alongside the output (useful for re-conversion)
python skills/convert-arxiv-to-md/scripts/convert_arxiv_to_md.py 2511.12490 --keep-source
```

Output lands next to the source PDF, or in the current directory for ID/URL
inputs (override with `-o/--output`):

```
Discovery-of-a-13-Sharpe-OOS-Factor-Drift-Regimes/
├── Discovery-of-a-13-Sharpe-OOS-Factor-Drift-Regimes.md
├── media/            figures, linked inline where they appear
└── latex-src/        only with --keep-source
```

## Reading the output

The markdown is written for Obsidian/GitHub rendering:

- Headings are numbered like the PDF (`# 1 Introduction`, `## 3.1 ...`).
- Math is native `$...$` / `$$...$$` LaTeX — renderable, editable.
- Tables are pipe tables; a table too complex for pipe syntax is emitted as
  HTML, which still renders.
- Citations appear as `[@bibtex-key]`; the full references live in a
  `References` section at the end. When quoting sources back to the user,
  resolve keys against that section (e.g. `[@lo_mackinlay_1990]` → "Lo and
  MacKinlay (1990)").
- Figures are linked inline at their original positions from `media/`.

## Verifying a conversion

Run the script, then check its report line — it prints heading counts,
citation keys, and figure files, plus warnings for anything it could not do
(unresolved references, unrenderable TikZ figures, missing bibliography).
Then skim the top of the produced `.md` yourself (title in YAML front matter,
numbered headings, `$`-math intact) before telling the user it succeeded. If
the report shows `WARNING: no markdown headings` or pandoc failed, the
source probably uses packages pandoc cannot parse — fall back to
`convert-pdf-to-md` for that paper and say so in your summary to the user.

## Known limitations

- **TikZ/pgfplots figures** are drawn in LaTeX, not embedded images, so they
  cannot be extracted; the script warns how many were dropped. Point the
  user to the PDF for those figures.
- **PDF-only submissions** (no LaTeX source on arXiv) fail with a clear
  error — use `convert-pdf-to-md`.
- **Exotic classes** (`subfiles`, some journal styles with heavy macros) can
  leave fragments of raw LaTeX in the output; when the verification skim
  looks garbled, prefer the fallback path.
- **Rate limits**: arXiv throttles rapid repeated downloads; the script
  reports this and a short wait usually clears it.

## Recovering from "pandoc failed (exit 64)" on one paper

Malformed sources are common enough that the script repairs them itself:
when pandoc rejects a paper, it retries once after content-preserving
surgery — deleting `\vskip\baselineskip` primitives, flattening nested
`tabular[t]` wrappers inside outer tables, unwrapping `turn` rotation
environments, closing dangling `{` groups before `\end{document}`, and
trimming whitespace inside `\includegraphics` paths. Each repair appears in
the report as a `source repair:` note, and the repairs never fire on
well-formed papers.

If the retry still fails, escalate manually, patching the source minimally
(a local `.tar.gz` of the source is a valid script input, so the full
pipeline still runs). Keep a pristine copy of the original archive so each
edit is a re-appliable delta, and test cheaply with direct
`pandoc -f latex -t markdown` calls before repacking:

1. **Author typo: unclosed `{` in a paragraph.** Symptom is the misleading
   `Error at ... (line N, column 1): unexpected \end  \end{document}` —
   the open brace swallows the rest of the document, so the reported line is
   NEVER the bug, and naive prefix bisection produces false positives. Run a
   LaTeX-aware scanner (comment-stripping, `$`/`$$`/`\[`/`\(` math states,
   brace depth) over the body and find the first line where group depth
   becomes nonzero and never returns to 0. The auto-repair's document-level
   brace balancing only fires for small (≤3) imbalances; a larger one needs
   the precise diagnosis. Sanity counter: strip `%`-comments, replace all
   `$...$` spans with a placeholder, then `{` minus `}` must be 0 for the
   whole file.
2. **Deeper structural damage** (mismatched environments, corrupted
   floats): fix by hand in the same minimal-patch style, then re-run the
   script on the repaired archive.
3. **When the source is hopeless**, fall back to `convert-pdf-to-md` and
   say so in your summary to the user.

## References come in three shapes — the script handles all of them

Pandoc never runs BibTeX, so the script bridges each bibliography layout
itself and prints what it did:

- **Compiled `.bbl` in the payload** (with or without the `.bib`): spliced
  into the source so the rendered reference list survives.
- **Inline `thebibliography`** in the `.tex`: rendered directly by pandoc;
  the script adds the `References` heading.
- **`.bib` only** (no `.bbl`): the script renders the cited entries itself
  from the `.bib` and appends a `# References` section, keeping `[@key]`
  citations traceable — the report line notes this ("rendered N references
  from ...").

Still verify a `# References` section exists during your output check; if it
is missing, the payload had no `.bbl` and no `.bib` the script could find —
the report warns about that, and the paper's citations will remain
`[@key]`-only.
