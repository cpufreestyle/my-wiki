#!/usr/bin/env python3
"""vision_face_mood.py - macOS Vision 面部情绪（VNDetectFaceLandmarksRequest）

背景：MediaPipe 1.0.1 在 macOS 上初始化 FaceLandmarker 时，其 Metal GPU 委托
(-[DrishtiMetalHelper initWithCalculatorContext:]) 会在 MediaPipe 自己的线程池里
触发 absl::Check failed，直接 abort 整个进程。而 web_server.py 在同一进程内调用
MediaPipe，一次失败就带崩全部 HTTP 服务（表现为「面部识别请求失败」）。

本模块改用 Apple 自带的 VNDetectFaceLandmarksRequest（macOS 10.15+，无需下载模型、
GPU 加速、不依赖第三方推理库），从 76 点 constellation 抽取与 MediaPipe 版完全相同
的六个归一化几何特征，交由 face_mood.features_to_mood 统一映射情绪，
保证两条后端结果口径一致。

依赖：仅 pyobjc（Vision/Quartz）+ opencv-python（摄像头采样）。
"""
import io
import json
import statistics
import sys
import time

from face_mood import (
    DEFAULT_FRAMES,
    DEFAULT_INTERVAL,
    MOODS,
    features_to_mood,
)

_VISION = None
_PROBED = None


def _load():
    """惰性加载 Vision；macOS 且 pyobjc 可用时返回 True，否则 False。"""
    global _VISION, _PROBED
    if _PROBED is not None:
        return _PROBED
    _PROBED = False
    if sys.platform != "darwin":
        return False
    try:
        import Vision
        if not hasattr(Vision, "VNDetectFaceLandmarksRequest"):
            return False
    except Exception:
        return False
    _VISION = Vision
    _PROBED = True
    return True


def is_available():
    """当前环境是否支持 macOS Vision 人脸关键点。"""
    return _load() is True


def deps_status():
    """返回 (vision_ok, cv2_ok)，供 UI / API 提前提示缺失依赖。"""
    cv_ok = True
    try:
        import cv2
    except Exception:
        cv_ok = False
    return _load() is True, cv_ok


def _points(region):
    """取 VNFaceLandmarkRegion2D 的归一化点，翻成 y 向下（与 FaceMesh 同向）。

    pyobjc 把 normalizedPoints 暴露成 objc.varlist：只支持下标访问、没有 __iter__，
    直接 for 迭代会 SIGBUS，因此按 pointCount 做索引取值。
    """
    if region is None:
        return []
    n = getattr(region, "pointCount", None)
    if callable(n):
        n = n()
    if not n:
        return []
    val = getattr(region, "normalizedPoints", None)
    if callable(val):
        val = val()
    if val is None:
        return []
    out = []
    for i in range(int(n)):
        p = val[i]
        out.append((float(p.x), 1.0 - float(p.y)))
    return out


