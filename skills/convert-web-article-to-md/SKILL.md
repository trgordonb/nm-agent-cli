---
name: convert-web-article-to-md
description: 'Converts web blog articles — especially math/code-heavy technical posts (quantitative finance, machine learning, physics) — into clean, AI-agent-readable Markdown: native $...$/$$...$$ LaTeX math, language-tagged code fences, downloaded figures, and provenance front matter. Use this skill whenever the user shares a blog URL or web article and wants it converted to markdown, saved for offline/agent reading, summarized, annotated, or ingested — even if they only say "read this article", "save this post", or "turn it into md" and never say "convert". Also use it when a fetched-markdown rendering of an article came back with missing equations, dropped code listings, or broken sentences like "at time , is the mean" (inline math silently stripped) and needs repair. NOT for arXiv papers (use convert-arxiv-to-md — LaTeX source converts far better) or local PDFs (use convert-pdf-to-md); for a mix of sources, invoke those siblings alongside this one so nothing is silently skipped.'
---

# Convert Web Articles to Markdown

## When to use this skill

Technical blogs that mix math with code are the hardest pages to convert and
the easiest to get silently wrong. Fetched-markdown services (URL-to-MD web
readers, `WebFetch`, reader modes) routinely destroy exactly the parts that
make the article valuable. On a typical QuantStart article (e.g.
"Ornstein-Uhlenbeck Simulation with Python") a naive conversion loses:

- **All display equations.** Many blogs author math as raw LaTeX in loose
  HTML text (`\begin{eqnarray}...\end{eqnarray}` sitting between `<p>` tags,
  `\( ... \)` inline) and render it client-side with MathJax/KaTeX. Because
  the TeX is not inside any block element, text extractors drop it — you get
  "The SDE is given by:" followed by nothing.
- **All inline symbols.** `\( X_t \)` disappears mid-sentence, leaving
  "represents the stochastic process at time , is the long-term mean".
- **The code listings.** Prism/Pygments `<pre><code class="language-python">`
  blocks are frequently stripped or mangled, so the "Full Code" section ends
  up empty.

This skill converts from the **raw HTML** instead, recovering math into
native `$...$` / `$$...$$` LaTeX and code into language-tagged fences. The
resulting file is written for agent consumption: provenance front matter, a
clean heading hierarchy, absolute links, figures in `media/`, and no site
chrome.

**Routing.** arXiv paper (ID, URL, or arXiv-stamped PDF) → `convert-arxiv-to-md`
— the LaTeX source beats any HTML pipeline. Local PDFs → `convert-pdf-to-md`.
Blog/article URLs and saved `.html` files → this skill. When a request mixes
source types, invoke the relevant skills together.

## Setup

Nothing to install: `beautifulsoup4`, `markdownify`, and `requests` are
already project dependencies. Sanity check (optional):

```bash
uv run python -c "import bs4, markdownify, requests"
```

## Usage

```bash
# Single article URL
uv run python skills/convert-web-article-to-md/scripts/convert_web_article_to_md.py \
    https://www.quantstart.com/articles/ornstein-uhlenbeck-simulation-with-python

# Batch (several URLs and/or local .html files, mixed)
uv run python skills/convert-web-article-to-md/scripts/convert_web_article_to_md.py \
    <url-1> <url-2> workspace/saved-page.html

# Options
-o <parent_dir>   # where <slug>/ folders are created (default: . for URLs,
                  # the HTML file's own directory for local files)
--no-media        # keep images as absolute URLs instead of downloading
--source auto|dom|blob   # auto (default) prefers the site's embedded hydration
                  # markdown and falls back to the rendered DOM; dom forces the
                  # DOM pipeline; blob requires a hydration blob and fails
                  # without one
```

Each input produces:

```
<slug>/
├── <slug>.md     the converted article
├── media/        content images, linked inline at their original position
├── raw.html      the exact HTML parsed — kept for auditing and re-parsing
└── hydration.md  the extracted author markdown (only when a hydration blob
                  was found and used)
```

## How the conversion works

**Preferred source: the site's own markdown.** SSR frameworks (Next.js-style)
embed the markdown the site rendered inside `<script>` hydration blobs. The
script finds and validates such a blob (structure signals + title match) and,
when found, converts that source directly — math markers normalized, prose
dollars escaped, links absolutized, images downloaded. This is the author's
own markdown, so it is lossless where the rendered DOM is not: subscripts
that the site's renderer ate into `<em>` tags survive verbatim. The report's
`Source:` line tells you which path ran.

