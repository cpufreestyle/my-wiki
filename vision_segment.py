#!/usr/bin/env python3
"""vision_segment.py — macOS Vision 人物分割（Apple 官方虚化同款技术）

通过 PyObjC 调用 VNGeneratePersonSegmentationRequest（macOS 11+ 系统自带，
FaceTime 人像 / 照片虚化背后的分割引擎，GPU 加速、无需下载模型），
把一帧 JPEG 解码后生成人像 alpha mask（RGBA PNG，白底 alpha=mask），
供网页端 destination-in 抠图合成。

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

    def segment_jpeg_to_png(self, jpeg_bytes):
        """输入一帧 JPEG，返回人像 alpha mask 的 RGBA PNG 字节。

        RGB 通道恒为白、alpha=mask，前端 drawImage + destination-in 即得抠图。
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
        # Balanced：约 10-20ms/帧（M 系列），精度接近 Accurate
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

        rgba = Image.merge("RGBA", (mask.point(lambda v: 255),) * 3 + (mask,))
        out = io.BytesIO()
        rgba.save(out, "PNG")
        return out.getvalue()
