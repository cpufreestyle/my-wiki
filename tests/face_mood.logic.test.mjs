// tests/face_mood.logic.test.mjs
// face_mood_web.html 情绪识别逻辑单元测试（零依赖：Node 内置 node:test / node:assert）
//
// 做法与 tests/mood_web.logic.test.mjs 一致：从 face_mood_web.html 的 module script 里
// 抽出 FACS 动作单元链路（estimateAUs / updateNeutralBaseline / subtractNeutral /
// classifyExpression / topFeatures）及其依赖常量，放进 vm 沙箱执行。
// 运行：node --test "tests/**/*.test.mjs"

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import vm from "node:vm";

const __dirname = dirname(fileURLToPath(import.meta.url));
const HTML_PATH = join(__dirname, "..", "face_mood_web.html");
const Q1 = String.fromCharCode(39);

function getScript() {
    const html = readFileSync(HTML_PATH, "utf-8");
    const m = html.match(/<script type="module">([\s\S]*?)<\/script>/);
    if (!m) throw new Error("未找到 module script 块");
    return m[1];
}

// 从 depth 0 的第一个 ; 处截断，跳过字符串与注释里的分号
function extractConst(src, name) {
    const sig = `const ${name} =`;
    const start = src.indexOf(sig);
    assert.ok(start !== -1, `未找到 const ${name}`);
    let depth = 0, i = start + sig.length, str = null;
    for (; i < src.length; i++) {
        const ch = src[i];
        if (str) {
            if (ch === "\\") i++;
            else if (ch === str) str = null;
            continue;
        }
        if (ch === '"' || ch === Q1 || ch === "`") { str = ch; continue; }
        if (ch === "/" && src[i + 1] === "/") { while (i < src.length && src[i] !== "\n") i++; continue; }
        if (ch === "{" || ch === "[" || ch === "(") depth++;
        else if (ch === "}" || ch === "]" || ch === ")") depth--;
        else if (ch === ";" && depth === 0) return src.slice(start, i + 1);
    }
    throw new Error(`const ${name} 未闭合`);
}

function extractFunction(src, name) {
    const sig = `function ${name}(`;
    const start = src.indexOf(sig);
    assert.ok(start !== -1, `未找到函数 ${name}`);
    const braceStart = src.indexOf("{", start);
    let depth = 0, i = braceStart, str = null;
    for (; i < src.length; i++) {
        const ch = src[i];
        if (str) {
            if (ch === "\\") i++;
            else if (ch === str) str = null;
            continue;
        }
        if (ch === '"' || ch === Q1 || ch === "`") { str = ch; continue; }
        if (ch === "/" && src[i + 1] === "/") { while (i < src.length && src[i] !== "\n") i++; continue; }
        if (ch === "{") depth++;
        else if (ch === "}") {
            depth--;
            if (depth === 0) return src.slice(start, i + 1);
        }
    }
    throw new Error(`函数 ${name} 花括号不配对`);
}

const CONSTS = [
    "EMOTIONS", "BLENDSHAPE_KEYS", "BLENDSHAPE_INDEX", "AU_DEFS", "AU_KEYS",
    "EMOTION_AU", "AU_ON", "REQ_PENALTY", "CLASSIFY_TEMPERATURE",
    "REQ_WEIGHT", "INH_PENALTY", "NEUTRAL_DECAY",
    "NEUTRAL_ALPHA", "NEUTRAL_QUIET", "SMOOTH_ALPHA",
];
const FNS = [
    "estimateAUs", "smoothAU", "updateNeutralBaseline", "subtractNeutral",
    "classifyExpression", "topFeatures",
];

function makeSandbox() {
    const script = getScript();
    const parts = [];
    for (const c of CONSTS) parts.push(extractConst(script, c));
    parts.push("let neutralAU = null;");
    for (const c of CONSTS) parts.push("this." + c + " = " + c + ";");
    for (const f of FNS) parts.push(extractFunction(script, f));
    parts.push("this.estimateAUs = estimateAUs;");
    parts.push("this.smoothAU = smoothAU;");
    parts.push("this.updateNeutralBaseline = updateNeutralBaseline;");
    parts.push("this.subtractNeutral = subtractNeutral;");
    parts.push("this.classifyExpression = classifyExpression;");
    parts.push("this.topFeatures = topFeatures;");
    parts.push("this.setNeutralAU = (v) => { neutralAU = v; };");
    parts.push("this.getNeutralAU = () => neutralAU;");
    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(parts.join("\n"), sandbox);
    return sandbox;
}

