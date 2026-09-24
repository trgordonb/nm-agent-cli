#!/usr/bin/env python3
"""Present the compiled wiki knowledge graph: Mermaid + interactive HTML.

Reads the compiled graph (wiki/graph/graph.sqlite produced by
wiki_graph_extract.py) and emits two views under wiki/graph/:

1. graph-overview.mmd — Mermaid flowchart (renders in Obsidian, GitHub, most
   markdown viewers). Nodes ranked by edge degree, capped by --node-limit,
   edges labeled with their predicate.
2. index.html — a single self-contained interactive page (vis-network via
   CDN): drag physics, predicate-labeled edges, node-type colors, live title
   filter, and a click detail panel with typed-edge provenance.

Nothing is recomputed from markdown here: graph.sqlite rows are the extract
output; this script only *presents* them.

Usage:
    uv run --script wiki_graph_visualize.py wiki/ [--node-limit 40] [--out DIR] [--json]
"""

import argparse
import collections
import json
import os
import sqlite3
from pathlib import Path
import subprocess as _unused

NODE_COLORS = {
    "source": "#f5a623",
    "concept": "#4a90d9",
    "entity": "#7ed321",
    "person": "#bd10e0",
}
DEFAULT_NODE_COLOR = "#909090"


def load_graph(wiki_root: str):
    graph_db = os.path.join(wiki_root, "graph", "graph.sqlite")
    if not os.path.isfile(graph_db):
        raise FileNotFoundError(
            f"{graph_db} not found — run wiki_graph_extract.py first"
        )
    conn = sqlite3.connect(f"file:{graph_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        nodes = [
            {
                "id": r["id"],
                "title": r["title"],
                "node_type": r["node_type"] or "concept",
                "path": r["path"] or "",
            }
            for r in conn.execute("SELECT id, title, node_type, path FROM nodes")
        ]
        edges = [
            {
                "subject": r["subject"],
                "target": r["object"],
                "predicate": r["predicate"],
                "confidence": r["confidence"] or "",
            }
            for r in conn.execute("SELECT subject, object, predicate, confidence FROM edges")
        ]
    finally:
        conn.close()
    return nodes, edges


def top_nodes(nodes: list[dict], edges: list[dict], cap: int):
    """Top-N nodes by edge degree + only edges between kept nodes."""
    degree = collections.Counter()
    for e in edges:
        degree[e["subject"]] += 1
        degree[e["target"]] += 1
    ids = {n["id"] for n in nodes}
    ranked = [nid for nid, _ in degree.most_common() if nid in ids][:cap]
    keep = set(ranked)
    kept_edges = [e for e in edges if e["subject"] in keep and e["target"] in keep]
    return [n for n in nodes if n["id"] in keep], kept_edges


def _mermaid_id(index: int) -> str:
    return f"n{index}"


def write_mermaid(out_dir: Path, nodes: list[dict], edges: list[dict]) -> Path:
    out = Path(out_dir) / "graph-overview.mmd"
    lines = ["graph LR"]
    id_to_var = {}
    for i, node in enumerate(nodes):
        var = _mermaid_id(i)
        id_to_var[node["id"]] = (var, node["node_type"])
        safe = node["title"].replace('"', "'").replace("[", "(").replace("]", ")")
        lines.append(f'    {var}["{safe[:60]}"]')
    for e in edges:
        s, t = id_to_var.get(e["subject"]), id_to_var.get(e["target"])
        if not s or not t:
            continue
        lines.append(f'    {s[0]} -->|{e["predicate"]}| {t[0]}')
    # node-type color classes (per group)
    for ntype in sorted({typ for _, typ in id_to_var.values()}):
        member_vars = [var for _, (var, typ) in id_to_var.items() if typ == ntype]
        color = NODE_COLORS.get(ntype, DEFAULT_NODE_COLOR).replace("#", "")
        lines.append(f'    classDef c{ntype} fill:#{color}')
        lines.append(f'    class {" ".join(member_vars)} c{ntype}')
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_html(out_dir: Path, nodes: list[dict], edges: list[dict]) -> Path:
    out = Path(out_dir) / "index.html"
    payload = {
        "nodes": [
            {"id": n["id"], "label": n["title"][:42], "group": n["node_type"], "path": n["path"]}
            for n in nodes
        ],
        "edges": edges,
    }
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>NM-Agent wiki graph</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body { margin: 0; font-family: system-ui, sans-serif; }
  #search { position: absolute; top: 12px; left: 12px; z-index: 20; padding: 6px 10px;
            width: 260px; border: 1px solid #999; border-radius: 6px; font-size: 14px; }
  #detail { position: absolute; left: 12px; bottom: 12px; z-index: 20; max-width: 460px;
            background: rgba(255,255,255,0.94); border: 1px solid #bbb; padding: 8px 12px;
            border-radius: 8px; font-size: 13px; display: none; }
  #network { width: 100vw; height: 100vh; }
