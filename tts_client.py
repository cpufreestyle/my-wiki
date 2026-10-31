#!/usr/bin/env python3
"""tts_client.py — 三级 TTS 后端：Gemini → StepFun → macOS say

默认顺序合成一段文本并播放，任何一级失败都自动降级到下一级：

1. gemini   Google Gemini TTS（--no-style 等价：只发正文，避免模型把语气提示念出来）
2. stepfun  阶跃星辰 /v1/audio/speech（Step Plan 会员把 base 换成 step_plan 路径即可）
3. say      macOS 内置语音，离线兜底

密钥只从环境变量读取（`GEMINI_API_KEY` / `STEPFUN_API_KEY`），也兼容
`~/.workbuddy/gemini_tts/config.json`（可用 `GEMINI_TTS_CONFIG` 指向别处）。
本模块只写临时音频目录，不触碰 brain/ daily/ wiki/ 用户内容。

常用环境变量：
    MYWIKI_TTS_PROVIDERS   逗号分隔，覆盖默认顺序，如 "stepfun,say"
    MYWIKI_TTS_OUT_DIR     音频输出目录（默认系统临时目录/mywiki_tts）
    GEMINI_TTS_MODEL      默认 gemini-3.8-flash-tts
    GEMINI_TTS_VOICE      默认 algenib
    GEMINI_TTS_BASE_URL   默认 https://generativelanguage.googleapis.com/v1beta
    GEMINI_TTS_PROXY      走本地代理时才需要（也可用标准 HTTPS_PROXY）
    STEPFUN_TTS_MODEL     默认 step-tts-mini
    STEPFUN_TTS_VOICE     默认 wenrounvsheng
    STEPFUN_TTS_BASE_URL  默认 https://api.stepfun.com/v1；会员可设为
                          https://api.stepfun.com/step_plan/v1
    MYWIKI_SAY_VOICE      默认 Tingting
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import ProxyHandler, Request, build_opener

DEFAULT_PROVIDERS = ("gemini", "stepfun", "say")
GEMINI_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash-tts"
GEMINI_DEFAULT_VOICE = "algenib"
STEPFUN_DEFAULT_BASE = "https://api.stepfun.com/v1"
STEPFUN_DEFAULT_MODEL = "step-tts-mini"
STEPFUN_DEFAULT_VOICE = "wenrounvsheng"
SAY_DEFAULT_VOICE = "Tingting"
GEMINI_CONFIG_PATH = Path.home() / ".workbuddy" / "gemini_tts" / "config.json"
TIMEOUT = 60.0


class TTSError(RuntimeError):
    """任一后端合成失败；消息里不得包含 API key。"""


@dataclass(frozen=True)
class TTSResult:
    provider: str
    path: str


def _log(message):
    print("[TTS] " + message, file=sys.stderr)


def _sanitize(message, secret):
    """错误消息会进日志/异常链，先把密钥抹掉。"""
    return message.replace(secret, "***") if secret else message


def _gemini_conf():
    """环境变量优先，其次读取 WorkBuddy 的 Gemini TTS 配置（只读）。"""
    stored = {}
    path = Path(os.environ.get("GEMINI_TTS_CONFIG") or GEMINI_CONFIG_PATH).expanduser()
    try:
        if path.is_file():
            stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    return {
        "key": os.environ.get("GEMINI_API_KEY") or stored.get("api_key") or "",
        "base": os.environ.get("GEMINI_TTS_BASE_URL") or GEMINI_DEFAULT_BASE,
        "model": os.environ.get("GEMINI_TTS_MODEL") or stored.get("model")
        or GEMINI_DEFAULT_MODEL,
        "voice": os.environ.get("GEMINI_TTS_VOICE") or stored.get("default_voice")
        or GEMINI_DEFAULT_VOICE,
        "proxy": os.environ.get("GEMINI_TTS_PROXY") or stored.get("proxy") or "",
    }


def _stepfun_conf():
    return {
        "key": os.environ.get("STEPFUN_API_KEY") or "",
        "base": os.environ.get("STEPFUN_TTS_BASE_URL") or STEPFUN_DEFAULT_BASE,
        "model": os.environ.get("STEPFUN_TTS_MODEL") or STEPFUN_DEFAULT_MODEL,
        "voice": os.environ.get("STEPFUN_TTS_VOICE") or STEPFUN_DEFAULT_VOICE,
    }


def _post(url, payload, headers, proxy=None, timeout=TIMEOUT):
    """POST 并返回 (content_type, body)。异常只保留状态码与响应片段。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST")
    if proxy:
        opener = build_opener(ProxyHandler({"http": proxy, "https": proxy}))
    else:
        opener = build_opener()
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.headers.get("Content-Type", ""), response.read()
    except HTTPError as exc:
        snippet = exc.read()[:200].decode("utf-8", "replace")
        raise TTSError("HTTP {}: {}".format(exc.code, snippet)) from None
    except URLError as exc:
        raise TTSError("网络错误: {}".format(exc.reason)) from None


def _pcm_rate(mime_type):
    match = re.search(r"rate=(\d+)", mime_type or "")
    return int(match.group(1)) if match else 24000


