#!/usr/bin/env python3
"""vision_segment.py — macOS Vision 人物分割（Apple 官方虚化同款技术）

通过 PyObjC 调用 VNGeneratePersonSegmentationRequest（macOS 11+ 系统自带，
FaceTime 人像 / 照片虚化背后的分割引擎，GPU 加速、无需下载模型），
把一帧 JPEG 解码后生成人像 alpha mask（RGBA PNG，白底 alpha=mask），
供网页端 destination-in 抠图合成。

mask 约定（前后端唯一事实来源，改一端必须同步另一端）：
    1) 输出宽高 == 传入 JPEG 的宽高。Vision 内部固定产出 4:3 的
       OneComponent8 掩码，与 16:9 摄像头帧不同比例；这里按帧尺寸
       重采样回同一坐标系，前端 drawImage 与视频帧同尺寸叠加即可，
       不需要在 JS 里猜宽高比（猜错的后果是人被横向压扁或错位）。
    2) RGB 恒为白、alpha=matte（人像=255 不透明，背景=0 透明）。

非 macOS 或缺 pyobjc 时 is_available() 返回 False，web_server 自动降级
为浏览器端 MediaPipe Selfie Segmentation。
"""
import ctypes
import io
import sys
import threading

# ---- 可用性探测（惰性、线程安全） ----
_available = None
_lock = threading.Lock()


def _try_import():
    try:
        import Vision  # noqa: F401
        import Quartz  # noqa: F401
        from Foundation import NSData  # noqa: F401
        return True
    except Exception:
        return False


def is_available():
    """当前环境是否支持 macOS Vision 人物分割。"""
    global _available
    if _available is None:
        with _lock:
            if _available is None:
                _available = sys.platform == "darwin" and _try_import()
    return _available


def matte_to_frame_size(mask, jpeg_bytes):
    """把 Vision 掩码重采样到「帧尺寸」，返回同内容的 L 模式图像。

    Vision 固定输出 4:3 的 OneComponent8 掩码，而摄像头可能是 16:9
    （甚至以后换成别的比例）。直接拿 4:3 掩码铺到 16:9 画面上，人物会被
    横向压扁约 1.33 倍，边缘与真实人体错开——表现为「抠图边缘对不上人」
    「人周围发虚」。在 JS 里猜宽高比同样脆弱（要区分 Vision/MediaPipe 两种
    引擎的不同约定），所以在后端一次性对齐坐标系，前端 drawImage 即可。

    像素语义不变：仍为 0=背景 / 255=人像。
    """
    from PIL import Image
    frame = Image.open(io.BytesIO(jpeg_bytes))
    if frame.size == mask.size:
        return mask
    return mask.resize(frame.size, Image.BILINEAR)


