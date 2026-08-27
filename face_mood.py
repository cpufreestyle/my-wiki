#!/usr/bin/env python3
"""
face_mood.py - 面部情绪识别（MediaPipe FaceLandmarker + 摄像头）

流程：cv2 打开摄像头 → 采样 N 帧 → MediaPipe FaceLandmarker 提取 478 个
面部关键点 → 计算几何特征（嘴角上扬度 / 嘴张开度 / 眉眼距 / 眉间紧锁 /
悲伤眉形 / 眼睛开合）→ 映射到 MyWiki 五种心情（开心/平静/低落/兴奋/
焦虑）。与 voice_mood 的声学分析互为补充，多路信号在 UI 层融合。

依赖：mediapipe>=0.10、opencv-python（模型文件约 3.6MB，首次运行自动
下载到 models/，之后离线可用）。缺失时可调用 auto_install_deps() 自动
安装，或手动：
  python -m pip install mediapipe opencv-python

注：mediapipe 0.10+/1.x 移除了旧的 mp.solutions.face_mesh，这里统一使用
新的 Tasks API（FaceLandmarker + .task 模型文件）。
"""
import math
import os
import statistics
import subprocess
import sys
import time
import urllib.request

MOODS = ("开心", "平静", "低落", "兴奋", "焦虑")

# 采样默认参数
DEFAULT_FRAMES = 12       # 采样帧数
DEFAULT_INTERVAL = 0.15   # 帧间隔（秒），总采样约 2 秒

# FaceLandmarker 模型（mediapipe 官方，float16，约 3.6MB）
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/"
             "face_landmarker/face_landmarker/float16/latest/"
             "face_landmarker.task")


# ---------- 依赖管理（模式与 voice_mood 一致） ----------

def deps_status():
    """返回 (mediapipe_ok, cv2_ok)，用于 UI / CLI 提前提示缺失依赖。"""
    mp_ok = False
    cv_ok = False
    try:
        import mediapipe  # noqa: F401
        mp_ok = True
    except Exception:
        pass
    try:
        import cv2  # noqa: F401
        cv_ok = True
    except Exception:
        pass
    return mp_ok, cv_ok


def _ensure_pip(notes):
    """确保当前解释器能用 `python -m pip`（与 voice_mood 相同的兜底逻辑）。"""
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
    notes.append("pip: ensurepip 失败")
    return False


def auto_install_deps():
    """尝试自动安装缺失依赖（mediapipe 约 50MB，首次安装需数分钟）。

    返回 (mp_ok, cv_ok, notes)。
    """
    notes = []
    pip_ok = _ensure_pip(notes)
    mp_ok, cv_ok = deps_status()
    if not pip_ok:
        notes.append("依赖安装跳过（pip 不可用，请手动安装）")
        return mp_ok, cv_ok, notes

    for name, ok in (("mediapipe", mp_ok), ("opencv-python", cv_ok)):
        if ok:
            notes.append("{}: 已就绪，跳过".format(name))
            continue
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", name],
                capture_output=True, text=True, timeout=600)
            notes.append("{}: {}".format(
                name, "已安装" if r.returncode == 0 else "安装失败"))
        except Exception as e:
            notes.append("{}: 安装异常 {}".format(name, e))

    mp_ok, cv_ok = deps_status()
    return mp_ok, cv_ok, notes


