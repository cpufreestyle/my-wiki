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

def _resolve_vault_path(repo_root) -> "Path | None":
    """若 config/obsidian.json 配置了 vault_path 且存在，则返回该 Obsidian vault 作为数据根。"""
    cfg = Path(repo_root) / "config" / "obsidian.json"
    if cfg.exists():
        try:
            import json
            vp = json.loads(cfg.read_text(encoding="utf-8")).get("vault_path", "")
            if vp and Path(vp).expanduser().is_dir():
                return Path(vp).expanduser()
        except Exception:
            pass
    return None


def _canonical_wiki_root(here: Path) -> "Path | None":
    """复用 wiki_paths 的统一解析（与桌面端 / 网页端同一套），不可用时返回 None。"""
    try:
        from wiki_paths import _resolve_wiki_dir
        return Path(_resolve_wiki_dir(str(here)))
    except Exception:
        return None


def _looks_like_wiki(p: Path) -> bool:
    """粗判目录是否为 wiki 根（含 INDEX.md / daily / README.md 之一）。"""
    return (p / "INDEX.md").exists() or (p / "daily").exists() or (p / "README.md").exists()


def find_wiki_root() -> Path:
    """智能定位 wiki 根目录。

    优先级: 环境变量 MYWIKI_ROOT > config/obsidian.json 的 vault_path (Obsidian vault) > 仓库根。
    统一复用 wiki_paths 的解析，仅在结果不像 wiki 目录时回退原有启发式。
    """
    here = Path(__file__).resolve().parent  # rag.py 位于仓库根
    canon = _canonical_wiki_root(here)
    if canon is not None and _looks_like_wiki(canon):
        return canon
    # 兜底：统一解析不可用、或其结果不像 wiki 目录时，沿用原有启发式
    env = os.environ.get("MYWIKI_ROOT")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    vp = _resolve_vault_path(here)
    if vp:
        return vp
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

# 单批嵌入条数上限：整库一次性提交会让 Ollama runner 连接重置（400）
EMBED_BATCH = 32

# RRF 融合常数：越大越弱化 top-1 的优势，让两路结果更均衡
RRF_K = 60
# 单篇笔记在融合结果里最多出现的片段数，避免一篇占满结果页
MAX_CHUNKS_PER_DOC = 2


