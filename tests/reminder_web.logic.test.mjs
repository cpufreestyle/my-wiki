// tests/reminder_web.logic.test.mjs
// reminder_web.html 纯日期逻辑单元测试（零依赖，使用 Node 内置 node:test / node:assert）
//
// 做法：从 reminder_web.html 的 <script> 中「按函数名 + 花括号配对」抽取纯函数
// getPresetTime / computeRemindAt，放进 vm 沙箱执行，避免复制逻辑、也无需改动 HTML。
// 运行：node --test tests/

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = join(__dirname, "..", "reminder_web.html");

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

// 构建沙箱：注入两个纯函数 + 可变的 currentHours / currentKey 上下文
function makeSandbox() {
    const script = getScript();
    const sandbox = { currentHours: null, currentKey: null, Date, Math, result: null };
    vm.createContext(sandbox);
    const code =
        extractFunction(script, "getPresetTime") +
        "\n" +
        extractFunction(script, "computeRemindAt") +
        "\n" +
        "this.getPresetTime = getPresetTime; this.computeRemindAt = computeRemindAt;";
    vm.runInContext(code, sandbox);
    return sandbox;
}

test("getPresetTime('tomorrow_9') 返回明天 09:00", () => {
    const s = makeSandbox();
    const d = s.getPresetTime("tomorrow_9");
    const now = new Date();
    const expectedDay = new Date(now);
    expectedDay.setDate(now.getDate() + 1);
    assert.equal(d.getDate(), expectedDay.getDate());
    assert.equal(d.getHours(), 9);
    assert.equal(d.getMinutes(), 0);
    assert.equal(d.getSeconds(), 0);
    assert.ok(d.getTime() > now.getTime(), "应为将来时间");
});

test("getPresetTime('tomorrow_18') 返回明天 18:00", () => {
    const s = makeSandbox();
    const d = s.getPresetTime("tomorrow_18");
    assert.equal(d.getHours(), 18);
    assert.equal(d.getMinutes(), 0);
});

test("getPresetTime('nextweek_9') 在未来一周内且为 09:00", () => {
    const s = makeSandbox();
    const d = s.getPresetTime("nextweek_9");
    const now = new Date();
    assert.equal(d.getHours(), 9);
    assert.equal(d.getMinutes(), 0);
    assert.ok(d.getTime() > now.getTime(), "应为将来时间");
    const days = (d.getTime() - now.getTime()) / 86400000;
    assert.ok(days <= 7 + 1, `应在约一周内, 实际 ${days.toFixed(1)} 天`);
});

test("computeRemindAt: currentHours=2 时约为 now + 2 小时", () => {
    const s = makeSandbox();
    s.currentHours = 2;
    s.currentKey = null;
    const before = Date.now();
    const d = s.computeRemindAt();
    const diffMin = (d.getTime() - before) / 60000;
    assert.ok(Math.abs(diffMin - 120) < 1, `期望约 120 分钟, 实际 ${diffMin.toFixed(2)}`);
});

test("computeRemindAt: 无 hours 时走 key 分支并与 getPresetTime 一致", () => {
    const s = makeSandbox();
    s.currentHours = null;
    s.currentKey = "tomorrow_9";
    const a = s.computeRemindAt();
    const b = s.getPresetTime("tomorrow_9");
    // 同一秒内生成，允许 2 秒误差
    assert.ok(Math.abs(a.getTime() - b.getTime()) < 2000);
    assert.equal(a.getHours(), 9);
});
