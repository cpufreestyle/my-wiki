#!/usr/bin/env python3
"""
voice_mood.py - 语音识别心情（本地麦克风 → 文字）

零 pyaudio 依赖方案：
  - 录音：ffmpeg（avfoundation / dshow / alsa，按平台自动选择）
  - 识别：SpeechRecognition 的 Google Web Speech API（需联网，支持中文 zh-CN）

流程图：点击按钮 → 后台线程 ffmpeg 录音 → AudioFile 读 wav → recognize_google → 回调返回文字
调用方把文字填入心情输入框并触发分析。
"""
import os
import shutil
import subprocess
import sys
import threading
import tempfile
import wave
import struct
import math
import array
import time

# ---- 诊断日志（写入临时目录，便于排查“正在聆听后没下文”问题）----
_DEBUG_LOG = os.path.join(tempfile.gettempdir(), "mywiki_voice_debug.log")

def _dbg(msg):
    """写入诊断日志，每行带时间戳。"""
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass

TMP_WAV = os.path.join(tempfile.gettempdir(), "mywiki_voice.wav")
MAX_SECONDS = 12  # 单次最长录音秒数（可中途点停止提前结束）

# ---------- 偏好：识别后是否自动保存心情 ----------
_PREF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
_AUTOSAVE_FILE = os.path.join(_PREF_DIR, "voice_autosave.txt")
DEFAULT_AUTOSAVE = True


def load_autosave_pref() -> bool:
    """读取「语音识别后自动保存心情」偏好，读不到回退默认开启。"""
    try:
        if os.path.exists(_AUTOSAVE_FILE):
            with open(_AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip() == "1"
    except Exception:
        pass
    return DEFAULT_AUTOSAVE


def save_autosave_pref(enabled: bool) -> None:
    """写入「语音识别后自动保存心情」偏好。"""
    try:
        os.makedirs(_PREF_DIR, exist_ok=True)
        with open(_AUTOSAVE_FILE, "w", encoding="utf-8") as f:
            f.write("1" if enabled else "0")
    except Exception:
        pass


def get_ffmpeg_path():
    """查找 ffmpeg 可执行文件。

    查找顺序：
      1. shutil.which（系统 PATH）
      2. 常见安装路径（macOS Homebrew / Linux apt / Windows）
         —— macOS GUI 应用启动时 PATH 只有 /usr/bin:/bin，
            shutil.which 找不到 Homebrew 安装的 ffmpeg，
            必须主动检查 /opt/homebrew/bin 等路径。
      3. pip 包 static-ffmpeg（最后手段，自动下载二进制）
    """
    # 1) 系统 PATH
    p = shutil.which("ffmpeg")
    if p:
        return p

    # 2) 常见安装路径（GUI 应用 PATH 受限时使用）
    candidate_paths = []
    if sys.platform == "darwin":
        candidate_paths = [
            "/opt/homebrew/bin/ffmpeg",           # Apple Silicon Homebrew
            "/usr/local/bin/ffmpeg",              # Intel Homebrew / MacPorts
            "/opt/local/bin/ffmpeg",              # MacPorts
        ]
    elif sys.platform.startswith("linux"):
        candidate_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/snap/bin/ffmpeg",
        ]
    elif sys.platform == "win32":
        candidate_paths = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin", "ffmpeg.exe"),
        ]
    for cand in candidate_paths:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand

    # 3) pip 包 static-ffmpeg（最后手段）
    try:
        from static_ffmpeg import run as sf
        ffmpeg_path, _ = sf.get_or_fetch_platform_executables_else_raise()
        if ffmpeg_path and os.path.exists(ffmpeg_path):
            return ffmpeg_path
    except Exception:
        pass
    return None


def deps_status():
    """返回 (ffmpeg_ok, sr_ok)，用于 UI 提前提示缺失依赖。"""
    ffmpeg_ok = get_ffmpeg_path() is not None
    sr_ok = False
    try:
        import speech_recognition  # noqa: F401
        sr_ok = True
    except Exception:
        sr_ok = False
    return ffmpeg_ok, sr_ok