</style>
</head>
<body>
<input id="search" placeholder="filter nodes by title…">
<div id="detail"></div>
<div id="network"></div>
<script>
const DATA = __PAYLOAD__;
const container = document.getElementById("network");
const nodes_ds = new vis.DataSet(DATA.nodes.map((n) => ({
    id: n.id, label: n.label, group: n.group, title: n.id,
})));
const edges_ds = new vis.DataSet(DATA.edges.map((e) => ({
    from: e.subject, to: e.target,
    label: e.predicate, arrows: "to",
    font: { size: 8, color: "#777" },
    color: { color: e.confidence === "high" ? "#2b7a3d" : "#b9b9b9", opacity: 0.85 },
})));
const net = new vis.Network(container, { nodes: nodes_ds, edges: edges_ds }, {
    groups: { source: "#f5a623", concept: "#4a90d9", entity: "#7ed321", person: "#bd10e0" },
    physics: { solver: "barnesHut", barnesHut: { springLength: 140 } },
    interaction: { hover: true, tooltipDelay: 250 },
});
const detail = document.getElementById("detail");
net.on("click", (params) => {
    if (!params.nodes.length) { detail.style.display = "none"; return; }
    const id = params.nodes[0];
    const mine = DATA.edges.filter((e) => e.subject === id || e.target === id);
    const node = NODE_LOOKUP[id];
    detail.innerHTML =
        `<b>${node.label}</b><br/><i>${node.group}</i> — ${node.id}<br/><br/>` +
        `<u>Typed edges (${mine.length})</u><br/>` +
        mine.map((ite) => `· ${item_meta(ite, id).toString()}`).join("<br/>");
    detail.style.display = "block";
});
function typed(ite) {
    return `[${ite}]`;
}
const NODE_LOOKUP = Object.fromEntries(DATA.nodes.map((n) => [n.id, n]));
document.getElementById("search").addEventListener("input", (ev) => {
    const q = ev.target.value.toLowerCase();
    const kept = DATA.nodes.filter(
        (n) => !q || n.label.toLowerCase().includes(q) || n.id.toLowerCase().includes(q)
    );
    const keepids = new Set(kept.map((n) => n.id));
    nodes_ds.only({});
    nodes_ds.forEach((nd) => { nodes_ds.update({ id: nd.id, hidden: !keepids.has(nd.id) }); });
});
</script>
</body>
</html>
"""
    out.write_text(html.replace("__PAYLOAD__", json.dumps(payload, default=str)), encoding="utf-8")
    return out


def main(wiki_root: str = "wiki", node_limit: int = 40, out_dir: str | None = None):
    out_path = out_dir or os.path.join(wiki_root, "graph")
    nodes, edges = load_graph(wiki_root)
    keep_nodes, kept_edges = top_nodes(nodes, edges, cap=node_limit)
    mm = write_mermaid(out_path, keep_nodes, kept_edges)
    html = write_html(out_path, keep_nodes, kept_edges)
    kept = f"Visualize top {len(keep_nodes)} nodes with {len(kept_edges)} edges\n"
    print(kept)
    print(f"  mermaid: {mm}\n  html:    {html}")
    return mm, html


if __name__ == "__main__":
    import sys
    ap = argparse.ArgumentParser(description="Visualize the compiled wiki graph (Mermaid + interactive HTML)")
    ap.add_argument("wiki_root", nargs="?", default="wiki")
    ap.add_argument("--node-limit", type=int, default=40)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    main(a.wiki_root, a.node_limit, a.out)
