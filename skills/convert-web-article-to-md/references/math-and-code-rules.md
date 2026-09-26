# Math and Code Conversion Rules

Deep-dive for the `convert-web-article-to-md` script's conventions and for
hand-repairing the warnings it emits. Read this when a conversion report says
"Needs attention" or when you're converting an unusual page by hand.

## 1. Where the math hides

A single page may mix several encodings. Recover TeX from whichever you find:

| Encoding in raw HTML | What it looks like | Recovery |
|---|---|---|
| Loose TeX text nodes | `\begin{eqnarray}...\end{eqnarray}` or `\[ ... \]` sitting **between** `<p>` tags, not inside any element | The script wraps these in `$$...$$`. This is the QuantStart pattern — the reason naive converters lose every display equation |
| Inline TeX in prose | `\( X_t \)` inside paragraph text | `\( ... \)` → `$ ... $`. Losing these leaves broken sentences ("at time , is the mean") |
| MathJax v2 | `<script type="math/tex">X_t^2</script>` and `type="math/tex; mode=display"` | The script text is the TeX; `mode=display` marks display math |
| MathJax v3 | `<mjx-container>` markup, TeX no longer in a script tag | Recover from the preceding `aria-label`/`<mjx-assistive-mml>` MathML if present, else transcribe from the rendered equation |
| KaTeX | `<span class="katex">` containing `<annotation encoding="application/x-tex">` | The annotation holds the original TeX verbatim — take it |
| Math as images | `<img class="math latex" src=".../equation.png" alt="\int_0^t ...">` | Use the `alt` text as TeX when it looks like LaTeX; otherwise transcribe from the rendered image |
| Already-dollars | `$$ ... $$` / `$ ... $` in the HTML | Keep as-is |
| ASCII pseudo-math | `<p><strong>d(log S_t) = (mu - sigma^2/2) dt + sigma dW_t</strong></p>` — whole-line bold spans written as plain ASCII | The script passes them through (and warns). Transcribe to native `$$...$$` LaTeX — see §2b |
| Hydration markdown blob | Article markdown embedded JSON-escaped inside a `<script>` blob (Next.js-style SSR data), searchable in `raw.html` | Ground truth when the rendered DOM is lossy — the site's renderer may have consumed equation underscores into `<em>` tags |

## 2. Normalization rules (source TeX → clean markdown math)

- `\( ... \)` → `$ ... $` and `\[ ... \]` → `$$ ... $$` (keep any newlines;
  display math reads best as `$$\n<body>\n$$`).
- `\begin{eqnarray}` → `\begin{aligned}` (and `\end{eqnarray}` likewise).
  `eqnarray` is deprecated LaTeX and some markdown renderers reject it. The
  eqnarray `&=&` alignment style (`x &=& y`) is valid inside `aligned` — leave
  it as the author wrote it.
- `\begin{equation}`, `\begin{align}`, `\begin{gather}` etc. stay *inside*
  the `$$...$$` wrapper: `$$\n\begin{aligned}...\end{aligned}\n$$`. Don't
  strip the environments — they carry the author's alignment.
- Keep `\label{...}`, `\tag{...}`, `\nonumber` — they document the author's
  numbering and are harmless.
