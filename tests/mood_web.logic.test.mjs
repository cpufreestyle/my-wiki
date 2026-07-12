// tests/mood_web.logic.test.mjs
// mood_web.html 心情分析逻辑单元测试（零依赖，Node 内置 node:test / node:assert）
//
// 做法：从 mood_web.html 的 <script> 中抽出纯函数 analyze_mood 及其依赖的
// MOOD_KEYWORDS / NEGATION_WORDS 常量，放进 vm 沙箱执行。运行：node --test tests/

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = join(__dirname, "..", "mood_web.html");

function getScript() {
    const html = readFileSync(HTML_PATH, "utf-8");
    const m = html.match(/<script>([\s\S]*?)<\/script>/);
    if (!m) throw new Error("未找到 <script> 块");
    return m[1];
}

function extractFunction(src, name) {
    const sig = `function ${name}`;
    const start = src.indexOf(sig);
    assert.ok(start !== -1, `未找到函数 ${name}`);
    const braceStart = src.indexOf("{", start);
    let depth = 0;
    for (let i = braceStart; i < src.length; i++) {
        const ch = src[i];
        if (ch === "{") depth++;
        else if (ch === "}") {
            depth--;
            if (depth === 0) return src.slice(start, i + 1);
        }
    }
    throw new Error(`函数 ${name} 花括号不配对`);
}

function extractConst(src, name) {
    const sig = `const ${name} =`;
    const start = src.indexOf(sig);
    assert.ok(start !== -1, `未找到 const ${name}`);
    const end = src.indexOf(";", start);
    return src.slice(start, end + 1);
}

function makeSandbox() {
    const script = getScript();
    const sandbox = {};
    vm.createContext(sandbox);
    const code = [
        extractConst(script, "MOOD_KEYWORDS"),
        extractConst(script, "NEGATION_WORDS"),
        extractFunction(script, "analyze_mood"),
        "this.analyze_mood = analyze_mood;",
    ].join("\n");
    vm.runInContext(code, sandbox);
    return sandbox;
}

test("analyze_mood：含开心/顺利关键词 → 返回 开心", () => {
    const s = makeSandbox();
    const [mood, conf] = s.analyze_mood("我今天很开心，顺利完成了工作");
    assert.equal(mood, "开心");
    assert.ok(conf > 0, "置信度应 > 0");
});

test("analyze_mood：否定词（不开心）不计入开心", () => {
    const s = makeSandbox();
    const [mood] = s.analyze_mood("我今天不开心，有点郁闷");
    assert.notEqual(mood, "开心", "否定语境下不应判定为开心");
});

test("analyze_mood：中性文本 → 返回 平静 + 0.5", () => {
    const s = makeSandbox();
    const [mood, conf, reason] = s.analyze_mood("刚刚吃了一碗面");
    assert.equal(mood, "平静");
    assert.equal(conf, 0.5);
    assert.equal(reason, "no obvious mood");
});

test("analyze_mood：多关键词提升置信度（≥0.5）", () => {
    const s = makeSandbox();
    const [, conf] = s.analyze_mood("好开心好高兴好快乐，今天太顺利了");
    assert.ok(conf >= 0.5, `多命中应提升置信度，实际 ${conf}`);
});

test("analyze_mood：返回三元组结构稳定", () => {
    const s = makeSandbox();
    const r = s.analyze_mood("有点焦虑，压力好大");
    assert.equal(r.length, 3);
    assert.equal(r[0], "焦虑");
});