def _regions(jpeg_bytes):
    """跑一次人脸关键点检测，返回 {区域名: [(x, y), ...]}；无人脸返回 None。"""
    if not _load():
        return None
    from Foundation import NSData
    from PIL import Image

    frame = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    buf = io.BytesIO()
    frame.save(buf, "JPEG", quality=92)
    raw = buf.getvalue()
    data = NSData.dataWithBytes_length_(raw, len(raw))
    handler = _VISION.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    req = _VISION.VNDetectFaceLandmarksRequest.alloc().initWithCompletionHandler_(None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise RuntimeError("Vision 人脸检测失败: {}".format(err))
    results = req.results()
    if not results:
        return None
    obs = results[0]
    lm = getattr(obs, "landmarks")
    if callable(lm):
        lm = lm()
    if lm is None:
        return None
    names = ("faceContour", "outerLips", "innerLips", "leftEye", "rightEye",
             "leftEyebrow", "rightEyebrow")
    out = {}
    for name in names:
        region = getattr(lm, name, None)
        if callable(region):
            region = region()
        pts = _points(region)
        if pts:
            out[name] = pts
    return out


def _xs(pts):
    return [p[0] for p in pts]


def _ys(pts):
    return [p[1] for p in pts]


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _innermost(pts, x_center):
    """取最靠近 x_center 的点，用于定位眉头。"""
    return min(pts, key=lambda p: abs(p[0] - x_center))


def extract_features(regions):
    """从 Vision 区域点集抽取六个归一化几何特征。

    与 face_mood.extract_features（FaceMesh 索引版）保持同一套定义与量纲，
    因此可直接复用 features_to_mood 的阈值。输入点坐标归一化且 y 向下。
    """
    fc = regions.get("faceContour") or []
    ol = regions.get("outerLips") or []
    il = regions.get("innerLips") or []
    le = regions.get("leftEye") or []
    re = regions.get("rightEye") or []
    lb = regions.get("leftEyebrow") or []
    rb = regions.get("rightEyebrow") or []

    face_h = (max(_ys(fc)) - min(_ys(fc))) if fc else 0.0
    if face_h <= 1e-6:
        face_h = 1e-6

    # 嘴角 = 外唇最左 / 最右点；唇心 = 内唇竖直中点
    if ol:
        xs = _xs(ol)
        corner_l = ol[xs.index(min(xs))]
        corner_r = ol[xs.index(max(xs))]
        corners_y = (corner_l[1] + corner_r[1]) / 2.0
    else:
        corners_y = 0.0
    if il:
        lip_mid_y = (min(_ys(il)) + max(_ys(il))) / 2.0
    elif ol:
        ys = _ys(ol)
        lip_mid_y = (min(ys) + max(ys)) / 2.0
    else:
        lip_mid_y = 0.0
    smile = (lip_mid_y - corners_y) / face_h

    mouth_open = (max(_ys(il)) - min(_ys(il))) / face_h if il else 0.0

    # 眉眼距：上眼睑顶到眉底的间隙
    gaps = []
    for eye, brow in ((le, lb), (re, rb)):
        if eye and brow:
            gaps.append((min(_ys(eye)) - max(_ys(brow))) / face_h)
    brow_eye = (sum(gaps) / len(gaps)) if gaps else 0.0

    # 眉间距：两个内眉头（最靠近中线者）的水平距离
    if lb and rb:
        brow_gap = _dist(_innermost(lb, 0.5), _innermost(rb, 0.5)) / face_h
    else:
        brow_gap = 1.0

    # 悲伤眉形：内眉头相对眉尾的竖直偏移
    sads = []
    for brow, is_left in ((lb, True), (rb, False)):
        if brow:
            xs = _xs(brow)
            tail = brow[xs.index(min(xs)) if is_left else xs.index(max(xs))]
            sads.append((_innermost(brow, 0.5)[1] - tail[1]) / face_h)
    sad_brow = (sum(sads) / len(sads)) if sads else 0.0

    # 眼睛开合度
    opens = []
    for eye in (le, re):
        if eye:
            opens.append((max(_ys(eye)) - min(_ys(eye))) / face_h)
    eye_open = (sum(opens) / len(opens)) if opens else 0.0

    return {
        "smile": smile,
        "mouth_open": mouth_open,
        "brow_eye": brow_eye,
        "brow_gap": brow_gap,
        "sad_brow": sad_brow,
        "eye_open": eye_open,
    }


def analyze_frames(jpeg_frames):
    """输入多帧 JPEG 字节，返回与 face_mood.capture_and_analyze 同构的结果 dict。"""
    ok_v, _ok_cv = deps_status()
    if not ok_v:
        return {"error": "当前 macOS 版本不支持 Vision 人脸关键点"}
    features_list = []
    for jb in jpeg_frames:
        try:
            regions = _regions(jb)
        except Exception as e:
            return {"error": str(e)}
        if not regions:
            continue
        features_list.append(extract_features(regions))
    if not features_list:
        return {"error": "未检测到人脸，请正对摄像头再试一次。"}
    median = {k: statistics.median(ft[k] for ft in features_list)
              for k in features_list[0]}
    mood, conf, detail = features_to_mood(median)
    return {
        "mood": mood,
        "confidence": conf,
        "detail": detail,
        "features": {k: round(v, 4) for k, v in median.items()},
        "frames": len(features_list),
        "backend": "vision",
    }



# 摄像头探测 / 打开重试 --------------------------------------------------------
# macOS 摄像头是独占设备：被 Zoom / 腾讯会议 / FaceTime / 其它浏览器标签页占用时
# 会打开失败，且首帧常未就绪。不重试的话，用户看到的就是一句「无法打开摄像头」。
CAMERA_OPEN_TRIES = 3       # 打开重试次数
CAMERA_OPEN_BACKOFF = 0.5   # 每次重试间隔（秒）
FRAME_READ_TRIES = 5        # 单帧读取重试次数（首帧常未就绪）


def _avf_device():
    """取 macOS 默认视频采集设备；非 macOS 或不可用时返回 None。"""
    if sys.platform != "darwin":
        return None
    try:
        import objc
        objc.loadBundle(
            "AVFoundation",
            bundle_path=objc.pathForFramework(
                "/System/Library/Frameworks/AVFoundation.framework"),
            module_globals=globals())
        return AVCaptureDevice.defaultDeviceWithMediaType_("vide")
    except Exception:
        return None


def _avf_state():
    """返回摄像头设备状态：present / device / busy_by_other。"""
    state = {"present": False, "device": None, "busy_by_other": None}
    dev = _avf_device()
    if dev is None:
        return state
    try:
        if dev.isConnected():
            state["present"] = True
            state["device"] = str(dev.localizedName())
        for attr in ("isInUseByAnotherApplication", "isInUseByAnotherClient"):
            getter = getattr(dev, attr, None)
            if callable(getter):
                state["busy_by_other"] = bool(getter())
                break
    except Exception:
        pass
    return state


def camera_hint(state=None):
    """把摄像头状态翻译成可操作的中文提示。"""
    state = state if state is not None else _avf_state()
    if not state.get("present"):
        return ("未检测到摄像头设备：请检查摄像头/采集卡连接，"
                "以及系统设置 → 隐私与安全性 → 摄像头 权限")
    if state.get("busy_by_other"):
        return ("摄像头正被其它程序占用（Zoom / 腾讯会议 / FaceTime / "
                "其它浏览器标签页），关闭后重试")
    return ("摄像头打不开：请在系统设置 → 隐私与安全性 → 摄像头 中允许"
            "终端 / Python，或重新插拔摄像头")


def _read_frames(cap, num_frames, interval, cv2mod=None):
    """从已打开的摄像头读 num_frames 帧，返回 JPEG 字节列表。"""
    if cv2mod is None:
        import cv2 as cv2mod
    frames = []
    for i in range(num_frames):
        frame = None
        for _ in range(FRAME_READ_TRIES):
            ok, frame = cap.read()
            if ok and frame is not None:
                break
            time.sleep(0.05)
        if frame is None:
            break
        ok, buf = cv2mod.imencode(".jpg", frame)
        if not ok:
            break
        frames.append(bytes(buf))
        if i < num_frames - 1:
            time.sleep(interval)
    return frames


def _open_camera(cam_index, tries=None):
    """带重试地打开摄像头，返回 (cap, opened)。"""
    import cv2
    if sys.platform == "win32":
        def opener():
            return cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
    else:
        def opener():
            return cv2.VideoCapture(cam_index)
    cap = None
    opened = False
    for _ in range(max(1, tries or CAMERA_OPEN_TRIES)):
        if cap is not None:
            cap.release()
        cap = opener()
        opened = bool(cap.isOpened())
        if opened:
            break
        time.sleep(CAMERA_OPEN_BACKOFF)
    return cap, opened


def camera_probe(cam_index=0):
    """摄像头自检：只取 1 帧，返回结构化状态（不长时间占用摄像头）。"""
    import cv2
    state = _avf_state()
    probe = {"present": state["present"], "device": state["device"],
             "busy_by_other": state["busy_by_other"],
             "can_open": False, "can_read": False}
    cap, opened = _open_camera(cam_index)
    probe["can_open"] = bool(opened)
    try:
        if opened:
            frames = _read_frames(cap, 1, 0.0, cv2mod=cv2)
            probe["can_read"] = bool(frames)
            probe["frame_bytes"] = len(frames[0]) if frames else 0
    finally:
        if cap is not None:
            cap.release()
    if probe["can_read"]:
        probe["ok"] = True
        probe["hint"] = "摄像头正常，可以开始面部识别。"
    else:
        probe["ok"] = False
        probe["hint"] = camera_hint(state)
    return probe


def capture_and_analyze(num_frames=DEFAULT_FRAMES, interval=DEFAULT_INTERVAL,
                        cam_index=0):
    """打开摄像头采样若干帧并分析面部情绪（Vision 后端）。"""
    if not deps_status()[1]:
        return {"error": "缺少依赖：opencv-python。"
                "可运行 python -m pip install opencv-python"}
    import cv2
    state = _avf_state()
    # 被其它程序占用时多等几轮，避免一句「无法打开摄像头」把用户挡死
    tries = CAMERA_OPEN_TRIES if state.get("busy_by_other") else 1
    cap, opened = _open_camera(cam_index, tries=tries)
    try:
        if not opened:
            return {"error": camera_hint(state)}
        frames = _read_frames(cap, num_frames, interval, cv2mod=cv2)
    finally:
        if cap is not None:
            cap.release()
    if not frames:
        return {"error": "摄像头已打开但采集不到画面：" + camera_hint(state)}
    return analyze_frames(frames)


def main():
    """供 web_server 以子进程调用，规避 native abort 带走主进程。

    --json          识别一次：成功 stdout {"ok": true, "face": {...}}，
                    失败 {"ok": false, "error": ...}（单行）
    --camera-probe  只做摄像头自检：{"ok": true, "camera": {...}}
    """
    if "--camera-probe" in sys.argv:
        probe = camera_probe()
        json.dump({"ok": bool(probe.get("ok")), "camera": probe},
                  sys.stdout, ensure_ascii=False)
        return 0 if probe.get("ok") else 1
    result = capture_and_analyze()
    if "error" in result:
        json.dump({"ok": False, "error": result["error"]},
                  sys.stdout, ensure_ascii=False)
        return 1
    json.dump({"ok": True, "face": result}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