const S = makeSandbox();

function bs(map) {
    return { categories: Object.entries(map).map(([categoryName, score]) => ({ categoryName, score })) };
}

// 依据 Ekman/FACS 公开规则构造的各表情规范 blendshape 输入
const PROTOTYPES = {
    平静: {},
    开心: { mouthSmileLeft: 0.85, mouthSmileRight: 0.8, cheekSquintLeft: 0.6, cheekSquintRight: 0.55 },
    悲伤: { browInnerUp: 0.62, mouthFrownLeft: 0.6, mouthFrownRight: 0.55, browDownLeft: 0.35, browDownRight: 0.3, mouthShrugLower: 0.4 },
    愤怒: { browDownLeft: 0.82, browDownRight: 0.78, eyeSquintLeft: 0.7, eyeSquintRight: 0.66, eyeWideLeft: 0.45, eyeWideRight: 0.4, mouthPressLeft: 0.5, mouthPressRight: 0.48 },
    惊讶: { browInnerUp: 0.78, browOuterUpLeft: 0.85, browOuterUpRight: 0.82, eyeWideLeft: 0.9, eyeWideRight: 0.85, jawOpen: 0.75, mouthClose: 0.05 },
    恐惧: { browInnerUp: 0.7, browOuterUpLeft: 0.8, browOuterUpRight: 0.78, eyeWideLeft: 0.75, eyeWideRight: 0.72, eyeSquintLeft: 0.6, eyeSquintRight: 0.58, mouthStretchLeft: 0.6, mouthStretchRight: 0.58 },
    厌恶: { noseSneerLeft: 0.72, noseSneerRight: 0.68, mouthUpperUpLeft: 0.7, mouthUpperUpRight: 0.62, mouthShrugLower: 0.3 },
    轻蔑: { mouthSmileLeft: 0.86, mouthSmileRight: 0.1, mouthDimpleLeft: 0.62, mouthDimpleRight: 0.14 },
};

// ---------- 特征完整性 ----------
test("blendshape 覆盖 FaceLandmarker 全部 52 路输出", () => {
    assert.equal(S.BLENDSHAPE_KEYS.length, 52, "BLENDSHAPE_KEYS 应为 52 项");
    assert.ok(S.BLENDSHAPE_KEYS.includes("_neutral"), "应含 _neutral");
    for (const k of ["browOuterUpLeft", "eyeSquintLeft", "mouthUpperUpLeft",
                     "mouthDimpleLeft", "mouthFrownLeft", "jawForward"]) {
        assert.ok(S.BLENDSHAPE_KEYS.includes(k), `缺关键判别特征 ${k}`);
    }
});

test("AU 原型引用的 AU 都必须有定义", () => {
    const defined = new Set(Object.keys(S.AU_DEFS));
    for (const [emo, p] of Object.entries(S.EMOTION_AU)) {
        for (const k of [...p.req, ...p.sup]) {
            assert.ok(defined.has(k), `${emo} 引用了未定义的 AU: ${k}`);
        }
    }
});

test("EMOTIONS 与 EMOTION_AU 键集一致", () => {
    const a = new Set(S.EMOTIONS);
    const b = new Set(Object.keys(S.EMOTION_AU));
    assert.deepEqual([...a].sort(), [...b].sort(), "两个集合必须一致");
});

