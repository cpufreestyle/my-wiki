#!/usr/bin/env python3
"""
rag.py — MyWiki 语义检索 (Semantic RAG)

为 MyWiki 提供真正的语义检索能力，替代原本的子串文本匹配：

  - 默认 BM25 模式：纯标准库实现，零额外依赖，开箱即用。
    中文采用字符级 bigram 分词（经典无词典方案），英文按词切分，
    具备一定的语义近似能力。
  - 可选 Ollama 本地 embedding 模式：若本机运行了 Ollama 且装有
    nomic-embed-text 等嵌入模型，自动升级为向量语义检索，效果更好且
    完全离线、隐私友好。

用法:
  python rag.py "查询语句"                 # 语义搜索 top-10
  python rag.py "查询" --limit 5
  python rag.py "查询" --mode ollama       # 强制使用本地 embedding
  python rag.py --rebuild                  # 强制重建向量/统计缓存

也可作为模块:
  from rag import RAGEngine
  eng = RAGEngine()
  eng.index()
  hits = eng.search("如何配置本地模型")
"""
import os
import re
import sys
import json
import math
import hashlib
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def find_wiki_root() -> Path:
    """智能定位 wiki 根目录。"""
    env = os.environ.get("MYWIKI_ROOT")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).resolve().parent
    if (here / "daily").exists() or (here / "README.md").exists():
        return here
    alt = here / "wiki"
    if alt.exists():
        return alt
    return here