**Fallback: the rendered DOM.** Without a usable blob, the script isolates
the article body (dropping nav/ads/related-posts/cookie chrome), then
recovers math from every encoding it reasonably finds: loose
`\begin{env}` TeX nodes, `\( \)` / `\[ \]` spans, MathJax v2
`<script type="math/tex">` tags, and KaTeX `<span class="katex">` (TeX is
recovered from the embedded annotation). `\begin{eqnarray}` is rewritten to
`aligned`. Code blocks become fenced blocks with the language detected from
Prism/Pygments/highlight.js/prettyprint class names; prose dollars ("$5 to
$10") are escaped so renderers can't pair them into fake math, while
variables like `$t$` stay math. Ad/avatar/tracker images are dropped; content
images are downloaded to `media/` and linked inline.

Math and code are protected behind placeholder tokens during the generic
HTML→Markdown pass, so markdownify's underscore/asterisk escaping can never
mangle `$X_t$` or fence content. Every bare `_` and `^` in prose gets the
same protection (some sites author equations as plain text with `X_t`-style
subscripts, and text nodes get split around `<em>`/entities where prefix
matching can't help). Articles ending in sign-up CTA boxes ("Want to go
deeper", "Keep reading", "Next step") are truncated — only when the marker
sits in the last 30% of the document and is followed by explicit CTA
vocabulary, so real "Next steps" sections survive.

## Reading the report — warnings are the contract

The script ends with a summary (math/code/image counts) plus either
`Verification: no leftover markers...` or a `Needs attention:` list. Those
warnings are specific: unconverted `\(`, raw `\begin{...}` outside `$$`,
unbalanced `$`, HTML-entity leftovers, failed image downloads. Fix each one
in the `.md` by hand (the recovery rules in
[`references/math-and-code-rules.md`](references/math-and-code-rules.md)
cover the common cases) and re-check against `raw.html` — do not report a
conversion as clean while warnings remain unexplained. After the report,
skim the produced `.md` yourself: front matter present, first and last
sections are article content (not Subscribe/cookie boilerplate), math
delimiters visually paired, every fence has a language tag.

## JavaScript-rendered pages (math/code absent from raw HTML)

Some sites render the article, the math, or the code only client-side. The
tell: `raw.html` contains no math markers (`\(`, `\begin{`, `math/tex`,
`katex`) **and** no `<pre>` blocks although the live page shows them. The
script cannot recover what isn't in the HTML — render the page in a real
browser first:

1. Use the `browser-use:control-browser` skill to open the URL and let it
   finish rendering.
2. Save the rendered DOM (post-JS HTML) to a file, e.g.
   `workspace/<slug>.html`.
3. Run this skill's script on that file. Note the saved DOM carries
   syntax-highlight `<span>` wrappers in code blocks; the script strips them
   and keeps the plain text.

Paywalled articles are out of scope — tell the user rather than fetching
around the wall.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `HTTP 403/429` error at fetch | The site blocks scripted requests | Render and save the page in a browser (see above), convert the saved file |
| Output is tiny/empty | Wrong content container detected on an unusual layout | Open `raw.html`, find the article wrapper's class/id; if it's beyond quick manual fixes, extract the body by hand using the reference doc's rules |
| Equations appear as images | Math baked into `<img>` (no TeX in the page) | Transcribe display equations to LaTeX manually; the `alt` text often holds the TeX |
| `unconverted \( / \[ math remains` warning | Regex missed a nested/unusual span | Convert those spans by hand in the `.md`: `\(...\)` → `$...$`, `\[...\]` → `$$...$$` (see reference doc) |
| Mangled rendered-text math soup (e.g. `EWMAt=(1−λ)×Yt+...EWMA_t = ...`) | KaTeX variant with no `<annotation>` (some WordPress plugins): TeX sits as trailing text inside `<math>` | Fixed in-script: TeX recovered from the `<math>` tail; for older runs, transcribe from the `<span class="katex-mathml"><math>...` block in `raw.html` |
| All article figures missing, `Images: N chrome/ads dropped` | Notebook posts embed figures as base64 `data:image/png;base64,` URIs | Fixed in-script: data-URI PNG/JPEG figures are decoded into `media/`. If the decode fails, the report lists each failure under Needs attention |
| `data-URI image decode failed (...)` warning | Malformed or non-raster data-URI | Check `raw.html`; download/decode by hand if the figure matters |
| `bold ASCII pseudo-math` warnings (many) | The site authors display equations as bold plain text (`**d(log S_t) = ...**`), not LaTeX — the converter reproduces them faithfully | Transcribe each into native `$$...$$` LaTeX against the rendered page (or the hydration markdown blob in `raw.html`); this is expected for some sites (e.g. quantt.co.uk) |
| `emphasis-mangled math (*{...})` warning (DOM path only) | The site's own markdown renderer consumed equation underscores into `<em>` tags before the converter ever saw them — the DOM is already lossy | The automated fix is the hydration path (`--source blob`, or check it ran: the `Source:` report line). Otherwise grep `raw.html` for the equation text: the original markdown is usually embedded in a hydration `<script>` blob (JSON-escaped). Restore the affected equation from there |
| `--source blob` fails with "no hydration markdown blob found" | The site doesn't embed its markdown source (server-rendered HTML only) | Use `--source dom` (or auto); the DOM pipeline is the normal path for such sites |
| `raw LaTeX environment outside $$` warning | An environment the recovery pass didn't wrap | Wrap it in `$$\n...\n$$`; rewrite `eqnarray` to `aligned` while you're there |
| Fences contain `<span class="token">` junk | Input was a browser-saved DOM with highlighter markup | Expected input for the script — but if a block still has spans, strip them keeping text content |
| `missing media file: media/...` | Image download failed | Re-download by hand or replace with the absolute URL (it's in the md) |

## Known limitations

- **Client-side-only content** needs the browser-render pass above; the
  script fails loudly (empty math/code counts) rather than pretending.
- **Math-as-images** without TeX in `alt` text can't be transcribed
  automatically — flag those to the user.
- **Embedded iframes** (videos, calculators) become `[embedded content: url]`
  links, not embeds.
- Base64 `data:image/png;base64,` / `data:image/jpeg;base64,` figures are
  decoded into `media/` (notebook-style posts); other data-URI images remain
  dropped.
- The chrome-removal heuristics are conservative (anything holding half the
  article survives), but novel layouts can still leak boilerplate — the final
  skim catches it.