def _ollama_has_embed_model(timeout=1.5):
    """探测本机 Ollama 是否可用且装有 EMBED_MODEL 对应的嵌入模型。

    只做一次轻量 GET /api/tags。名字比对忽略 ":latest" 这类 tag 差异。
    任何异常都当作不可用，绝不抛出，保证纯离线环境下仍留在 BM25。
    """
    try:
        import requests
        resp = requests.get(OLLAMA_URL + "/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return False
        names = [m.get("name", "") for m in (resp.json().get("models") or [])]
        want = EMBED_MODEL.split(":")[0]
        return any(n.split(":")[0] == want for n in names)
    except Exception:
        return False


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
    """按段落 / 标题切分为语义块，便于精准召回。

    断块时机：累计长度已达上限且当前行处于段落边界（空行或标题）时切断；
    若始终遇不到边界（整篇无空行/标题），则在超出 2 倍上限时强制切断，
    避免出现数千字的巨型块——块越大，嵌入向量越“平均”，检索越不精准。
    """
    lines = text.splitlines()
    blocks, cur, cur_len = [], [], 0

    def flush():
        joined = "\n".join(cur).strip()
        if joined:
            blocks.append(joined)

    for ln in lines:
        at_boundary = ln.strip() == "" or ln.startswith("#")
        # 到上限后遇到任意段落边界就切；一直没有边界则到 2 倍上限强切
        if cur and ((cur_len >= max_chars and at_boundary) or cur_len >= max_chars * 2):
            flush()
            cur, cur_len = [], 0
            if ln.strip() == "":
                continue
        cur.append(ln)
        cur_len += len(ln) + 1

    if cur:
        flush()
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
        # 未显式指定时自动探测：装了本地嵌入模型就用向量语义检索，
        # 否则留在零依赖的 BM25。此前恒为 "bm25"，装了 Ollama 也用不上。
        return "ollama" if _ollama_has_embed_model() else "bm25"

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

    def _iter_source_files(self):
        """遍历知识库 .md，按规范路径去重后返回 [(canonical_rel, rel, path)]。

        两处去重：
        1. brain/ 下的分类目录（brain/daily/、brain/projects/…）与顶层同名
           目录存放的是同一批文档的副本；
        2. macOS 大小写不敏感文件系统上，同一篇笔记可能存在仅大小写不同
           的两个文件名（LLM_Wiki.md / llm_wiki.md）。

        不去重会让同一篇笔记被索引多次，top-k 里出现多条分数完全相同的
        重复项，白白占掉名额。规范路径取小写并去掉开头的 "brain/"；
        冲突时优先保留顶层版本，其次按路径字典序取其一。
        """
        chosen = {}
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
                canon = rel[len("brain/"):] if rel.startswith("brain/") else rel
                key = canon.lower()
                prev = chosen.get(key)
                if prev is None:
                    chosen[key] = (canon, rel, f)
                    continue
                prev_rel = prev[1]
                prev_in_brain = prev_rel.startswith("brain/")
                cur_in_brain = rel.startswith("brain/")
                if prev_in_brain and not cur_in_brain:
                    chosen[key] = (canon, rel, f)
                elif prev_in_brain == cur_in_brain and canon < prev[0]:
                    chosen[key] = (canon, rel, f)
        return sorted(chosen.values(), key=lambda x: x[0])

    def _corpus_signature(self):
        """知识库内容签名：所有 .md 的 (canonical_rel, mtime) 排序后取 md5。

        只 stat 不读文件内容，成本远低于全量重读 + 重分词。
        """
        items = []
        for canon, _rel, f in self._iter_source_files():
            try:
                items.append((canon, f.stat().st_mtime))
            except OSError:
                continue
        items.sort()
        h = hashlib.md5()
        for rel, mt in items:
            h.update("{}:{}\n".format(rel, mt).encode("utf-8"))
        return h.hexdigest()


    def _restore_bm25(self, cached):
        """从缓存恢复 BM25 预处理结果（跳过读文件与分词）。"""
        self.blocks = cached.get("blocks") or []
        self.N = cached.get("N", len(self.blocks))
        self.df = cached.get("df", {}) or {}
        self.avgdl = cached.get("avgdl", 0.0) or 0.0

    def _save_bm25(self, sig):
        """把 BM25 预处理结果落盘，避免每次冷启动全量重读 + 重分词。"""
        try:
            self.cache["bm25"] = {
                "sig": sig,
                "N": self.N,
                "df": self.df,
                "avgdl": self.avgdl,
                "blocks": [
                    {
                        "rel": b.get("rel"),
                        "title": b.get("title"),
                        "text": b.get("text"),
                        "tf": b.get("tf", {}),
                        "dl": b.get("dl", 0),
                        "mtime": b.get("mtime"),
                    }
                    for b in self.blocks
                ],
            }
            self._save_cache()
        except Exception:
            pass  # 缓存写失败不影响检索正确性

    # --- 收集与分块 ---
    def _collect_blocks(self):
        blocks = []
        for canon, _rel, f in self._iter_source_files():
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
                    "rel": canon,
                    "title": title,
                    "text": b,
                    "mtime": f.stat().st_mtime,
                })
        return blocks


    def index(self, force=False):
        # 语料未变化时直接复用上次的 BM25 预处理结果（跳过全量读文件与分词）。
        # 此前每次冷启动都要重新读完整个知识库并重新分词。
        sig = self._corpus_signature()
        cached = self.cache.get("bm25") if isinstance(self.cache, dict) else None
        if not force and cached and cached.get("sig") == sig and cached.get("blocks"):
            self._restore_bm25(cached)
            if self.mode == "ollama":
                self._embed_blocks(force=force)
            return self
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
        self._save_bm25(sig)
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

        def embed_batch(texts):
            """向 Ollama 请求一批嵌入，返回向量列表；失败抛异常。"""
            import requests
            resp = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": texts},
                timeout=180,
            )
            resp.raise_for_status()
            return resp.json().get("embeddings", [])

        # 一次性把整库塞进单个请求会让 Ollama runner 连接重置（400），
        # 于是按小批重试：单批失败只丢该批，其余批仍拿到向量。
        done = 0
        for start in range(0, len(pending), EMBED_BATCH):
            chunk = pending[start:start + EMBED_BATCH]
            try:
                embs = embed_batch([t for _, t in chunk])
            except Exception as e:  # noqa: BLE001
                print(
                    f"[WARN] 嵌入批次 {start}-{start + len(chunk)} 失败，"
                    f"该批退回 BM25: {e}",
                    file=sys.stderr,
                )
                continue
            for (i, _), e in zip(chunk, embs):
                key = self.blocks[i]["_key"]
                emb_cache[key] = e
                self.blocks[i]["_emb"] = e
                done += 1
            self._save_cache()

        if done == 0:
            # 一条都没向量化成功：整库退回 BM25，保证检索仍可用
            print("[WARN] Ollama embedding 全部失败，回退 BM25", file=sys.stderr)
            self.mode = "bm25"
        elif done < len(pending):
            print(
                f"[WARN] 仅有 {done}/{len(pending)} 片段完成向量化，"
                f"其余由 BM25 补齐",
                file=sys.stderr,
            )
        else:
            self.cache["mode"] = "ollama"
            self._save_cache()

    # --- 查询 ---
    def search(self, query, limit=10):
        """混合检索：向量语义 + BM25 字面，用 RRF 融合排序。

        单用向量时存在 hubness——个别块（如标签密集的日记开头）对任何查询
        都给出高分，稳定占据 top-1；单用 BM25 则只认字面重合，换个说法就
        召回不到。RRF 只看排序名次、不看原始分数，天然免疫两者量纲差异，
        任一路召回不到的文档不会拖累另一路的名次。
        """
        if not self.blocks:
            self.index()
        q_tokens = tokenize(query)
        bm25_hits = self._search_bm25(q_tokens, limit * 3)

        emb_hits = None
        if self.mode == "ollama":
            embedded = [b for b in self.blocks if "_emb" in b]
            if embedded:
                # 查询向量化失败（Ollama 挂了/超时）时返回 None，整库退回 BM25
                emb_hits = self._search_embedding(query, limit * 3)

        if not emb_hits:
            return bm25_hits[:limit]
        return self._rrf_merge([emb_hits, bm25_hits], limit)

    @staticmethod
    def _rrf_merge(rankings, limit, k=RRF_K):
        """Reciprocal Rank Fusion：按名次倒数累加，避免分数不可比。

        以 (rel, snippet) 而非 rel 为融合键。同一篇笔记的多个片段各自计入
        名次——若按 rel 折叠，BM25 里命中 6 个片段的文档只能拿到 1 次贡献，
        反而被另一路只命中 1 个片段、但排在首位的文档压过去。
        同一片段被两路同时召回时贡献累加，这正是"两路都认为相关"的信号。
        """
        fused = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                key = (hit["rel"], hit["snippet"])
                prev = fused.get(key)
                contrib = 1.0 / (k + rank)
                if prev is None:
                    item = dict(hit)
                    item["score"] = contrib
                    fused[key] = item
                else:
                    prev["score"] += contrib
        ordered = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        out = []
        per_doc = {}
        for item in ordered:
            # 同一篇笔记最多保留 2 个片段，避免一篇占满整个结果页
            cnt = per_doc.get(item["rel"], 0)
            if cnt >= MAX_CHUNKS_PER_DOC:
                continue
            per_doc[item["rel"]] = cnt + 1
            item["score"] = round(item["score"], 4)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def _search_bm25(self, q_tokens, limit):
        k1, b = 1.5, 0.75
        # 去重一次 + 预计算 idf：此前在每个 block 内都重建 set(q_tokens)
        # 并对每个 token 重算一次 math.log，属于 O(blocks × tokens) 的重复计算。
        q_set = set(q_tokens)
        idf = {}
        for qt in q_set:
            df_t = self.df.get(qt, 0)
            idf[qt] = math.log((self.N - df_t + 0.5) / (df_t + 0.5) + 1)
        avgdl = self.avgdl
        scored = []
        for blk in self.blocks:
            tf_map = blk["tf"]
            # 同一 block 内 dl 固定，分母中这部分是常量，提到内层循环外
            denom_base = k1 * (1 - b + b * blk["dl"] / avgdl) if avgdl else k1
            score = 0.0
            for qt in q_set:
                tf = tf_map.get(qt)
                if not tf:
                    continue
                score += idf[qt] * (tf * (k1 + 1)) / (tf + denom_base)
            if score > 0:
                scored.append((score, blk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return self._format(scored[:limit])

    def _search_embedding(self, query, limit):
        """向量检索。查询向量化失败时返回 None（由调用方退回 BM25），

        避免 Ollama 中途挂掉时整库检索返回空结果。
        """
        try:
            import requests
            resp = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": [query]},
                timeout=60,
            )
            resp.raise_for_status()
            q_emb = resp.json()["embeddings"][0]
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] 查询向量化失败，退回 BM25: {e}", file=sys.stderr)
            return None
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
