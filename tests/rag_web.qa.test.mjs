import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "..", "rag_web.html"), "utf8");

// 取出页面内联脚本，做静态契约检查（不启动浏览器）
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const js = scripts.join("\n");

test("rag_web.html: 内联脚本语法可解析", () => {
  assert.ok(scripts.length > 0, "应存在内联脚本");
  for (const s of scripts) {
    assert.doesNotThrow(() => new Function(s), "内联脚本应能被解析");
  }
});

test("rag_web.html: 提供检索/问答双模式切换按钮", () => {
  assert.match(html, /id="modeSearch"/, "应有检索模式按钮");
  assert.match(html, /id="modeAsk"/, "应有问题模式按钮");
  assert.match(js, /function setMode/, "应有模式切换函数");
});

test("rag_web.html: 问答走 POST /api/qa 且带 query", () => {
  assert.match(js, /api\/qa/, "应请求 /api/qa");
  assert.match(js, /method:\s*"POST"/, "应用 POST");
  assert.match(js, /JSON\.stringify\(\{\s*query/, "请求体应含 query");
});

test("rag_web.html: 问答结果区分 llm 与降级模式", () => {
  assert.match(js, /data\.mode === "llm"/, "应判断 mode");
  assert.match(js, /retrieval-only|检索模式/, "应处理降级展示");
});

test("rag_web.html: 答案区域与引用来源容器存在", () => {
  assert.match(html, /id="answerWrap"/, "应有答案容器");
  assert.match(js, /renderSources/, "应渲染引用来源");
});

test("rag_web.html: 搜索与回车均按当前模式分发", () => {
  assert.match(js, /if \(mode === "ask"\) \{ doAsk\(v\); \} else \{ doSearch\(v\); \}/);
});
