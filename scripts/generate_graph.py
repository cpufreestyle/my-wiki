#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_graph.py - Knowledge Graph Generator
Extracts [[wikilinks]] and #tags from all .md files to build a relationship graph.
No external dependencies (no networkx).
"""

from __future__ import annotations
import re, json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

WIKI_DIR = Path(__file__).parent.parent
GRAPH_JSON = WIKI_DIR / "knowledge_graph.json"

def extract_links(content):
    return re.findall(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]', content)

def extract_tags(content):
    return list({m for m in re.findall(r'(?<!#)#([\w-]+)', content)})

def build_graph():
    nodes, edges = {}, set()
    for md_file in WIKI_DIR.rglob("*.md"):
        rel = md_file.relative_to(WIKI_DIR)
        name = str(rel.with_suffix('')).replace('\\', '/')
        content = md_file.read_text(encoding='utf-8', errors='ignore')

        parent = rel.parts[0] if rel.parts else ''
        ntype = {"daily":"Diary","projects":"Project","concepts":"Concept","people":"People"}.get(parent, "Other")

        nodes[name] = {"type": ntype, "tags": extract_tags(content), "outlinks": extract_links(content), "file": str(rel)}

        for link in extract_links(content):
            edges.add((name, link))

    return nodes, edges

def compute_stats(nodes, edges):
    in_degree = defaultdict(int)
    for _, to in edges:
        in_degree[to] += 1
        for node in nodes:
            if node.endswith(to) or to.endswith(node.split('/')[-1]):
                in_degree[node] += 1

    hot = sorted(nodes.items(), key=lambda x: in_degree.get(x[0], 0), reverse=True)[:5]
    return {"total_nodes": len(nodes), "total_edges": len(edges),
            "hot": [{"name": n, "type": d["type"]} for n, d in hot],
            "generated": datetime.now().isoformat()}

def main():
    print("[Graph] Generating knowledge graph...")
    nodes, edges = build_graph()
    stats = compute_stats(nodes, edges)

    colors = {"Diary": "#4CAF50", "Project": "#2196F3", "Concept": "#FF9800", "People": "#9C27B0", "Other": "#9E9E9E"}
    in_degree = defaultdict(int)
    for _, to in edges: in_degree[to] += 1

    g_nodes = [{"id": n, "label": n.split('/')[-1], "type": d["type"],
                "color": colors.get(d["type"], "#9E9E9E"),
                "connections": in_degree.get(n, 0), "tags": d["tags"][:5]}
               for n, d in nodes.items()]
    g_links = [{"source": s, "target": t} for s, t in edges]

    graph_data = {"stats": stats, "nodes": g_nodes, "links": g_links}
    GRAPH_JSON.write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding='utf-8')

    print("  [OK] Nodes:", stats["total_nodes"], "  Edges:", stats["total_edges"])
    hot_names = ", ".join(n["name"] for n in stats["hot"][:3])
    print("  [OK] Hot:", hot_names if hot_names else "(none)")
    print("  [OK] graph.json saved")

    # Markdown report
    report = WIKI_DIR / "knowledge_report.md"
    lines = ["# Knowledge Graph Report\n\n",
             "> Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n\n---\n\n",
             "## Stats\n\n",
             "- Total nodes: " + str(stats["total_nodes"]) + "\n",
             "- Total edges: " + str(stats["total_edges"]) + "\n\n",
             "## Hot Nodes\n\n"]
    for n in stats["hot"]:
        lines.append("- [" + n["name"] + "](" + n["name"] + ".md) (" + n["type"] + ")\n")

    by_type = defaultdict(list)
    for name, data in nodes.items(): by_type[data["type"]].append(name)
    lines.append("\n## By Type\n\n")
    for ntype, lst in sorted(by_type.items()):
        lines.append("### " + ntype + " (" + str(len(lst)) + ")\n\n")
        for n in lst[:10]: lines.append("- " + n + "\n")
        if len(lst) > 10: lines.append("... and " + str(len(lst)-10) + " more\n")
        lines.append("\n")

    report.write_text(''.join(lines), encoding='utf-8')
    print("  [OK] knowledge_report.md updated")

if __name__ == "__main__":
    main()