def ensure_model():
    """确认模型文件存在；缺失时自动下载（约 3.6MB，仅需一次）。

    返回 (ok, msg)：ok=False 时 msg 说明原因（含手动下载指引）。
    """
    if os.path.isfile(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100_000:
        return True, ""
    try:
        os.makedirs(MODEL_DIR, exist_ok=True)
        tmp = MODEL_PATH + ".part"
        urllib.request.urlretrieve(MODEL_URL, tmp)
        os.replace(tmp, MODEL_PATH)
        return True, ""
    except Exception as e:
        return False, (
            "FaceLandmarker 模型下载失败（{}）。请手动下载：{} "
            "并保存到 {}".format(e, MODEL_URL, MODEL_PATH))


# ---------- 特征提取 ----------

def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def extract_features(lm):
    """从 FaceLandmarker 关键点提取归一化几何特征（除以脸高，抵消距离/脸型差异）。

    landmark 索引（FaceMesh 478 点约定，前 468 点与旧版一致）：
      10 额头 / 152 下巴（脸高标尺）
      61 291 嘴角 / 13 上唇内缘 / 14 下唇内缘
      105 334 眉头 / 70 300 眉尾 / 107 336 内眉
      159 145 左眼上下睑 / 386 374 右眼上下睑
    """
    face_h = _dist(lm[10], lm[152]) or 1e-6

    # 嘴角上扬度：正=嘴角高于唇心（微笑），负=嘴角下垂
    lip_mid_y = (lm[13].y + lm[14].y) / 2.0
    corners_y = (lm[61].y + lm[291].y) / 2.0
    smile = (lip_mid_y - corners_y) / face_h

    # 嘴张开度（说话/激动时变大）
    mouth_open = abs(lm[13].y - lm[14].y) / face_h

    # 眉眼距：眉毛抬升（惊讶/兴奋时变大）
    brow_eye = ((lm[159].y - lm[105].y) + (lm[386].y - lm[334].y)) / 2.0 / face_h

    # 眉间距：皱眉/紧锁时变小
    brow_gap = _dist(lm[107], lm[336]) / face_h

    # 悲伤眉形：眉头相对眉尾抬高（担忧/低落的典型特征）
    sad_brow = ((lm[105].y - lm[70].y) + (lm[334].y - lm[300].y)) / 2.0 / face_h

    # 眼睛开合度（疲劳/低落时变小）
    eye_open = (abs(lm[159].y - lm[145].y) + abs(lm[386].y - lm[374].y)) / 2.0 / face_h

    return {
        "smile": smile,
        "mouth_open": mouth_open,
        "brow_eye": brow_eye,
        "brow_gap": brow_gap,
        "sad_brow": sad_brow,
        "eye_open": eye_open,
    }


def features_to_mood(f):
    """将面部几何特征映射为情绪评分。

    返回 (mood, confidence, detail)，置信度上限 0.85（几何启发式，
    与文本/声学信号在 UI 层融合，不单独给满置信）。
    """
    scores = {m: 0 for m in MOODS}
    details = []

    # 嘴角形态
    if f["smile"] > 0.030:
        scores["开心"] += 2
        scores["兴奋"] += 1
        details.append("嘴角上扬")
    elif f["smile"] > 0.012:
        scores["开心"] += 2
        details.append("面带微笑")
    elif f["smile"] < -0.008:
        scores["低落"] += 2
        details.append("嘴角下垂")

    # 嘴张开度
    if f["mouth_open"] > 0.045:
        scores["兴奋"] += 2
        details.append("嘴巴张开")
    elif f["mouth_open"] > 0.025:
        scores["兴奋"] += 1

    # 眉毛抬升
    if f["brow_eye"] > 0.105:
        scores["兴奋"] += 1
        scores["开心"] += 1
        details.append("眉毛上扬")

    # 眉间紧锁（压力/焦虑的典型特征）
    if f["brow_gap"] < 0.075:
        scores["焦虑"] += 2
        details.append("眉头紧锁")

    # 悲伤眉形（低落/担忧）
    if f["sad_brow"] > 0.010:
        scores["低落"] += 2
        scores["焦虑"] += 1
        details.append("眉形低垂")

    # 眼睛开合
    if f["eye_open"] < 0.018:
        scores["低落"] += 1
        scores["平静"] += 1
        details.append("眼神疲惫")

    best = max(scores.items(), key=lambda x: x[1])
    if best[1] == 0:
        return "平静", 0.4, "表情无明显特征"

    conf = min(best[1] / 5.0, 0.85)
    return best[0], round(conf, 2), "、".join(details)


# ---------- 摄像头采样 ----------

def capture_and_analyze(num_frames=DEFAULT_FRAMES, interval=DEFAULT_INTERVAL,
                        cam_index=0):
    """打开摄像头采样若干帧并分析面部情绪。

    返回 dict: {mood, confidence, detail, features, frames}；
    依赖缺失 / 摄像头不可用 / 未检测到人脸时返回 {"error": ...}。
    """
    mp_ok, cv_ok = deps_status()
    if not (mp_ok and cv_ok):
        missing = []
        if not mp_ok:
            missing.append("mediapipe")
        if not cv_ok:
            missing.append("opencv-python")
        return {"error": "缺少依赖：" + "、".join(missing)
                + "。可运行 python -m pip install " + " ".join(missing)}

    ok, msg = ensure_model()
    if not ok:
        return {"error": msg}

    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python import vision

    # Windows 下 CAP_DSHOW 打开更快（避免 MSMF 后端数秒延迟）
    if sys.platform == "win32":
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        cap.release()
        return {"error": "无法打开摄像头（设备被占用或不存在）"}

    features_list = []
    try:
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5)
        landmarker = vision.FaceLandmarker.create_from_options(options)
        t0 = time.monotonic()
        for _ in range(num_frames):
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int((time.monotonic() - t0) * 1000)
            result = landmarker.detect_for_video(mp_image, ts_ms)
            if result.face_landmarks:
                lm = result.face_landmarks[0]
                features_list.append(extract_features(lm))
            time.sleep(interval)
    finally:
        cap.release()

    if not features_list:
        return {"error": "未检测到人脸，请正对摄像头再试一次。"}

    # 多帧取中位数，抑制单帧抖动 / 眨眼
    median = {k: statistics.median(ft[k] for ft in features_list)
              for k in features_list[0]}
    mood, conf, detail = features_to_mood(median)
    return {
        "mood": mood,
        "confidence": conf,
        "detail": detail,
        "features": {k: round(v, 4) for k, v in median.items()},
        "frames": len(features_list),
    }


if __name__ == "__main__":
    print("face_mood - MediaPipe 面部情绪识别")
    mp_ok, cv_ok = deps_status()
    if not (mp_ok and cv_ok):
        print("依赖缺失，尝试自动安装（首次约需数分钟）…")
        mp_ok, cv_ok, notes = auto_install_deps()
        for n in notes:
            print("  " + n)
        if not (mp_ok and cv_ok):
            print("安装失败，请手动安装后重试。")
            sys.exit(1)
    ok, msg = ensure_model()
    if not ok:
        print(msg)
        sys.exit(1)
    print("请正对摄像头，采样约 {} 秒…".format(
        round(DEFAULT_FRAMES * DEFAULT_INTERVAL, 1)))
    result = capture_and_analyze()
    if "error" in result:
        print("失败：" + result["error"])
        sys.exit(1)
    print("情绪: {} (置信度 {})".format(result["mood"], result["confidence"]))
    print("特征: " + result["detail"])
    print("采样: {} 帧".format(result["frames"]))