def _ensure_pip(notes):
    """确保当前解释器能用 `python -m pip`。

    有些 venv 创建时未包含 pip（现象：`No module named pip`），
    此时先尝试用 ensurepip 引导安装 pip，再返回是否可用。
    """
    # 先探测 pip 模块是否存在
    probe = subprocess.run([sys.executable, "-m", "pip", "--version"],
                           capture_output=True, text=True, timeout=60)
    if probe.returncode == 0:
        return True
    notes.append("pip: 未找到，尝试用 ensurepip 引导安装…")
    boot = subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"],
                          capture_output=True, text=True, timeout=300)
    if boot.returncode == 0:
        notes.append("pip: 已通过 ensurepip 安装")
        return True
    notes.append("pip: ensurepip 失败（{}）".format(
        (boot.stderr or boot.stdout).strip().splitlines()[-1] if (boot.stderr or boot.stdout).strip() else "未知错误"))
    return False


def auto_install_deps():
    """尝试自动安装缺失依赖（纯 pip，无需 brew / portaudio）。

    - SpeechRecognition：始终尝试 pip 安装。
    - ffmpeg：优先 pip 安装 static-ffmpeg（自带二进制，无需系统权限）；
      若已存在于系统 PATH 则跳过。
    返回 (ffmpeg_ok, sr_ok, notes)。
    """
    notes = []

    # 确保 pip 可用（部分 venv 没有自带 pip）
    pip_ok = _ensure_pip(notes)

    # 1) ffmpeg
    if get_ffmpeg_path() is None:
        if not pip_ok:
            notes.append("ffmpeg: 跳过（pip 不可用，可手动 brew install ffmpeg）")
        else:
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "static-ffmpeg"],
                                   capture_output=True, text=True, timeout=300)
                if r.returncode == 0 and get_ffmpeg_path() is not None:
                    notes.append("ffmpeg: 已通过 static-ffmpeg 安装")
                else:
                    notes.append("ffmpeg: static-ffmpeg 安装失败（可手动 brew install ffmpeg）")
            except Exception as e:
                notes.append("ffmpeg: 安装异常 {}".format(e))
    else:
        notes.append("ffmpeg: 已就绪，跳过")

    # 2) SpeechRecognition
    try:
        import speech_recognition  # noqa: F401
        notes.append("SpeechRecognition: 已就绪，跳过")
    except Exception:
        if not pip_ok:
            notes.append("SpeechRecognition: 跳过（pip 不可用，请先确保 pip 可用）")
        else:
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "SpeechRecognition"],
                                   capture_output=True, text=True, timeout=300)
                if r.returncode == 0:
                    notes.append("SpeechRecognition: 已安装")
                else:
                    notes.append("SpeechRecognition: 安装失败")
            except Exception as e:
                notes.append("SpeechRecognition: 安装异常 {}".format(e))

    ffmpeg_ok, sr_ok = deps_status()
    return ffmpeg_ok, sr_ok, notes


def _ffmpeg_input_args():
    """按平台返回 ffmpeg 录音输入参数。"""
    if sys.platform == "darwin":
        return ["-f", "avfoundation", "-i", ":0"]          # 默认音频输入设备
    if sys.platform == "win32":
        return ["-f", "dshow", "-i", "audio=麦克风"]         # 中文 Windows 默认麦克风名
    return ["-f", "alsa", "-i", "default"]                  # Linux