class VisionSegmenter:
    """人物分割器（线程不安全，调用方自行串行化或每线程一个实例）。"""

    def __init__(self):
        if not is_available():
            raise RuntimeError("macOS Vision 不可用")
        import Vision
        from Foundation import NSData  # noqa: F401
        self._Vision = Vision
        self._NSData = NSData
        # CVPixelBufferGetBaseAddress 在 pyobjc 里返回 varlist 装箱，
        # 直接用 ctypes 调 C 符号拿裸指针更直接
        self._cv = ctypes.CDLL(
            "/System/Library/Frameworks/CoreVideo.framework/CoreVideo")
        self._cv.CVPixelBufferGetBaseAddress.restype = ctypes.c_void_p
        self._cv.CVPixelBufferGetBaseAddress.argtypes = [ctypes.c_void_p]

    def segment_jpeg_to_png(self, jpeg_bytes, quality="balanced"):
        """输入一帧 JPEG，返回人像 alpha mask 的 RGBA PNG 字节。

        返回尺寸 == 传入 JPEG 尺寸；RGB 恒为白、alpha=matte（人像不透明）。
        前端 drawImage + destination-in 即得抠图。
        quality: 'balanced'（实时，~14ms）| 'accurate'（单次高质量，边缘更准）。
        """
        from Quartz import (
            CVPixelBufferLockBaseAddress, CVPixelBufferUnlockBaseAddress,
            CVPixelBufferGetBytesPerRow, CVPixelBufferGetWidth,
            CVPixelBufferGetHeight,
        )
        from PIL import Image

        V = self._Vision
        data = self._NSData.dataWithBytes_length_(jpeg_bytes, len(jpeg_bytes))
        handler = V.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        req = V.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
        if quality == "accurate":
            req.setQualityLevel_(V.VNGeneratePersonSegmentationRequestQualityLevelAccurate)
        else:
            req.setQualityLevel_(V.VNGeneratePersonSegmentationRequestQualityLevelBalanced)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(f"Vision 请求失败: {err}")
        results = req.results()
        if not results:
            raise RuntimeError("Vision 未返回分割结果")

        pb = results[0].pixelBuffer()
        CVPixelBufferLockBaseAddress(pb, 0)
        try:
            w = CVPixelBufferGetWidth(pb)
            h = CVPixelBufferGetHeight(pb)
            bs = CVPixelBufferGetBytesPerRow(pb)
            addr = self._cv.CVPixelBufferGetBaseAddress(pb.__c_void_p__())
            arr = (ctypes.c_ubyte * (bs * h)).from_address(addr)
            lines = [bytes(arr[i * bs:i * bs + w]) for i in range(h)]
            mask = Image.frombytes("L", (w, h), b"".join(lines))
        finally:
            CVPixelBufferUnlockBaseAddress(pb, 0)

        mask = matte_to_frame_size(mask, jpeg_bytes)

        rgba = Image.merge("RGBA", (mask.point(lambda v: 255),) * 3 + (mask,))
        out = io.BytesIO()
        rgba.save(out, "PNG")
        return out.getvalue()

    def cutout_jpeg_to_png(self, jpeg_bytes):
        """输入一帧 JPEG，返回「人像透明背景」RGBA PNG（原始分辨率）。

        用 Accurate 档分割 + 原帧像素合成：人像区域保留原图，
        背景区域 alpha=0（透明），可直接作为 PNG 素材使用。
        """
        from Quartz import (
            CVPixelBufferLockBaseAddress, CVPixelBufferUnlockBaseAddress,
            CVPixelBufferGetBytesPerRow, CVPixelBufferGetWidth,
            CVPixelBufferGetHeight,
        )
        from PIL import Image

        V = self._Vision
        # 1) 读原帧
        frame = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
        # 2) Accurate 档分割
        data = self._NSData.dataWithBytes_length_(jpeg_bytes, len(jpeg_bytes))
        handler = V.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        req = V.VNGeneratePersonSegmentationRequest.alloc().initWithCompletionHandler_(None)
        req.setQualityLevel_(V.VNGeneratePersonSegmentationRequestQualityLevelAccurate)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(f"Vision 请求失败: {err}")
        results = req.results()
        if not results:
            raise RuntimeError("Vision 未返回分割结果")
        pb = results[0].pixelBuffer()
        CVPixelBufferLockBaseAddress(pb, 0)
        try:
            mw = CVPixelBufferGetWidth(pb)
            mh = CVPixelBufferGetHeight(pb)
            bs = CVPixelBufferGetBytesPerRow(pb)
            addr = self._cv.CVPixelBufferGetBaseAddress(pb.__c_void_p__())
            arr = (ctypes.c_ubyte * (bs * mh)).from_address(addr)
            lines = [bytes(arr[i * bs:i * bs + mw]) for i in range(mh)]
            mask = Image.frombytes("L", (mw, mh), b"".join(lines))
        finally:
            CVPixelBufferUnlockBaseAddress(pb, 0)
        # 3) mask 放大到原帧尺寸（双线性 → 软边缘），人像=原像素 / 背景=透明
        mask = mask.resize(frame.size, Image.BILINEAR)
        cut = frame.convert("RGBA")
        cut.putalpha(mask)
        out = io.BytesIO()
        cut.save(out, "PNG")
        return out.getvalue()
