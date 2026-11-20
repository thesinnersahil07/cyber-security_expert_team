#!/usr/bin/env python3
"""Persistent self-training knowledge base manager for Cyber Command Hive Apex.

Allows research_trainer and cyber_mentor_coach to store, search, and list
verified tool cards, web-researched playbooks, no-tool Python fallbacks, and
After-Action Review (AAR) lessons across sessions.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = ("tools", "playbooks", "fallbacks", "aar")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip().lower()).strip("-")
    return cleaned[:64] or "entry"


def ensure_kb(kb_root: Path) -> Path:
    kb_root.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        (kb_root / category).mkdir(parents=True, exist_ok=True)
    index_path = kb_root / "index.json"
    if not index_path.exists():
        index_path.write_text(json.dumps({"entries": []}, indent=2), encoding="utf-8")
    return index_path


def load_index(index_path: Path) -> dict:
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def save_index(index_path: Path, data: dict) -> None:
    index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cmd_init(kb_root: Path) -> int:
    index_path = ensure_kb(kb_root)
    print(json.dumps({"status": "initialized", "kb_root": str(kb_root), "index": str(index_path)}, indent=2))
    return 0


def cmd_add(kb_root: Path, category: str, title: str, tags: list[str], body: str, source: str) -> int:
    index_path = ensure_kb(kb_root)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = slugify(title)
    rel_path = f"{category}/{slug}.md"
    file_path = kb_root / rel_path

    tag_line = ", ".join(tags) if tags else "general"
    markdown = (
        f"# {title}\n\n"
        f"- **Category:** `{category}`\n"
        f"- **Updated (UTC):** {now}\n"
        f"- **Tags:** {tag_line}\n"
        f"- **Verified Source:** {source or 'Local Kali verification / manpage'}\n\n"
        f"{body.strip()}\n"
    )
    file_path.write_text(markdown, encoding="utf-8")

    data = load_index(index_path)
    entries = [e for e in data.get("entries", []) if e.get("path") != rel_path]
    entries.append(
        {
            "title": title,
            "category": category,
            "tags": tags,
            "source": source,
            "updated_utc": now,
            "path": rel_path,
        }
    )
    data["entries"] = entries
    save_index(index_path, data)
    print(json.dumps({"status": "saved", "path": str(file_path), "entry_count": len(entries)}, indent=2))
    return 0


def cmd_search(kb_root: Path, query: str) -> int:
    index_path = ensure_kb(kb_root)
    data = load_index(index_path)
    terms = [t.lower() for t in query.split() if t.strip()]
    matches: list[dict] = []

    for entry in data.get("entries", []):
        file_path = kb_root / entry["path"]
        content = file_path.read_text(encoding="utf-8", errors="replace") if file_path.is_file() else ""
        haystack = " ".join([entry.get("title", ""), " ".join(entry.get("tags", [])), content]).lower()
        score = sum(haystack.count(term) for term in terms)
        if score > 0:
            matches.append(
                {
                    "score": score,
                    "title": entry["title"],
                    "category": entry["category"],
                    "tags": entry.get("tags", []),
                    "path": str(file_path),
                    "preview": content[:260].replace("\n", " "),
                }
            )

    matches.sort(key=lambda item: item["score"], reverse=True)
    print(json.dumps({"query": query, "match_count": len(matches), "matches": matches[:10]}, indent=2))
    return 0


def cmd_list(kb_root: Path, category: str | None) -> int:
    index_path = ensure_kb(kb_root)
    data = load_index(index_path)
    entries = data.get("entries", [])
    if category:
        entries = [e for e in entries if e.get("category") == category]
    print(json.dumps({"kb_root": str(kb_root), "count": len(entries), "entries": entries}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage Cyber Command Hive Apex persistent knowledge base.")
    parser.add_argument(
        "--kb-dir",
        type=Path,
        default=Path("knowledge_base"),
        help="Path to persistent knowledge_base directory (default: ./knowledge_base).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize the knowledge_base directory and index.")

    add_p = sub.add_parser("add", help="Add or update a tool card, playbook, or fallback entry.")
    add_p.add_argument("--category", choices=CATEGORIES, required=True)
    add_p.add_argument("--title", required=True)
    add_p.add_argument("--tags", default="", help="Comma-separated tags.")
    add_p.add_argument("--source", default="", help="Verified source URL or local command reference.")
    add_p.add_argument("--body", required=True, help="Markdown body of the learned entry.")

    aar_p = sub.add_parser("aar", help="Record an After-Action Review lesson.")
    aar_p.add_argument("--case-id", required=True)
    aar_p.add_argument("--tags", default="aar,lessons-learned")
    aar_p.add_argument("--body", required=True, help="Summary of blockers, web research, and lessons learned.")

    search_p = sub.add_parser("search", help="Search saved knowledge base entries.")
    search_p.add_argument("query", help="Search keywords.")

    list_p = sub.add_parser("list", help="List saved knowledge base entries.")
    list_p.add_argument("--category", choices=CATEGORIES, default=None)

    args = parser.parse_args()
    if args.command == "init":
        return cmd_init(args.kb_dir)
    if args.command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        return cmd_add(args.kb_dir, args.category, args.title, tags, args.body, args.source)
    if args.command == "aar":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        return cmd_add(args.kb_dir, "aar", f"AAR {args.case_id}", tags, args.body, "Internal After-Action Review")
    if args.command == "search":
        return cmd_search(args.kb_dir, args.query)
    if args.command == "list":
        return cmd_list(args.kb_dir, args.category)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