def analyze_voice_acoustics(wav_path):
    """分析录音的声学特征，辅助判断情绪。

    纯 Python 实现，无额外依赖（仅用 wave + struct + math）。
    从 PCM WAV 中提取：
      - energy_rms: 整体能量（RMS），反映音量/力度
      - energy_std: 能量波动，反映情绪稳定性
      - pitch_zcr: 过零率（ZCR），近似音高
      - pitch_std: 过零率波动，反映语调变化
      - speech_rate: 有效语音段密度，近似语速
      - duration: 录音时长（秒）

    返回 dict，分析失败返回 None。
    声学特征与情绪的关联（基于语音情感分析研究）：
      - 兴奋: 高能量 + 高过零率 + 大波动
      - 焦虑: 高语速 + 高过零率波动 + 中等能量
      - 开心: 中高能量 + 中高过零率 + 中等波动
      - 低落: 低能量 + 低过零率 + 小波动
      - 平静: 中低能量 + 低过零率 + 小波动
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if not raw or n_frames == 0:
            return None

        # 解析 PCM 样本为整数列表（仅支持 16-bit，与录音参数一致）
        if sample_width != 2:
            return None
        samples = array.array("h")  # signed short
        samples.frombytes(raw)
        if n_channels > 1:
            # 取第一个声道
            samples = array.array("h", samples[::n_channels])

        n = len(samples)
        if n == 0:
            return None

        duration = n / float(framerate)

        # 按帧分析（每帧 30ms，步长 20ms）
        frame_size = int(0.030 * framerate)
        hop_size = int(0.020 * framerate)
        if frame_size < 2 or hop_size < 1:
            frame_size = max(frame_size, 2)
            hop_size = max(hop_size, 1)

        frame_energies = []
        frame_zcrs = []
        voiced_frames = 0

        for i in range(0, n - frame_size, hop_size):
            frame = samples[i:i + frame_size]
            # RMS 能量
            sum_sq = sum(s * s for s in frame)
            rms = math.sqrt(sum_sq / len(frame))
            frame_energies.append(rms)
            # 过零率 (ZCR) — 近似音高
            zc = 0
            for j in range(1, len(frame)):
                if (frame[j - 1] >= 0) != (frame[j] >= 0):
                    zc += 1
            zcr = zc / len(frame)
            frame_zcrs.append(zcr)
            # 有声帧判断（能量 > 阈值）
            if rms > 300:
                voiced_frames += 1

        if not frame_energies:
            return None

        # --- 汇总统计 ---
        # 能量
        energy_rms = sum(frame_energies) / len(frame_energies)
        energy_std = math.sqrt(
            sum((e - energy_rms) ** 2 for e in frame_energies) / len(frame_energies)
        ) if len(frame_energies) > 1 else 0

        # 过零率
        pitch_zcr = sum(frame_zcrs) / len(frame_zcrs)
        pitch_std = math.sqrt(
            sum((z - pitch_zcr) ** 2 for z in frame_zcrs) / len(frame_zcrs)
        ) if len(frame_zcrs) > 1 else 0

        # 语速估计：有声帧数 / 时长
        speech_rate = voiced_frames / duration if duration > 0 else 0

        return {
            "energy_rms": round(energy_rms, 1),
            "energy_std": round(energy_std, 1),
            "pitch_zcr": round(pitch_zcr, 4),
            "pitch_std": round(pitch_std, 4),
            "speech_rate": round(speech_rate, 2),
            "duration": round(duration, 1),
            "voiced_frames": voiced_frames,
            "total_frames": len(frame_energies),
        }
    except Exception:
        return None


def acoustics_to_mood(features):
    """将声学特征映射为情绪倾向评分。

    返回 (mood_hint, confidence, detail):
      mood_hint: 基于声音特征的倾向（可能与文本分析不同，用于辅助）
      confidence: 0.0-0.5（声学分析置信度，作为辅助不超 0.5）
      detail: 人类可读的分析描述
    """
    if not features:
        return None, 0, ""

    e = features["energy_rms"]
    e_std = features["energy_std"]
    zcr = features["pitch_zcr"]
    zcr_std = features["pitch_std"]
    rate = features["speech_rate"]
    voiced = features["voiced_frames"]

    # 有效语音太少（基本没说话）
    if voiced < 3:
        return "平静", 0.1, "声音太短，无法分析声学特征"

    scores = {"开心": 0, "平静": 0, "低落": 0, "兴奋": 0, "焦虑": 0}
    details = []

    # 能量分析（RMS 范围约 0-30000，16-bit PCM）
    if e > 5000:
        scores["兴奋"] += 2
        scores["开心"] += 1
        details.append("音量较高")
    elif e > 2000:
        scores["开心"] += 1
        scores["焦虑"] += 1
        details.append("音量适中")
    elif e > 500:
        scores["平静"] += 1
        details.append("音量较低")
    else:
        scores["低落"] += 2
        details.append("声音很轻")

    # 能量波动
    if e_std > 3000:
        scores["兴奋"] += 1
        scores["焦虑"] += 1
        details.append("音量波动大")
    elif e_std < 500:
        scores["平静"] += 1
        scores["低落"] += 1
        details.append("音量稳定")

    # 过零率（近似音高，越高音调越高）
    if zcr > 0.15:
        scores["兴奋"] += 1
        scores["焦虑"] += 1
        details.append("音调偏高")
    elif zcr < 0.06:
        scores["低落"] += 1
        scores["平静"] += 1
        details.append("音调偏低")
    else:
        scores["开心"] += 1
        details.append("音调适中")

    # 过零率波动（语调变化）
    if zcr_std > 0.05:
        scores["兴奋"] += 1
        scores["开心"] += 1
        details.append("语调起伏丰富")
    elif zcr_std < 0.01:
        scores["平静"] += 1
        scores["低落"] += 1
        details.append("语调平缓")

    # 语速
    if rate > 8:
        scores["焦虑"] += 1
        scores["兴奋"] += 1
        details.append("语速较快")
    elif rate < 2:
        scores["低落"] += 1
        scores["平静"] += 1
        details.append("语速较慢")

    best = max(scores.items(), key=lambda x: x[1])
    if best[1] == 0:
        return "平静", 0.1, "声学特征不明显"

    # 声学分析作为辅助，置信度上限 0.5
    conf = min(best[1] / 6.0, 0.5)
    return best[0], round(conf, 2), "、".join(details)


class VoiceRecorder:
    """在后台线程录音并识别，通过回调把结果抛回主线程。"""

    def __init__(self, on_status=None, on_result=None, on_error=None,
                 on_acoustics=None):
        self.on_status = on_status or (lambda *a, **k: None)
        self.on_result = on_result or (lambda *a, **k: None)
        self.on_error = on_error or (lambda *a, **k: None)
        self.on_acoustics = on_acoustics or (lambda *a, **k: None)
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._running = False

    @property
    def running(self):
        return self._running

    def start(self, lang="zh-CN", max_seconds=MAX_SECONDS):
        _dbg("start() 被调用, _running={}".format(self._running))
        if self._running:
            _dbg("start() 放弃：已在运行")
            return
        self._running = True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(lang, max_seconds), daemon=True)
        self._thread.start()
        _dbg("start() 线程已启动")

    def stop(self):
        """请求停止录音：非阻塞式终止 ffmpeg，已录部分不再识别（直接取消）。

        关键：不在主线程调用 proc.wait()，否则会冻结 UI（macOS 上 ffmpeg
        可能不响应 SIGTERM，proc.wait(timeout=2) 会阻塞主线程 2 秒，
        导致按钮卡在"停止"状态、用户无法操作）。
        """
        self._stop.set()
        self._running = False  # 立即标记为非运行状态，防止重复启动
        proc = self._proc
        self._proc = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            # 后台线程确保进程被杀死，不阻塞主线程
            def _force_kill():
                try:
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            threading.Thread(target=_force_kill, daemon=True).start()

    def _run(self, lang, max_seconds):
        try:
            _dbg("=== _run 开始 (lang={}, max_seconds={}) ===".format(lang, max_seconds))
            # 1) 录音
            self.on_status("recording", "正在聆听…（最多 {} 秒）".format(max_seconds))
            ffmpeg_path = get_ffmpeg_path()
            _dbg("ffmpeg_path={}".format(ffmpeg_path))
            if not ffmpeg_path:
                _dbg("错误：未找到 ffmpeg")
                self.on_error("未找到 ffmpeg，无法录音。")
                return
            args = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                    *_ffmpeg_input_args(),
                    "-t", str(max_seconds), "-ar", "16000", "-ac", "1",
                    "-c:a", "pcm_s16le", TMP_WAV]
            _dbg("启动 ffmpeg: {}".format(" ".join(args)))
            # 捕获 stderr 用于诊断录音失败（macOS 麦克风权限、设备不存在等）
            # 用局部变量 proc 引用，避免 stop() 并发把 self._proc 设为 None 后
            # _run 线程访问 self._proc.returncode 导致 AttributeError
            proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            self._proc = proc
            stdout_data, stderr_data = proc.communicate()
            retcode = proc.returncode
            self._proc = None
            _dbg("ffmpeg 结束, returncode={}".format(retcode))

            # 用户中途停止：不再直接丢弃，尝试识别已录内容
            if self._stop.is_set():
                _dbg("用户中途停止，尝试识别已录内容")
                wav_size = os.path.getsize(TMP_WAV) if os.path.exists(TMP_WAV) else 0
                if wav_size < 44:
                    # 录得太短，无法识别
                    self.on_status("idle", "已取消")
                    return
                # 有有效录音，继续往下走声学分析 + 识别流程
                _dbg("已录内容有效 ({}字节)，继续识别".format(wav_size))

            wav_size = os.path.getsize(TMP_WAV) if os.path.exists(TMP_WAV) else 0
            _dbg("WAV 文件大小={}".format(wav_size))
            if not os.path.exists(TMP_WAV) or wav_size < 44:
                # 录音失败：用 stderr 信息帮助诊断
                err_msg = stderr_data.decode("utf-8", errors="replace").strip() if stderr_data else ""
                _dbg("录音失败, stderr={}".format(err_msg[:200]))
                low = err_msg.lower()
                if ("operation not permitted" in low or "denied" in low
                        or "authorization" in low or "avcapture" in low
                        or "microphone" in low):
                    # macOS 麦克风权限被拒（或设备被系统禁用）
                    self.on_error(
                        "麦克风权限被拒绝。请到「系统设置 › 隐私与安全性 › 麦克风」，"
                        "给运行本程序的终端或应用（Terminal、iTerm 或 MyWiki.app）"
                        "开启权限，然后重启程序重试。")
                elif err_msg:
                    self.on_error("录音失败：{}".format(err_msg[:200]))
                else:
                    self.on_status("idle", "已取消")
                return

            # 2) 声学特征分析（纯本地，不依赖网络，先于文字识别）
            _dbg("开始声学分析")
            acoustics = analyze_voice_acoustics(TMP_WAV)
            _dbg("声学分析完成: {}".format(acoustics is not None))
            if acoustics:
                self.on_acoustics(acoustics)

            # 3) 语音识别（文字）
            _dbg("开始语音识别")
            self.on_status("recognizing", "识别中…")
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            # 设置超时，避免 Google API 不可达时永久挂起
            recognizer.operation_timeout = 10  # 单次请求最多 10 秒
            recognizer.pause_threshold = 0.8
            with sr.AudioFile(TMP_WAV) as source:
                audio = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio, language=lang)
                _dbg("识别成功: text={}".format((text or "")[:50]))
            except sr.UnknownValueError:
                _dbg("识别失败: UnknownValueError")
                # 文字识别失败时，仍可用声学特征分析心情
                if acoustics:
                    self.on_result(None, acoustics)
                    self.on_status("done", "已分析声音特征（文字未识别）")
                else:
                    self.on_error("没听清，请再说一次。")
                return
            except sr.RequestError as e:
                _dbg("识别失败: RequestError={}".format(e))
                # 网络不通时，仍可用声学特征分析心情
                if acoustics:
                    self.on_result(None, acoustics)
                    self.on_status("done", "已分析声音特征（识别服务不可用）")
                else:
                    self.on_error("识别服务不可用（需联网）：{}".format(e))
                return
            except Exception as e:
                _dbg("识别失败: Exception={}".format(e))
                # 其他异常时，仍可用声学特征
                if acoustics:
                    self.on_result(None, acoustics)
                    self.on_status("done", "已分析声音特征")
                else:
                    self.on_error("识别失败（可能网络不通）：{}".format(e))
                return

            text = (text or "").strip()
            if not text:
                _dbg("识别结果为空")
                if acoustics:
                    self.on_result(None, acoustics)
                    self.on_status("done", "已分析声音特征")
                else:
                    self.on_error("识别结果为空，请再说一次。")
                return
            _dbg("分发结果: text={}, acoustics={}".format(text[:30], acoustics is not None))
            self.on_result(text, acoustics)
            self.on_status("done", "已识别")
        except FileNotFoundError:
            _dbg("异常: FileNotFoundError")
            self.on_error("未找到 ffmpeg，无法录音。")
        except Exception as e:
            _dbg("异常: {}".format(e))
            self.on_error("语音识别失败：{}".format(e))
        finally:
            _dbg("_run 结束")
            self._running = False
