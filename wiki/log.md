# Wiki Log

Append-only chronological record of operations on the wiki. Each entry begins with `## [YYYY-MM-DD] <op> | <description>` so it's parseable with `grep "^## \[" log.md | tail -N`.

Operations:
- `ingest` — a source was processed into the wiki.
- `query` — a question was answered against the wiki (typically only logged when the answer was filed back as synthesis).
- `lint` — a health check was run.
- `schema` — the schema was modified.
- `shard` — an index was sharded.

---

## [2026-09-23] init | Bootstrapped wiki skeleton from llm-wiki skill init_wiki.py: directories, SCHEMA.md, index.md, log.md, page/experience/pattern templates, graph ontology + gitignores. Retrieval setup verified ("status": "ready"; fastembed 0.8.0, sqlite-vec 0.1.9, pyyaml 6.0.3; BAAI/bge-small-en-v1.5 @ 384d; model cached at ~/.cache/llm-wiki/fastembed). 0 pages, 0 sections.

## [2026-09-23] ingest | Batch: 10 quant-trading research clippings (Artur Sepp ×5, Cesar Alvarez ×5; 2017–2024)
   Note: raw files arrived in raw/assets/; moved to raw/ (assets/ is reserved for images per SCHEMA.md).
   Created 10 source pages, 2 entity pages, 18 concept pages; rebuilt index.md (0 → 30 pages).
   Touched per source: see "Where this fits" sections; cross-links woven between Sepp's regime/convexity work and Alvarez's robustness corpus (contrast page pair artur-sepp / cesar-alvarez).
   Tag taxonomy added to SCHEMA.md; graph layer not yet populated (no typed edges added; markdown wikilinks only).

## [2026-09-24] graph | Built graph layer: authored typed edges on 7 pages, linted, extracted (49 nodes, 421 edges)
   Added `graph.relationships` frontmatter (each with verbatim raw evidence + raw_ref line anchor):
   - person:artur-sepp → 5× `authored`, 4× `works_on` (vol-carry, vol-forecasting, trend-following, smart-beta); person:cesar-alvarez → 5× `authored`, 3× `works_on` (backtest, overfitting, parameter-robustness).
   - 5× `depends_on`: volatility-carry-strategies→volatility-risk-premia; volatility-forecasting→model-cycling; smart-beta→bootstrapping-simulation; trend-following↔return-autocorrelation (mutual pair).
   - Deliberately NOT typed: cites/contradicts between the two authors — grepped raw corpus; zero cross-citations exist, so the Sepp-vs-Alvarez contrast stays as body wikilinks (mentions), not typed edges.
   wiki_graph_lint.py: no issues (49 nodes). wiki_graph_extract.py: 49 nodes, 421 edges (mentions 289, sourced_from 100, authored 10, summarizes_raw 10, works_on 7, depends_on 5). Query layer verified (neighbors/facts/path). Structural wiki_lint.py: clean. nodes.jsonl/edges.jsonl tracked; graph.sqlite/graph.graphml gitignored per default policy.
