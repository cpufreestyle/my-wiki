# Video Analysis Skill 创建

**时间**: 2026-07-08 00:08-00:13 GMT+8

## 背景
用户要求将 aipmday.mp4 视频分析流程做成可复用 skill。

## 回顾的完整流程
1. FFmpeg 提取关键帧（每 30 秒一帧，200 张 JPEG）
2. Whisper 音频转写尝试（因网络/模型问题失败）
3. 帧复制到 workspace 可访问路径
4. Vision 模型分批逐帧分析（前半段 5 帧 + 后半段 6 帧）
5. 综合分析生成结构化报告
6. A2A 网络尝试调用 StepFun 深度分析（超时）

## 创建的 Skill

### 文件结构
```
~/.qclaw/skills/video-analysis/
├── SKILL.md                    # Skill 定义和工作流指引
└── scripts/
    └── analyze_video.py        # 核心管线脚本 (10.7KB)
```

### analyze_video.py 功能
- **Step 1**: ffprobe 探测视频元数据 → `video_meta.json`
- **Step 2**: ffmpeg 提取 16kHz 单声道 WAV → `audio.wav`
- **Step 3**: ffmpeg 按间隔提取关键帧 → `frames/frame_XXXX.jpg`
- **Step 4**: 可选 Whisper 转写（transformers pipeline → openai-whisper CLI 两级降级）
- **Step 5**: 生成 `analysis_ready.json` 汇总文件

### 参数
- `--frame-interval N`: 帧间隔秒数（默认 30）
- `--output-dir`: 输出目录
- `--skip-audio` / `--skip-frames` / `--skip-transcribe`: 跳过对应步骤

### 测试
- 合成 10 秒测试视频端到端验证通过
- 元数据提取 ✅
- 音频提取 ✅
- 帧提取 ✅ (2 帧)
- summary JSON 生成 ✅

### 分发
- 打包为 `video-analysis.skill`
- 推送到 Gitee skillhub 仓库 (commit 2f6f848)
- skillhub manifest 更新为 102 skills

## 设计决策
1. **脚本只做提取，不做分析** — Vision/LLM 分析由 OpenClaw agent 按 SKILL.md 工作流执行，保持灵活性
2. **帧采样策略写在 SKILL.md** — 根据视频时长动态选择，不在脚本中硬编码
3. **workspace 路径限制** — SKILL.md 明确提醒需将帧复制到 workspace 下才能用 image 工具
4. **转写可选** — 两级降级策略，失败不阻塞流程
