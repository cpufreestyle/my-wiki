// tests/daily_web.logic.test.mjs
// daily_web.html 标签提取逻辑单元测试（零依赖，Node 内置 node:test / node:assert）
//
// 做法：从 daily_web.html 的 <script> 中「按函数名 + 花括号配对」抽取纯函数
// extract_tags，连同其依赖的 STOP_WORDS / DOMAIN_KEYWORDS 常量，放进 vm 沙箱执行，
// 避免复制逻辑、也无需改动 HTML。运行：node --test tests/

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = join(__dirname, "..", "daily_web.html");

/** 提取 <script> 正文 */
function getScript() {
    const html = readFileSync(HTML_PATH, "utf-8");
    const m = html.match(/<script>([\s\S]*?)<\/script>/);
    if (!m) throw new Error("未找到 <script> 块");
    return m[1];
}

/** 按函数名定位并用花括号配对切出完整函数源码 */
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

/** 提取单行 `const NAME = ...;` 声明 */
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
        extractConst(script, "STOP_WORDS"),
        extractConst(script, "DOMAIN_KEYWORDS"),
        extractFunction(script, "extract_tags"),
        "this.extract_tags = extract_tags;",
    ].join("\n");
    vm.runInContext(code, sandbox);
    return sandbox;
}

test("extract_tags 返回数组且数量不超过 top_n（默认 5）", () => {
    const s = makeSandbox();
    const tags = s.extract_tags("今天去公司开会优化代码然后健身跑步游泳逛街购物");
    assert.ok(Array.isArray(tags));
    assert.ok(tags.length <= 5, `标签数应 ≤5，实际 ${tags.length}`);
});

test("extract_tags：领域关键词命中后必出现在结果中", () => {
    const s = makeSandbox();
    const tags = s.extract_tags("今天去公司开会，优化代码，感觉很顺利");
    // 注意：DOMAIN_KEYWORDS 含「优化代码」「写代码」等短语，不单独含「代码」
    for (const kw of ["公司", "开会", "优化", "优化代码"]) {
        assert.ok(tags.includes(kw), `领域关键词 ${kw} 应被提取，实际 ${tags}`);
    }
    assert.ok(!tags.includes("代码"), "「代码」非独立领域词，不应单独出现");
});

test("extract_tags：停用词（如 今天）不会被当作标签", () => {
    const s = makeSandbox();
    const tags = s.extract_tags("今天我去了公园和医院，然后回家");
    assert.ok(!tags.includes("今天"), `停用词 今天 不应出现在标签中，实际 ${tags}`);
});

test("extract_tags：纯数字被过滤，合法中英文词保留", () => {
    const s = makeSandbox();
    const tags = s.extract_tags("12345 abc 健身房 项目");
    assert.ok(!tags.includes("12345"), "纯数字应被过滤");
    // abc 是合法 3 字母词（非停用词），按桌面逻辑应保留
    assert.ok(tags.includes("abc"), "合法英文词 abc 应保留");
    assert.ok(tags.includes("健身房"), "2-4 字中文词应保留");
});

test("extract_tags：top_n 参数生效", () => {
    const s = makeSandbox();
    const long = "公司 开会 优化 代码 健身 跑步 游泳 逛街 购物 公园 医院 学校".repeat(2);
    const tags = s.extract_tags(long, 3);
    assert.equal(tags.length, 3, `top_n=3 时应恰好 3 个，实际 ${tags.length}`);
});