// ---------- estimateAUs ----------
test("estimateAUs: max / mean / lipsPart / asym 四种折算", () => {
    const au = S.estimateAUs(bs({
        browOuterUpLeft: 0.9, browOuterUpRight: 0.2,
        mouthSmileLeft: 0.8, mouthSmileRight: 0.4,
        jawOpen: 0.8, mouthClose: 0.5,
    }));
    assert.ok(Math.abs(au.AU2 - 0.9) < 1e-9, `AU2 应为 0.9，实际 ${au.AU2}`);
    assert.ok(Math.abs(au.AU12 - 0.6) < 1e-9, `AU12 应为 0.6，实际 ${au.AU12}`);
    assert.ok(Math.abs(au.AU25 - 0.475) < 1e-9, `AU25 应为 0.475，实际 ${au.AU25}`);
    assert.ok(Math.abs(au.AU26 - 0.8) < 1e-9, `AU26 应为 0.8，实际 ${au.AU26}`);
    assert.ok(au.AU12asym > 0.3, `AU12asym 应 >0.3，实际 ${au.AU12asym}`);
});

test("estimateAUs: 对称微笑不判单侧上扬", () => {
    const au = S.estimateAUs(bs({ mouthSmileLeft: 0.9, mouthSmileRight: 0.88 }));
    assert.ok(au.AU12asym < 0.05, `两侧几乎相等时单侧上扬应接近 0，实际 ${au.AU12asym}`);
});

test("estimateAUs: 空输入不抛异常", () => {
    const au = S.estimateAUs(bs({}));
    for (const k of S.AU_KEYS) assert.ok(au[k] >= 0 && au[k] <= 1);
    assert.equal(au.peak, 0);
});

// ---------- 表情原型识别 ----------
for (const [emo, spec] of Object.entries(PROTOTYPES)) {
    test(`规范 ${emo} 表情应被识别为 ${emo}`, () => {
        const au = S.estimateAUs(bs(spec));
        const r = S.classifyExpression(au);
        assert.equal(r.label, emo, `应判为 ${emo}，实际 ${r.label}（scores: ${JSON.stringify(r.scores)}）`);
        assert.ok(r.confidence > 0.5, `${emo} 置信度应 >0.5，实际 ${r.confidence}`);
    });
}

test("概率分布归一且与 EMOTIONS 等长", () => {
    const r = S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.愤怒)));
    assert.equal(r.probs.length, S.EMOTIONS.length);
    const sum = r.probs.reduce((a, b) => a + b, 0);
    assert.ok(Math.abs(sum - 1) < 1e-9, `概率和应为 1，实际 ${sum}`);
});

// ---------- 必需 AU 的判别力（旧线性加权做不到的部分） ----------
test("缺必需 AU 的情绪不成立：只扬嘴角不判悲伤/愤怒", () => {
    const au = S.estimateAUs(bs({ mouthSmileLeft: 0.8, mouthSmileRight: 0.78 }));
    const r = S.classifyExpression(au);
    assert.equal(r.label, "开心", `应判为开心，实际 ${r.label}`);
});

test("惊讶与恐惧必须分开：AU7 把惊讶翻成恐惧", () => {
    assert.equal(S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.惊讶))).label, "惊讶");
    const fear = S.estimateAUs(bs({ ...PROTOTYPES.惊讶, eyeSquintLeft: 0.62, eyeSquintRight: 0.6 }));
    assert.equal(S.classifyExpression(fear).label, "恐惧",
        "惊讶的 AU 组合 + AU7 应翻到恐惧（AU7 恐惧必需、惊讶不要）");
});

test("厌恶与愤怒必须分开", () => {
    assert.equal(S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.厌恶))).label, "厌恶");
    assert.equal(S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.愤怒))).label, "愤怒");
});

test("单侧上扬走轻蔑、对称上扬走开心", () => {
    assert.equal(S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.轻蔑))).label, "轻蔑");
    assert.equal(S.classifyExpression(S.estimateAUs(bs(PROTOTYPES.开心))).label, "开心");
});