- Escape currency/prose dollars so renderers can't pair them into math:
  "the trade costs \$5,000 and exits at \$10,000". Rule of thumb used by the
  script: content with TeX syntax (`\`, `^`, `_`, `{`) is math; content
  starting with a digit or currency symbol is money; anything else (single
  letters like `$t$`, `$N$`) is math.
- Markdown escaping hazards inside math: `_`, `*`, `\`, and `<` must appear
  verbatim in the output. The script token-protects every bare `_`/`^` in
  prose so markdownify can never normalize `_..._` emphasis pairs to `*` —
  if you still see `(b b^T)*{ik}`-style fragments, the loss happened in the
  site's own renderer before the HTML was served: recover the original
  equation from the hydration markdown blob (grep `raw.html` for the
  equation text; it is JSON-escaped, so `\\(` = `\(`).
- Tables/alignment: `\|` inside `\begin{array}` column specs and `|` used as
  a delimiter must not be confused with markdown table pipes — math spans are
  never parsed as markdown tables.
- Delimiter balance: within one line/paragraph, unescaped `$` must come in
  pairs. The script's verifier flags odd counts; when fixing, prefer escaping
  the prose dollar over unescaping the math one.

### 2b. Upgrading ASCII pseudo-math to LaTeX

When the verifier reports bold ASCII pseudo-math, transcribe each line into a
native `$$...$$` block. The source ASCII is a faithful but non-TeX notation —
translate mechanically, keeping the author's structure:

- `d(log S_t) = (mu - sigma^2 / 2) dt + sigma dW_t` →
  `$$d(\log S_t) = \left(\mu - \tfrac{\sigma^2}{2}\right) dt + \sigma\, dW_t$$`
- `df/dt` → `\frac{df}{dt}` or `\partial f/\partial t` (match how the prose
  around it refers to the derivative); `sum_{i,k}` → `\sum_{i,k}`;
  `integral_0^t` → `\int_0^t`; `Delta` → `\Delta`; `*` multiplication →
  juxtaposition or `\cdot`.
- Greek words (`mu`, `sigma`, `theta`) → their symbols; keep sub/superscripts
  exactly (`W_t^2`, `d^2f/dx^2` → `\partial^2 f/\partial x^2`).
- Cross-check each transcription against the hydration markdown blob in
  `raw.html` (JSON-escaped) or the rendered page — don't guess signs or
  indices. When a warning lists 17 equations, deliver 17 conversions.

## 3. Code block rules

- Source: `<pre><code class="language-python">` (Prism), `class="lang-py"` /
  `highlight-source-python` (GitHub), `class="highlight-python"` (Pygments),
  `brush: python;` (SyntaxHighlighter), or bare `<pre>`.
- Output: fenced block with the detected language tag. No language detected →
  bare fence; guess from content (`>>>` → `python` REPL, `$ ` prompts →
  `bash`, `fn ` → rust-ish) and mention the guess.
- Unescape HTML entities inside code: `&lt;` `<`, `&gt;` `>`, `&amp;` `&`,
  `&quot;` `"`, `&#39;` `'`. `&lt;`/`&gt;` leftovers in "code" that is
  actually highlighted-HTML soup are a symptom, not content.
- Strip syntax-highlight `<span>` wrappers (saved-DOM input) keeping only
  their text — code must be plain, executable text.
- Never reformat, re-indent, or "fix" code. Verbatim content is the contract;
  agents may need to run it.
- Extend the fence when the code itself contains backticks (```` ```` ````).
- Leading shell prompts (`$ `, `>>> `, `In [1]: `) and synthetic line numbers
  (`1  import numpy`) may be stripped only when they wrap *every* line
  uniformly and clearly aren't part of the code.
- The article's final "Full Code" listing is the authoritative, runnable
  version — prefer it over fragmented mid-article snippets when they differ.

## 4. What makes the output agent-readable

- Front matter carries provenance (`title`, `source`, `site`, `author`,
  `published`, `converted`) so agents can cite and freshness-check.
- One `#` title, article sections at `##`/`###` — a clean hierarchy makes
  chunking and outlining work.
- Math is native `$`/`$$` LaTeX (renderable *and* string-searchable), never
  images of equations.
- Links stay absolute so citations survive out of context; figures live in
  `media/` and are referenced inline where they appeared.
- No site chrome: no "Subscribe", cookie banners, related-post carousels,
  share buttons, or comment threads.

## 5. Verification checklist

1. Script report: `Verification: no leftover markers...` or every `Needs
   attention` item explained/fixed.
2. Grep sweeps over the final `.md` (outside code fences):
   - `\\(`, `\\[` → unconverted math spans
   - `\\begin\{(?!aligned|cases|matrix|array|split|gathered)` outside `$$`
     → raw environments to wrap
   - `&lt;|&gt;|&amp;` in prose → entity leftovers
   - odd unescaped-`$` lines → unbalanced delimiters
   - `\*[A-Za-z0-9]{0,4}\{` → emphasis-mangled subscripts (recover from the
     hydration blob, see §2)
3. Skim: heading hierarchy sane, fences tagged, first/last section is article
   content (no sign-up CTA tail), image links resolve on disk.
4. Compare counts: the report's display/inline math counts should roughly
   match the equation density you'd expect from the section titles ("Bayesian
   batch solution" pages are equation-dense; a count of 0 means something was
   dropped).
5. When in doubt about a dropped passage, search `raw.html` for the
   surrounding sentence and diff.