WIKI_ROOT = find_wiki_root()
CATEGORIES = ["daily", "projects", "concepts", "people", "brain"]
SKIP_DIRS = {".obsidian", ".git", "__pycache__", "node_modules", "attachments", ".trash"}
CACHE_PATH = WIKI_ROOT / "wiki" / ".rag_index.json"
OLLAMA_URL = os.environ.get("MYWIKI_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("MYWIKI_EMBED_MODEL", "nomic-embed-text")


# ---------------------------------------------------------------------------
# 分词 (中英文混合)
# ---------------------------------------------------------------------------

def tokenize(text: str):
    """中英混合分词：英文/数字按词，中文按字符 bigram。"""
    text = (text or "").lower()
    tokens = []
    # 英文 / 数字词（长度 > 1 才有区分度）
    for m in re.findall(r"[a-z0-9]+", text):
        if len(m) > 1:
            tokens.append(m)
    # 中文连续段 -> 字符 bigram
    for seg in re.findall(r"[一-鿿]+", text):
        if len(seg) == 1:
            tokens.append("c:" + seg)
        else:
            for i in range(len(seg) - 1):
                tokens.append("c:" + seg[i:i + 2])
    return tokens


def cosine(a, b):
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


# ---------------------------------------------------------------------------
# 分块
# ---------------------------------------------------------------------------

def chunk_text(text: str, max_chars: int = 600):
    """按段落 / 标题切分为语义块，便于精准召回。"""
    lines = text.splitlines()
    blocks, cur, cur_len = [], [], 0
    for ln in lines:
        cur.append(ln)
        cur_len += len(ln) + 1
        # 在空行或标题处断块，控制块大小
        if cur_len >= max_chars and (ln.strip() == "" or ln.startswith("#")):
            joined = "\n".join(cur).strip()
            if joined:
                blocks.append(joined)
            cur, cur_len = [], 0
    if cur:
        joined = "\n".join(cur).strip()
        if joined:
            blocks.append(joined)
    return [b for b in blocks if len(b) > 20]


# ---------------------------------------------------------------------------
# 语义检索引擎
# ---------------------------------------------------------------------------

class RAGEngine:
    def __init__(self, wiki_root=None, mode=None):
        self.root = Path(wiki_root) if wiki_root else WIKI_ROOT
        self.cache_path = self.root / "wiki" / ".rag_index.json"
        self.mode = mode or self._detect_mode()
        self.blocks = []
        self.N = 0
        self.df = {}
        self.avgdl = 0.0
        self.cache = self._load_cache()

    # --- 配置 / 缓存 ---
    def _detect_mode(self):
        env = os.environ.get("MYWIKI_RAG_MODE")
        if env in ("ollama", "bm25"):
            return env
        return "bm25"

    def _load_cache(self):
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False), encoding="utf-8"
        )

    # --- 收集与分块 ---
    def _collect_blocks(self):
        blocks = []
        for cat in CATEGORIES:
            root = self.root / cat
            if not root.exists():
                continue
            for f in root.rglob("*.md"):
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.name in ("INDEX.md", "README.md"):
                    continue
                rel = f.relative_to(self.root).as_posix()
                try:
                    text = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                # 去掉 YAML frontmatter 噪声，只索引正文
                m = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.DOTALL)
                body = text[m.end():] if m else text
                title = f.stem.replace("_", " ")
                for b in chunk_text(body):
                    blocks.append({
                        "rel": rel,
                        "title": title,
                        "text": b,
                        "mtime": f.stat().st_mtime,
                    })
        return blocks

    # --- 索引 ---
    def index(self, force=False):
        self.blocks = self._collect_blocks()
        # BM25 预处理
        for b in self.blocks:
            toks = tokenize(b["text"])
            tf = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            b["tf"] = tf
            b["dl"] = len(toks)
        self.N = len(self.blocks)
        df = {}
        for b in self.blocks:
            for t in b["tf"]:
                df[t] = df.get(t, 0) + 1
        self.df = df
        self.avgdl = (sum(b["dl"] for b in self.blocks) / self.N) if self.N else 0
        # 可选 embedding
        if self.mode == "ollama":
            self._embed_blocks(force=force)
        return self

    def _embed_blocks(self, force=False):
        emb_cache = self.cache.setdefault("embeddings", {})
        pending = []  # (block_index, text)
        for i, b in enumerate(self.blocks):
            key = b["rel"] + "|" + hashlib.md5(b["text"].encode()).hexdigest()[:12]
            b["_key"] = key
            if not force and key in emb_cache:
                b["_emb"] = emb_cache[key]
            else:
                pending.append((i, b["text"]))
        if not pending:
            return
        try:
            import requests
            batch = [t for _, t in pending]
            resp = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": batch},
                timeout=180,
            )
            resp.raise_for_status()
            embs = resp.json().get("embeddings", [])
            for (i, _), e in zip(pending, embs):
                key = self.blocks[i]["_key"]
                emb_cache[key] = e
                self.blocks[i]["_emb"] = e
            self.cache["mode"] = "ollama"
            self._save_cache()
        except Exception as e:
            print(f"[WARN] Ollama embedding 失败，回退 BM25: {e}", file=sys.stderr)
            self.mode = "bm25"

    # --- 查询 ---
    def search(self, query, limit=10):
        if not self.blocks:
            self.index()
        if self.mode == "ollama" and all("_emb" in b for b in self.blocks):
            return self._search_embedding(query, limit)
        return self._search_bm25(tokenize(query), limit)

    def _search_bm25(self, q_tokens, limit):
        k1, b = 1.5, 0.75
        scored = []
        for blk in self.blocks:
            score = 0.0
            for qt in set(q_tokens):
                tf = blk["tf"].get(qt)
                if not tf:
                    continue
                df_t = self.df.get(qt, 0)
                idf = math.log((self.N - df_t + 0.5) / (df_t + 0.5) + 1)
                score += idf * (tf * (k1 + 1)) / (
                    tf + k1 * (1 - b + b * blk["dl"] / self.avgdl)
                )
            if score > 0:
                scored.append((score, blk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return self._format(scored[:limit])

    def _search_embedding(self, query, limit):
        import requests
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": [query]},
            timeout=60,
        )
        resp.raise_for_status()
        q_emb = resp.json()["embeddings"][0]
        scored = []
        for blk in self.blocks:
            if "_emb" not in blk:
                continue
            sim = cosine(q_emb, blk["_emb"])
            if sim > 0:
                scored.append((sim, blk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return self._format(scored[:limit])

    def _format(self, scored):
        out = []
        for score, blk in scored:
            text = blk["text"]
            snippet = text[:160].replace("\n", " ").strip()
            if len(text) > 160:
                snippet += "..."
            out.append({
                "rel": blk["rel"],
                "title": blk["title"],
                "score": round(score, 4),
                "snippet": snippet,
            })
        return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="MyWiki 语义检索")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--mode", choices=["bm25", "ollama"], default=None)
    ap.add_argument("--rebuild", action="store_true", help="强制重建缓存")
    args = ap.parse_args()

    eng = RAGEngine(mode=args.mode)
    if args.rebuild:
        eng.index(force=True)
    if not args.query:
        print("用法: python rag.py \"查询语句\" [--mode ollama] [--limit 5]")
        return
    hits = eng.search(args.query, args.limit)
    if not hits:
        print("[NOT FOUND] 未找到语义相关的内容")
        return
    print(json.dumps(hits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