// ---------- 中性脸基准（换人不失效） ----------
test("中性脸基准：天生皱眉的人静止时不应被判成愤怒", () => {
    const resting = S.estimateAUs(bs({ browDownLeft: 0.42, browDownRight: 0.4, eyeSquintLeft: 0.3, eyeSquintRight: 0.28 }));
    S.setNeutralAU(resting);
    const angry = S.estimateAUs(bs({ browDownLeft: 0.85, browDownRight: 0.82, eyeSquintLeft: 0.72, eyeSquintRight: 0.7 }));
    assert.equal(S.classifyExpression(angry).label, "愤怒", "有基准后仍应识别动怒");
    const calm = S.estimateAUs(bs({ browDownLeft: 0.43, browDownRight: 0.41, eyeSquintLeft: 0.3, eyeSquintRight: 0.29 }));
    assert.notEqual(S.classifyExpression(calm).label, "愤怒", "静止眉位不应被判成愤怒");
    S.setNeutralAU(null);
});

test("updateNeutralBaseline 只学安静帧", () => {
    S.setNeutralAU(null);
    S.updateNeutralBaseline(S.estimateAUs(bs({ browDownLeft: 0.1, browDownRight: 0.1 })));
    const first = S.getNeutralAU();
    assert.ok(first, "安静帧应建立基准");
    assert.ok(first.AU4 > 0, "基准应记录 AU4");
    const before = S.getNeutralAU().AU4;
    S.updateNeutralBaseline(S.estimateAUs(bs({ browDownLeft: 0.9, browDownRight: 0.9 })));
    assert.ok(Math.abs(S.getNeutralAU().AU4 - before) < 1e-9, "表情帧不得改动基准");
    S.setNeutralAU(null);
});

// ---------- 可解释性 ----------
test("topFeatures 只回报达到阈值的 AU 并带中文标签", () => {
    const f = S.topFeatures(S.estimateAUs(bs(PROTOTYPES.愤怒)));
    const keys = Object.keys(f);
    assert.ok(keys.length > 0, "应有 AU 达到阈值");
    for (const k of keys) assert.ok(k.includes("("), `应带中文标签: ${k}`);
    assert.ok(keys.some((k) => k.startsWith("AU4")), "愤怒应回报 AU4");
    assert.ok(keys.some((k) => k.startsWith("AU7")), "愤怒应回报 AU7");
});

// ---------- EMA 平滑：peak 必须保留（生产路径回归） ----------
// 生产路径是 estimateAUs → smoothAU(EMA) → classifyExpression。
// 若 EMA 后 peak 丢失，classifyExpression 里「平静」分 = 1 - NEUTRAL_DECAY * 0 = 1.0，
// 所有表情都会塌缩成平静；而只把 estimateAUs 的输出喂给 classifyExpression 的用例
// 完全看不见这个 bug（那正是此前的盲区）。
test("smoothAU 必须重算 peak（否则平静恒 1.0、表情塌缩）", () => {
    const raw = S.estimateAUs(bs(PROTOTYPES.开心));
    assert.ok(raw.peak > 0, "estimateAUs 应给出 peak");

    // 首次（prev 为空）
    let sm = S.smoothAU(null, raw, S.SMOOTH_ALPHA);
    assert.ok(typeof sm.peak === "number", "smoothAU 必须产出 peak");
    assert.ok(sm.peak > 0, "首次平滑后 peak 应 > 0");

    // 连续多帧平滑，peak 不得丢失
    for (let i = 0; i < 12; i++) sm = S.smoothAU(sm, raw, S.SMOOTH_ALPHA);
    assert.ok(sm.peak > 0, "多帧平滑后 peak 仍应 > 0");
    assert.ok(Math.abs(sm.peak - raw.peak) < 0.05, "收敛后 peak 应接近原始 peak");
});

test("生产路径（EMA 后）不应把强表情判成平静", () => {
    for (const [emo, spec] of Object.entries(PROTOTYPES)) {
        if (emo === "平静") continue;
        const raw = S.estimateAUs(bs(spec));
        let sm = S.smoothAU(null, raw, S.SMOOTH_ALPHA);
        for (let i = 0; i < 10; i++) sm = S.smoothAU(sm, raw, S.SMOOTH_ALPHA);
        const r = S.classifyExpression(sm);
        assert.notEqual(r.label, "平静", `${emo} 经 EMA 后不应判为平静（peak=${sm.peak}）`);
    }
});

