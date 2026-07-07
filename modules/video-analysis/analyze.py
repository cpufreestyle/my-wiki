#!/usr/bin/env python3
"""
video analysis 模块入口 — 调用 OpenClaw video-analysis skill

Usage:
    python analyze.py <video_path> [--interval 30] [--title "标题"] [--output-dir DIR]

流程: ffprobe → ffmpeg 帧提取 → 关键帧采样 → Vision 分析 → Markdown 报告
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

MODULE_DIR = Path(__file__).parent
WIKI_ROOT = MODULE_DIR.parent.parent


def probe_video(video_path):
    """获取视频元数据"""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ ffprobe failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def extract_frames(video_path, output_dir, interval=30):
    """提取关键帧"""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vf", f"fps=1/{interval},scale=1280:-1",
        "-q:v", "3",
        str(output_dir / "frame_%04d.jpg")
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    frames = sorted(output_dir.glob("frame_*.jpg"))
    return frames


def sample_key_frames(frames, count=13):
    """均匀采样关键帧"""
    if len(frames) <= count:
        return frames
    step = len(frames) / count
    indices = [int(i * step) for i in range(count)]
    # 确保最后一帧包含
    if indices[-1] != len(frames) - 1:
        indices.append(len(frames) - 1)
    return [frames[i] for i in indices]


def generate_report(video_path, metadata, key_frames, title=None):
    """生成分析报告框架（实际分析由 OpenClaw Vision 完成）"""
    fmt = metadata.get("format", {})
    duration = float(fmt.get("duration", 0))
    
    streams = metadata.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    
    md = f"""# {title or Path(video_path).stem} — 视频分析报告

**视频文件**: `{video_path}`
**时长**: {duration:.0f}s ({duration/60:.1f} 分钟)
**分辨率**: {video_stream.get('width', '?')}x{video_stream.get('height', '?')}
**视频编码**: {video_stream.get('codec_name', '?')}
**音频编码**: {audio_stream.get('codec_name', '?')}
**分析日期**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**分析方法**: FFmpeg 提取{len(key_frames)}关键帧 → Vision 逐帧分析

---

## 关键帧列表

"""
    for i, frame in enumerate(key_frames):
        timestamp = i * 30  # approx
        md += f"- Frame {i+1} ({timestamp//60}m{timestamp%60}s): `{frame.name}`\n"
    
    md += """
---

## 分析内容

（由 OpenClaw Vision 模型逐帧分析后填充）

"""
    return md


def main():
    parser = argparse.ArgumentParser(description="Video Analysis Module")
    parser.add_argument("video", help="Video file path")
    parser.add_argument("--interval", type=int, default=30, help="Frame interval in seconds")
    parser.add_argument("--title", help="Report title")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    video_path = Path(args.video).expanduser()
    if not video_path.exists():
        print(f"❌ Video not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📹 Analyzing: {video_path.name}")
    
    # 1. Probe
    metadata = probe_video(video_path)
    fmt = metadata.get("format", {})
    duration = float(fmt.get("duration", 0))
    print(f"  Duration: {duration:.0f}s ({duration/60:.1f} min)")
    
    # 2. Extract frames
    output_dir = Path(args.output_dir) if args.output_dir else WIKI_ROOT / "attachments" / video_path.stem
    frames = extract_frames(video_path, output_dir, args.interval)
    print(f"  Frames extracted: {len(frames)}")
    
    # 3. Sample key frames
    key_frames = sample_key_frames(frames)
    print(f"  Key frames sampled: {len(key_frames)}")
    
    # 4. Generate report skeleton
    report = generate_report(video_path, metadata, key_frames, args.title)
    
    report_path = WIKI_ROOT / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}-{video_path.stem}-analysis.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report: {report_path}")
    print(f"\n✅ Frame extraction complete. Use OpenClaw image tool to analyze key frames.")
    print(f"   Key frames: {output_dir}")


if __name__ == "__main__":
    main()
