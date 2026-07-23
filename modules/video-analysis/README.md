# Video Analysis 模块

将视频文件通过 FFmpeg 提取关键帧 → Vision 模型逐帧分析 → 生成结构化 Markdown 报告。

## 依赖

- **FFmpeg**: 视频帧提取（`brew install ffmpeg`）
- **OpenClaw image 工具**: Vision 逐帧分析

## 使用

```bash
# 通过 wiki_tool.py
python wiki_tool.py video <video_path> [--interval 30] [--title "标题"]

# 直接调用 skill
# 参考 ~/.qclaw/skills/video-analysis/SKILL.md
```

## 流程

1. `ffprobe` 获取视频元数据（时长、分辨率、编码）
2. `ffmpeg` 按间隔提取帧（默认每30秒一帧）
3. 均匀采样 12-15 张关键帧
4. 分批送入 Vision 模型逐帧分析
5. 生成结构化 Markdown 报告
6. 保存到 `daily/` 并推送到 Obsidian Vault

## 文件

- `analyze.py`: 视频分析入口脚本
- `README.md`: 本文件