def _wrap_wav(raw, rate=24000, ch=1, bits=16):
    """把裸 PCM 包成 WAV；已经是 RIFF 的原样返回。"""
    if raw[:4] == b"RIFF":
        return raw
    size = len(raw)
    return (b"RIFF" + (36 + size).to_bytes(4, "little") + b"WAVEfmt " +
            (16).to_bytes(4, "little") +
            (1).to_bytes(2, "little") + ch.to_bytes(2, "little") +
            rate.to_bytes(4, "little") +
            (rate * ch * bits // 8).to_bytes(4, "little") +
            (ch * bits // 8).to_bytes(2, "little") +
            bits.to_bytes(2, "little") + b"data" +
            size.to_bytes(4, "little") + raw)


def _out_path(out_dir, suffix):
    directory = Path(out_dir or os.environ.get("MYWIKI_TTS_OUT_DIR")
                     or (Path(tempfile.gettempdir()) / "mywiki_tts"))
    directory.mkdir(parents=True, exist_ok=True)
    name = "tts-{}-{}{}".format(int(time.time()), uuid.uuid4().hex[:8], suffix)
    return directory / name


def _gemini_synthesize(text, out_dir):
    conf = _gemini_conf()
    if not conf["key"]:
        raise TTSError("未配置 GEMINI_API_KEY")
    url = "{}/models/{}:generateContent".format(
        conf["base"].rstrip("/"), quote(conf["model"], safe=""))
    payload = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voice_config": {
                "prebuilt_voice_config": {"voice_name": conf["voice"]}}},
        },
    }
    try:
        _content_type, raw = _post(
            url, payload,
            {"Content-Type": "application/json", "X-Goog-Api-Key": conf["key"]},
            conf["proxy"] or None)
    except TTSError as exc:
        raise TTSError(_sanitize("Gemini: {}".format(exc), conf["key"])) from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise TTSError("Gemini 返回了非 JSON 内容") from None
    for part in ((data.get("candidates") or [{}])[0].get("content", {}).get("parts") or []):
        inline = part.get("inlineData") or part.get("inline_data") or {}
        encoded = inline.get("data")
        if encoded:
            audio = base64.b64decode(encoded)
            audio = _wrap_wav(audio, rate=_pcm_rate(inline.get("mimeType")))
            path = _out_path(out_dir, ".wav")
            path.write_bytes(audio)
            return path
    raise TTSError("Gemini 未返回音频: {}".format(str(data)[:200]))


def _stepfun_synthesize(text, out_dir):
    conf = _stepfun_conf()
    if not conf["key"]:
        raise TTSError("未配置 STEPFUN_API_KEY")
    url = conf["base"].rstrip("/") + "/audio/speech"
    payload = {
        "model": conf["model"],
        "input": text,
        "voice": conf["voice"],
        "response_format": "wav",
    }
    headers = {"Authorization": "Bearer " + conf["key"],
               "Content-Type": "application/json"}
    try:
        content_type, raw = _post(url, payload, headers)
    except TTSError as exc:
        raise TTSError(_sanitize("StepFun: {}".format(exc), conf["key"])) from None
    if "application/json" in (content_type or "").lower() or raw[:1] == b"{":
        raise TTSError(_sanitize(
            "StepFun 返回错误: {}".format(raw[:200].decode("utf-8", "replace")),
            conf["key"]))
    path = _out_path(out_dir, ".wav")
    path.write_bytes(raw)
    return path


def _run_say(text, out_path, voice=None):
    """用 `say -f` 从临时文件读文本，避免正文以 '-' 开头被当成选项。"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(text)
        text_file = handle.name
    try:
        command = ["say", "-f", text_file, "-o", str(out_path)]
        if voice:
            command += ["-v", voice]
        subprocess.run(command, check=True, capture_output=True, timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError) as exc:
        raise TTSError("say 合成失败: {}".format(exc)) from None
    finally:
        try:
            os.unlink(text_file)
        except OSError:
            pass


def _say_synthesize(text, out_dir):
    path = _out_path(out_dir, ".aiff")
    _run_say(text, path, os.environ.get("MYWIKI_SAY_VOICE") or SAY_DEFAULT_VOICE)
    if not path.is_file() or path.stat().st_size == 0:
        raise TTSError("say 未生成音频")
    return path


_SYNTHESIZERS = {
    "gemini": _gemini_synthesize,
    "stepfun": _stepfun_synthesize,
    "say": _say_synthesize,
}


def _default_providers():
    configured = os.environ.get("MYWIKI_TTS_PROVIDERS")
    if not configured:
        return DEFAULT_PROVIDERS
    return tuple(name.strip() for name in configured.split(",") if name.strip())


def synthesize(text, provider, out_dir=None):
    """只用指定后端合成，返回音频路径；失败抛 TTSError。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("待合成文本为空")
    try:
        return _SYNTHESIZERS[provider](text, out_dir)
    except KeyError:
        raise TTSError("未知 TTS 后端: {}".format(provider)) from None


def play_audio(path):
    """macOS 内置 afplay 播放；阻塞到播放结束。"""
    subprocess.run(["afplay", str(path)], check=False)


def speak(text, providers=None, out_dir=None, play=True, player=None):
    """按顺序尝试各后端，合成成功后播放并返回实际使用的后端。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("待合成文本为空")
    attempts = []
    for provider in (_default_providers() if providers is None else providers):
        try:
            path = synthesize(text, provider, out_dir=out_dir)
        except TTSError as exc:
            _log("{} 失败，尝试下一个后端：{}".format(provider, exc))
            attempts.append("{}: {}".format(provider, exc))
            continue
        if play:
            (player or play_audio)(path)
        return TTSResult(provider=provider, path=str(path))
    raise TTSError("所有 TTS 后端均失败：" + "；".join(attempts))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tts_client.py <文本>", file=sys.stderr)
        raise SystemExit(2)
    result = speak(" ".join(sys.argv[1:]))
    print("{} -> {}".format(result.provider, result.path))
