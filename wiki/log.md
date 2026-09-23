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
