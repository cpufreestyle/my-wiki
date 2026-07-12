/*
 * voice-controller.js — MyWiki 网页语音录音共享模块
 *
 * 设计要点：
 *  1. 麦克风流 / AudioContext / AnalyserNode 整个会话只获取一次，
 *     权限仅在首次点击「语音」时弹一次；之后复用，不再反复请求授权。
 *  2. 停止录音时只停止采样定时器，不释放麦克风，直到页面卸载（beforeunload）
 *     才真正关闭，从根本上避免「第二次录不进去」的问题。
 *  3. 通过回调 onResult(text, acousticsMood) 适配不同页面：
 *      - 心情页：识别文字 + 声学分析 → 心情判断
 *      - 日记页：识别文字 → 追加到正文（不做心情判断）
 *
 * 用法：
 *   new VoiceController({ buttonId, statusId, targetInputId, onResult });
 */
(function (global) {
    "use strict";

    const SpeechRec = global.SpeechRecognition || global.webkitSpeechRecognition;

    class VoiceController {
        constructor(opts) {
            opts = opts || {};
            this.buttonId = opts.buttonId || "voiceBtn";
            this.statusId = opts.statusId || "voiceStatus";
            this.targetInputId = opts.targetInputId || null;  // 识别文字追加到该 textarea 的 id
            this.onResult = typeof opts.onResult === "function" ? opts.onResult : function () {};

            this.recognizer = null;
            this.recognizing = false;
            // 会话级复用状态
            this.micStream = null;
            this.audioCtx = null;
            this.analyser = null;
            this.sourceNode = null;
            this.micReady = false;
            this.micInitPromise = null;       // 防止并发重复 getUserMedia
            this.acousticsData = null;         // 本次录音的声学特征
            this.acousticsTimer = null;

            this._bind();
        }

        _btn() { return document.getElementById(this.buttonId); }
        _status() { return document.getElementById(this.statusId); }

        _toast(msg) {
            if (typeof global.toast === "function") { global.toast(msg); return; }
            const el = document.getElementById("toast");
            if (el) {
                el.textContent = msg;
                el.classList.add("show");
                clearTimeout(el._t);
                el._t = setTimeout(() => el.classList.remove("show"), 2400);
            }
        }

        _bind() {
            const btn = this._btn();
            if (btn) {
                btn.addEventListener("click", () => {
                    if (this.recognizing) { if (this.recognizer) this.recognizer.stop(); return; }
                    this.start();
                });
            }
            // 页面卸载时真正释放麦克风流与 AudioContext（会话期间一直复用）
            global.addEventListener("beforeunload", () => this._release());
        }

        // ---- 一次性获取麦克风并构建音频图；成功后整个会话复用 ----
        async ensureMic() {
            if (this.micReady) return true;
            if (this.micInitPromise) return this.micInitPromise;   // 防止并发重复 getUserMedia
            this.micInitPromise = (async () => {
                if (!global.navigator || !global.navigator.mediaDevices || !global.navigator.mediaDevices.getUserMedia) return false;
                try {
                    this.micStream = await global.navigator.mediaDevices.getUserMedia({ audio: true });
                    const AC = global.AudioContext || global.webkitAudioContext;
                    this.audioCtx = new AC();
                    if (this.audioCtx.state === "suspended") { try { await this.audioCtx.resume(); } catch (e) {} }
                    this.sourceNode = this.audioCtx.createMediaStreamSource(this.micStream);
                    this.analyser = this.audioCtx.createAnalyser();
                    this.analyser.fftSize = 2048;
                    this.sourceNode.connect(this.analyser);
                    this.micReady = true;
                    return true;
                } catch (e) {
                    // 授权被拒 / 无设备：重置，便于用户后续在浏览器设置允许后重试
                    this.micReady = false; this.micInitPromise = null;
                    this.micStream = null; this.audioCtx = null; this.analyser = null; this.sourceNode = null;
                    return false;
                }
            })();
            return this.micInitPromise;
        }

        // ---- 开始声学采样（复用已获取的麦克风流，不再重新请求权限） ----
        startAcoustics() {
            if (!this.micReady || !this.analyser) return false;
            if (this.audioCtx.state === "suspended") { try { this.audioCtx.resume(); } catch (e) {} }
            this.acousticsData = { energies: [], pitches: [], voiced: 0, frames: 0 };
            const bufLen = this.analyser.frequencyBinCount;
            const freqData = new Uint8Array(bufLen);
            const timeData = new Uint8Array(this.analyser.fftSize);
            if (this.acousticsTimer) clearInterval(this.acousticsTimer);
            this.acousticsTimer = setInterval(() => {
                if (!this.analyser) return;
                this.analyser.getByteTimeDomainData(timeData);
                this.analyser.getByteFrequencyData(freqData);
                // RMS 能量
                let sumSq = 0;
                for (let i = 0; i < timeData.length; i++) {
                    const v = (timeData[i] - 128) / 128;
                    sumSq += v * v;
                }
                const rms = Math.sqrt(sumSq / timeData.length);
                this.acousticsData.energies.push(rms);
                // 过零率（近似音高）
                let zc = 0;
                for (let i = 1; i < timeData.length; i++) {
                    if ((timeData[i - 1] >= 128) !== (timeData[i] >= 128)) zc++;
                }
                this.acousticsData.pitches.push(zc / timeData.length);
                if (rms > 0.02) this.acousticsData.voiced++;
                this.acousticsData.frames++;
            }, 50);
            return true;
        }

        // ---- 仅停止采样定时器；麦克风流与 AudioContext 在会话中复用 ----
        stopAcoustics() {
            if (this.acousticsTimer) { clearInterval(this.acousticsTimer); this.acousticsTimer = null; }
        }

        getAcousticsResult() {
            if (!this.acousticsData || this.acousticsData.frames === 0) return null;
            const es = this.acousticsData.energies;
            const ps = this.acousticsData.pitches;
            const avg = (a) => a.reduce((s, v) => s + v, 0) / a.length;
            const std = (a, m) => Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / a.length);
            const energy = avg(es);
            const energyStd = std(es, energy);
            const pitch = avg(ps);
            const pitchStd = std(ps, pitch);
            const duration = this.acousticsData.frames * 0.05;
            const rate = this.acousticsData.voiced / duration;
            return { energy, energy_std: energyStd, pitch_zcr: pitch, pitch_std: pitchStd, speech_rate: rate, voiced: this.acousticsData.voiced, duration };
        }

        // ---- 由声学特征推断情绪（与桌面版一致） ----
        acousticsToMood(f) {
            if (!f) return null;
            if (f.voiced < 3) return { mood: "平静", conf: 0.1, detail: "声音太短" };
            const s = { "开心": 0, "平静": 0, "低落": 0, "兴奋": 0, "焦虑": 0 };
            const d = [];
            if (f.energy > 0.08) { s["兴奋"] += 2; s["开心"] += 1; d.push("音量较高"); }
            else if (f.energy > 0.03) { s["开心"] += 1; s["焦虑"] += 1; d.push("音量适中"); }
            else if (f.energy > 0.01) { s["平静"] += 1; d.push("音量较低"); }
            else { s["低落"] += 2; d.push("声音很轻"); }
            if (f.energy_std > 0.05) { s["兴奋"] += 1; s["焦虑"] += 1; d.push("音量波动大"); }
            else if (f.energy_std < 0.01) { s["平静"] += 1; s["低落"] += 1; d.push("音量稳定"); }
            if (f.pitch_zcr > 0.15) { s["兴奋"] += 1; s["焦虑"] += 1; d.push("音调偏高"); }
            else if (f.pitch_zcr < 0.06) { s["低落"] += 1; s["平静"] += 1; d.push("音调偏低"); }
            else { s["开心"] += 1; d.push("音调适中"); }
            if (f.pitch_std > 0.05) { s["兴奋"] += 1; s["开心"] += 1; d.push("语调起伏丰富"); }
            else if (f.pitch_std < 0.01) { s["平静"] += 1; s["低落"] += 1; d.push("语调平缓"); }
            if (f.speech_rate > 8) { s["焦虑"] += 1; s["兴奋"] += 1; d.push("语速较快"); }
            else if (f.speech_rate < 2) { s["低落"] += 1; s["平静"] += 1; d.push("语速较慢"); }
            let best = "平静", bestV = -1;
            for (const m in s) { if (s[m] > bestV) { bestV = s[m]; best = m; } }
            if (bestV === 0) return { mood: "平静", conf: 0.1, detail: "声学特征不明显" };
            return { mood: best, conf: Math.min(bestV / 6, 0.5), detail: d.join("、") };
        }

        _appendText(txt) {
            if (!this.targetInputId || !txt) return;
            const ta = document.getElementById(this.targetInputId);
            if (!ta) return;
            const cur = (ta.value || "").trim();
            ta.value = cur ? cur + "\n" + txt : txt;
        }

        // ---- 把识别结果交给页面回调 ----
        _dispatch(txt, acou) {
            if (txt) this._appendText(txt);
            this.stopAcoustics();
            this.onResult(txt, acou);
        }

        _initRecognizer() {
            if (!SpeechRec) return null;
            const rec = new SpeechRec();
            rec.lang = "zh-CN";
            rec.continuous = false;
            rec.interimResults = false;
            rec.maxAlternatives = 1;
            rec.onresult = (ev) => {
                let txt = "";
                try { txt = ev.results[0][0].transcript || ""; } catch (e) {}
                const acou = this.acousticsToMood(this.getAcousticsResult());
                this._dispatch(txt, acou);
            };
            rec.onerror = (ev) => {
                let msg = (ev && ev.error) || "未知错误";
                if (msg === "not-allowed" || msg === "service-not-allowed")
                    msg = "麦克风权限被拒绝，请在浏览器设置中允许";
                else if (msg === "no-speech")
                    msg = "没听到声音，请再试一次";
                else if (msg === "network")
                    msg = "网络错误，语音识别需要联网";
                // 文字识别失败时，仍可用声学特征分析
                const acou = this.acousticsToMood(this.getAcousticsResult());
                if (acou && acou.voiced >= 3) {
                    this._dispatch(null, acou);
                } else {
                    const st = this._status();
                    if (st) st.textContent = "识别失败：" + msg;
                    this._toast(msg);
                }
                this._stopUI();
            };
            rec.onend = () => this._stopUI();
            return rec;
        }

        async start() {
            if (!SpeechRec) {
                this._toast("当前浏览器不支持语音识别（请用 Chrome 访问）");
                return;
            }
            // 复用已创建的 recognizer，避免重复弹授权
            if (!this.recognizer) this.recognizer = this._initRecognizer();
            if (!this.recognizer) return;
            // 获取麦克风（仅首次会弹一次授权，之后整个会话复用）
            const micOk = await this.ensureMic();
            if (micOk) {
                this.startAcoustics();
            } else {
                const st = this._status();
                if (st) st.textContent = "（声音分析不可用，仅文字识别）";
            }
            try {
                this.recognizer.start();
                this.recognizing = true;
                this._setUI(true);
            } catch (e) {
                // 若 start 失败（上一次尚未完全停止），稍后重试
                setTimeout(() => {
                    try { this.recognizer.start(); this.recognizing = true; this._setUI(true); }
                    catch (e) { this._toast("无法启动麦克风，请重试"); }
                }, 300);
            }
        }

        _stopUI() {
            this.recognizing = false;
            this._setUI(false);
            // 延迟停止声学采样，让最后一个结果（含声学特征）能返回
            setTimeout(() => this.stopAcoustics(), 400);
        }

        _setUI(on) {
            const btn = this._btn();
            if (btn) {
                btn.classList.toggle("recording", on);
                btn.textContent = on ? "⏹ 停止" : "🎤 语音";
            }
            const st = this._status();
            if (st && on) st.textContent = "正在聆听…";
        }

        _release() {
            if (this.micStream) { this.micStream.getTracks().forEach((t) => t.stop()); this.micStream = null; }
            if (this.audioCtx) { try { this.audioCtx.close(); } catch (e) {} this.audioCtx = null; }
            this.analyser = null; this.sourceNode = null; this.micReady = false;
        }
    }

    global.VoiceController = VoiceController;
})(window);
