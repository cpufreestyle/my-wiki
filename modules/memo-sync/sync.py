#!/usr/bin/env python3
"""
Memo Sync - OpenClaw ↔ Memo (MemoAI) 双向联动

将 OpenClaw workspace 的分析报告/日记/笔记推送到本地 Memo 应用，
以及从 Memo 拉取笔记内容到 OpenClaw workspace。

Memo 数据存储：
  - SQLite: ~/Library/Application Support/Memo/storage/local.db
  - 文件:   ~/Library/Application Support/Memo/temp/memo/<workspace-uuid>/
  - 表:     doc (title, content, localFilename, workspaceId)
            note (transcript, summary, filePath)
            tag, doc_tag, folder

Usage:
    python3 memo_sync.py push <markdown_file> [--title "标题"]
    python3 memo_sync.py push-dir <directory> [--pattern "*.md"]
    python3 memo_sync.py pull [--limit 10]
    python3 memo_sync.py list [--limit 20]
    python3 memo_sync.py search <keyword>
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime

# Memo paths
MEMO_DATA = Path.home() / "Library" / "Application Support" / "Memo"
MEMO_DB = MEMO_DATA / "storage" / "local.db"
MEMO_TEMP = MEMO_DATA / "temp" / "memo"

# OpenClaw workspace
WORKSPACE = Path.home() / ".qclaw" / "workspace"


def get_db():
    """Connect to Memo's SQLite database."""
    if not MEMO_DB.exists():
        print(f"❌ Memo database not found: {MEMO_DB}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(MEMO_DB))
    conn.row_factory = sqlite3.Row
    return conn


def get_workspace_uuid(conn):
    """Get the default workspace UUID and ID."""
    cur = conn.execute("SELECT id, uuid, folder FROM workspace LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("❌ No workspace found in Memo", file=sys.stderr)
        sys.exit(1)
    return row["id"], row["uuid"], row["folder"]


def push_to_memo(markdown_path, title=None):
    """Push a markdown file to Memo as a doc."""
    md_file = Path(markdown_path).expanduser()
    if not md_file.exists():
        print(f"❌ File not found: {md_file}", file=sys.stderr)
        return False

    content = md_file.read_text(encoding="utf-8")
    doc_title = title or md_file.stem

    conn = get_db()
    ws_id, ws_uuid, ws_folder = get_workspace_uuid(conn)

    # Generate a unique local filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_filename = f"openclaw_{timestamp}_{md_file.stem}"

    # Also save the file to Memo's workspace directory
    ws_dir = Path(ws_folder)
    docs_dir = ws_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    doc_file = docs_dir / f"{local_filename}.md"
    doc_file.write_text(content, encoding="utf-8")

    # Insert into doc table
    # content field is varchar(255) - use it for description, not full content
    description = content[:200].replace("\n", " ") + "..." if len(content) > 200 else content[:200]

    conn.execute(
        """INSERT INTO doc (title, localFilename, workspaceId, description, content, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (doc_title, local_filename, ws_id, description, doc_file.name,
         datetime.now().isoformat(timespec="seconds"),
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()

    print(f"✅ Pushed to Memo: {doc_title}")
    print(f"   File: {doc_file}")
    print(f"   DB:   doc table (workspaceId={ws_id})")
    return True


def push_dir(directory, pattern="*.md"):
    """Push all matching files from a directory to Memo."""
    dir_path = Path(directory).expanduser()
    if not dir_path.is_dir():
        print(f"❌ Directory not found: {dir_path}", file=sys.stderr)
        return

    files = sorted(dir_path.glob(pattern))
    if not files:
        print(f"⚠️  No files matching '{pattern}' in {dir_path}")
        return

    count = 0
    for f in files:
        if push_to_memo(f):
            count += 1
    print(f"\n📊 Pushed {count}/{len(files)} files to Memo")


def pull_from_memo(limit=10, output_dir=None):
    """Pull docs from Memo to OpenClaw workspace."""
    conn = get_db()
    cur = conn.execute(
        "SELECT d.id, d.title, d.localFilename, d.content, d.description, d.created_at "
        "FROM doc d ORDER BY d.created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()

    if not rows:
        print("📭 Memo has no docs yet")
        conn.close()
        return

    out_dir = Path(output_dir) if output_dir else WORKSPACE / "memo-pulled"
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for row in rows:
        # Try to read the full content from the file
        ws_id, ws_uuid, ws_folder = get_workspace_uuid(conn)
        doc_file = (Path(ws_folder) / "docs" / row["content"]) if row["content"] else None

        if doc_file and doc_file.exists():
            content = doc_file.read_text(encoding="utf-8")
        else:
            content = row["description"] or "(no content)"

        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in row["title"])
        out_file = out_dir / f"{safe_title}_{row['id']}.md"
        out_file.write_text(
            f"# {row['title']}\n\n"
            f"> Pulled from Memo | Created: {row['created_at']}\n\n"
            f"{content}\n",
            encoding="utf-8"
        )
        print(f"  📄 {row['title']} → {out_file}")
        count += 1

    conn.close()
    print(f"\n📊 Pulled {count} docs from Memo → {out_dir}")


def list_memo_docs(limit=20):
    """List docs in Memo."""
    conn = get_db()
    cur = conn.execute(
        "SELECT d.id, d.title, d.description, d.created_at, "
        "       (SELECT count(*) FROM note n WHERE n.workspaceId = d.workspaceId) as note_count "
        "FROM doc d ORDER BY d.created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()

    if not rows:
        print("📭 Memo has no docs")
    else:
        print(f"📚 Memo Docs ({len(rows)}):\n")
        for r in rows:
            desc = (r["description"] or "")[:60]
            print(f"  [{r['id']}] {r['title']}")
            print(f"      {desc}...")
            print(f"      Created: {r['created_at']}")
            print()

    # Also list notes
    cur = conn.execute(
        "SELECT id, ogFilename, status, substr(summary, 1, 80) as summary_preview, created_at "
        "FROM note ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    notes = cur.fetchall()
    if notes:
        print(f"🎤 Memo Notes ({len(notes)}):\n")
        for n in notes:
            print(f"  [{n['id']}] {n['ogFilename'] or '(unnamed)'} [{n['status']}]")
            if n["summary_preview"]:
                print(f"      Summary: {n['summary_preview']}...")
            print(f"      Created: {n['created_at']}")
            print()

    conn.close()


def search_memo(keyword):
    """Search docs and notes in Memo."""
    conn = get_db()
    kw = f"%{keyword}%"

    print(f"🔍 Searching Memo for: '{keyword}'\n")

    # Search docs
    cur = conn.execute(
        "SELECT id, title, description, created_at FROM doc WHERE title LIKE ? OR description LIKE ?",
        (kw, kw)
    )
    docs = cur.fetchall()
    if docs:
        print(f"📄 Docs ({len(docs)}):")
        for d in docs:
            print(f"  [{d['id']}] {d['title']} ({d['created_at']})")
    else:
        print("📄 Docs: no matches")

    # Search notes
    cur = conn.execute(
        "SELECT id, ogFilename, substr(summary, 1, 100) as s FROM note WHERE ogFilename LIKE ? OR summary LIKE ?",
        (kw, kw)
    )
    notes = cur.fetchall()
    if notes:
        print(f"\n🎤 Notes ({len(notes)}):")
        for n in notes:
            print(f"  [{n['id']}] {n['ogFilename']}")
            if n["s"]:
                print(f"      {n['s']}")
    else:
        print("\n🎤 Notes: no matches")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="OpenClaw ↔ Memo Sync")
    sub = parser.add_subparsers(dest="command")

    # push
    p_push = sub.add_parser("push", help="Push a markdown file to Memo")
    p_push.add_argument("file", help="Path to markdown file")
    p_push.add_argument("--title", help="Document title (default: filename)")

    # push-dir
    p_pushdir = sub.add_parser("push-dir", help="Push all matching files from directory")
    p_pushdir.add_argument("directory", help="Directory path")
    p_pushdir.add_argument("--pattern", default="*.md", help="Glob pattern (default: *.md)")

    # pull
    p_pull = sub.add_parser("pull", help="Pull docs from Memo to workspace")
    p_pull.add_argument("--limit", type=int, default=10)
    p_pull.add_argument("--output-dir", default=None)

    # list
    p_list = sub.add_parser("list", help="List docs in Memo")
    p_list.add_argument("--limit", type=int, default=20)

    # search
    p_search = sub.add_parser("search", help="Search Memo content")
    p_search.add_argument("keyword")

    args = parser.parse_args()

    if args.command == "push":
        push_to_memo(args.file, args.title)
    elif args.command == "push-dir":
        push_dir(args.directory, args.pattern)
    elif args.command == "pull":
        pull_from_memo(args.limit, args.output_dir)
    elif args.command == "list":
        list_memo_docs(args.limit)
    elif args.command == "search":
        search_memo(args.keyword)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
