#!/usr/bin/env python3
"""llm_qa.py — MyWiki 本地 LLM 问答（检索增强生成，RAG + Generate）

design:
  先用 rag.RAGEngine 在知识库里召回相关片段，再把片段作为上下文交给本地
  Ollama 模型生成中文答案，同时返回引用来源，保证答案可回溯、不凭空编造。

关键约束：
  - 完全离线：只走本机 Ollama（默认 http://localhost:11434），数据不出机器。
  - 优雅降级：Ollama 不可用时返回 ``available=False``，由调用方退回纯检索结果，
    而不是抛出 500。
  - 思考模型兼容：Qwen3.5 等模型默认会先输出长篇 thinking，需要显式
    ``"think": false`` 才会返回正式回答，否则 response 恒为空字符串。

用法::

    python llm_qa.py "如何配置本地模型"
    python llm_qa.py "..." --model Qwen3.5-4B --limit 5 --json

作为模块::

    from llm_qa import answer
    result = answer("我的知识库里有哪些项目")
"""
import json
import os
import sys

OLLAMA_URL = os.environ.get("MYWIKI_OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("MYWIKI_LLM_MODEL", "Qwen3.5-4B")
DEFAULT_TIMEOUT = float(os.environ.get("MYWIKI_LLM_TIMEOUT", "120"))

# 上下文长度上限（字符）。模型上下文有限，超出会截断最不相关的片段。
MAX_CONTEXT_CHARS = int(os.environ.get("MYWIKI_LLM_CONTEXT_CHARS", "6000"))

_SYSTEM_PROMPT = (
    "你是 MyWiki 个人知识库的助手。请严格依据下面提供的【知识库片段】回答用户问题。\n"
    "要求：\n"
    "1. 只使用片段中的信息；片段没有提到的内容，直接说明“知识库中没有相关信息”，不要编造。\n"
    "2. 用简体中文回答，简洁直接，优先分点说明。\n"
    "3. 回答中如需引用，用 [1] [2] 标注对应片段编号。\n"
)


def _build_context(hits, max_chars=MAX_CONTEXT_CHARS):
    """把检索命中的片段编号并拼成上下文，超出预算时截断尾部的片段。"""
    parts = []
    used = 0
    kept = 0
    for i, h in enumerate(hits, 1):
        block = "[{}] 来源: {}\n{}".format(i, h.get("rel", ""), h.get("snippet", ""))
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
        kept += 1
    return "\n\n".join(parts), kept


def ollama_available(timeout=2.0):
    """探测本机 Ollama 是否可达（轻量 GET /api/tags）。"""
    try:
        import requests
        resp = requests.get(OLLAMA_URL + "/api/tags", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def generate(prompt, model=None, timeout=None, system=None):
    """调用本地 Ollama 生成文本，返回 (text, error)。

    失败时返回 (None, 错误描述)，绝不抛异常，便于上层优雅降级。
    """
    try:
        import requests
    except Exception:
        return None, "缺少 requests 依赖"
    payload = {
        "model": model or DEFAULT_MODEL,
        "prompt": prompt,
        "system": system or _SYSTEM_PROMPT,
        "stream": False,
        # 思考型模型（Qwen3.5 等）不关掉思考时 response 恒为空
        "think": False,
        "options": {"num_predict": int(os.environ.get("MYWIKI_LLM_MAX_TOKENS", "700"))},
    }
    try:
        resp = requests.post(
            OLLAMA_URL + "/api/generate", json=payload,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        if not text:
            return None, "模型返回空内容"
        return text, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def retrieve(query, limit=6):
    """复用 rag.RAGEngine 召回相关片段，返回 (hits, error)。"""
    try:
        from rag import RAGEngine
    except Exception as e:  # noqa: BLE001
        return [], "rag 模块不可用: {}".format(e)
    try:
        eng = RAGEngine()
        eng.index()
        return eng.search(query, limit), None
    except Exception as e:  # noqa: BLE001
        return [], "检索失败: {}".format(e)


def answer(query, limit=6, model=None, timeout=None):
    """检索增强问答：先召回知识库片段，再让本地 LLM 基于片段作答。

    返回字典::

        {
          "ok": bool,               # 是否拿到了 LLM 答案
          "query": str,
          "answer": str | None,     # LLM 答案；不可用时为 None
          "mode": "llm" | "retrieval-only",
          "model": str,             # 实际使用的模型
          "sources": [{"index", "rel", "title", "score", "snippet"}],
          "error": str | None,      # 降级原因说明
        }

    Ollama 不可用时仍会返回检索结果（mode="retrieval-only"），保证功能不中断。
    """
    query = (query or "").strip()
    if not query:
        return {"ok": False, "query": "", "answer": None, "mode": "retrieval-only",
                "model": model or DEFAULT_MODEL, "sources": [], "error": "问题为空"}

    hits, retr_err = retrieve(query, limit)
    sources = [
        {
            "index": i,
            "rel": h.get("rel", ""),
            "title": h.get("title", ""),
            "score": h.get("score"),
            "snippet": h.get("snippet", ""),
        }
        for i, h in enumerate(hits, 1)
    ]

    base = {
        "query": query,
        "sources": sources,
        "model": model or DEFAULT_MODEL,
    }
    if retr_err:
        return dict(base, ok=False, answer=None, mode="retrieval-only", error=retr_err)
    if not hits:
        return dict(base, ok=True, answer="知识库中没有找到与「{}」相关的内容。".format(query),
                    mode="retrieval-only", error=None)

    if not ollama_available():
        return dict(base, ok=True, answer=None, mode="retrieval-only",
                    error="本地 Ollama 不可用，已回退为纯检索结果")

    context, kept = _build_context(hits)
    prompt = (
        "【知识库片段】\n{}\n\n【用户问题】\n{}\n\n请依据上述片段回答："
        .format(context, query)
    )
    text, gen_err = generate(prompt, model=model, timeout=timeout)
    if gen_err:
        return dict(base, ok=True, answer=None, mode="retrieval-only",
                    error="LLM 生成失败，已回退为纯检索结果：{}".format(gen_err))
    return dict(base, ok=True, answer=text, mode="llm", error=None)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="MyWiki 本地 LLM 问答（RAG + Ollama）")
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    if not args.query:
        print("用法: python llm_qa.py \"你的问题\" [--model Qwen3.5-4B] [--limit 5]")
        return
    result = answer(args.query, limit=args.limit, model=args.model)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if result.get("answer"):
        print(result["answer"])
        print("\n--- 引用来源 ---")
        for s in result.get("sources", [])[:5]:
            print("[{}] {} ({})".format(s["index"], s["title"], s["rel"]))
    else:
        print("[检索结果] {}".format(result.get("error") or "无答案"))
        for s in result.get("sources", []):
            print("- {} | {}".format(s["title"], s["snippet"][:80]))


if __name__ == "__main__":
    main()
