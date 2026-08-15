# 阶跃星辰 Builder Program 申请表 — 填写草稿

> 页面：https://platform.stepfun.com/builder-program#application-form
> 项目：MyWiki（个人知识管理系统 / AI Agent 共享知识中枢）
> 生成日期：2026-08-14
>
> ⚠️ 标 ❓ 的字段需要你本人补充，其余字段已按项目实际情况填好，可直接复制。

---

## 字段对照表（按表单顺序）

### 1. 姓名
```
micheal
```

### 2. 邮箱
```
qm0819@hotmail.com
```

### 3. 联系方式（手机号或微信号）
```
284274167（微信号）
```

### 4. 组织 / 团队名称
```
个人开发者（Individual）
```
> 个人申请按页面提示填 "Individual"

### 5. 阶跃星辰开放平台 UID
```
371879105778618368
```

### 6. 项目 / 产品名称
```
MyWiki — 个人知识管理系统与 AI Agent 共享知识中枢
```

### 7. 使用的 StepFun 模型（多选，根据实际接入勾选）
```
[√] Step 3.5 Flash（Agent / RAG 问答）
[√] Step 3.7 Flash（多模态推理）
[√] Step-1o Turbo Vision（视频 / 图片理解）
[√] StepAudio 2.5 ASR（录音转写）
[  ] StepAudio 2.5 TTS（语音播报，可选）
[  ] Step 2X Large / Step Image Edit 2（配图生成，可选）
```

### 8. 过去 30 天模型用量 ❓
```
（如尚未接入可填：暂无，申请后接入；或填写实际 Token / 调用次数）
```

### 9. 希望解决的问题或达成的效果
```
个人知识管理长期存在"三座大山"：笔记散落多处（日记 / 概念 / 项目 /
Obsidian Vault / 聊天记录 / 会议妙记 / 录音），格式互不相同；信息有沉淀、
难被再次找到；且多个人 AI Agent 各自为政、无法共享同一份知识上下文。

MyWiki 希望把零散的个人信息统一收拢为一份"活的" Markdown 知识库，
让检索、问答、回顾都建立在同一份语义理解之上；同时作为多个 AI Agent
（QClaw、MCP 客户端等）的共享知识中枢，让 AI 真正"站在我的全部上下文里"
工作，而不是每次从零开始。

接入 StepFun 后，期望达成：
- 用多模态/推理模型把"检索 + 理解 + 生成"下沉到知识库问答、会议纪要、周报
  摘要等真实场景；
- 让本机录音转写、视频分析等低频重活从"本地死数据"变成"可被追问的知识"。
```

### 10. 想在什么地方用到 StepFun 模型
```
1) RAG 知识库问答与摘要：用 Step 3.5/3.7 Flash 对 wiki 笔记做语义检索、
   跨笔记问答、每日/每周自动摘要（现有 RAG 引擎的 BM25 基础上叠加 LLM 理解）。
2) 多源内容理解：Step-1o Turbo Vision 用于会议截图、视频关键帧分析
   （现有 video-analysis 模块逐帧送 Vision 模型），把视频/图片内容转成
   结构化 Markdown 笔记。
3) 语音转写：StepAudio 2.5 ASR 接入多源上下文采集（scripts/collect_context.py
   的 recordings 来源），本机录音转写后落入共享 vault，供检索与问答。
4) 人机交互增强（可选）：StepAudio 2.5 TTS 做语音提醒播报；Step 2X Large
   为知识图谱 / 日记自动生成配图封面。
```

### 11. 目前进展
```
项目已完成并可本地运行（macOS 桌面端 + 网页版，Python 后端 + 前端单页应用）：

- 笔记管理：Markdown 日记 / 概念 / 项目 / 人物，YAML frontmatter，知识图谱
  可视化（knowledge_graph.json）。
- Obsidian Vault 双向同步：wiki/ 目录与外部 Vault 保持映射一致。
- MCP 协议接入：modules/shared-wiki/mcp_server.py 暴露统一读写 API，供各类
  AI Agent 读写知识库。
- RAG 语义检索：BM25 + 缓存 + 中文分词，已实现并测试通过。
- 多源上下文采集：scripts/collect_context.py 每日采集飞书聊天、企业微信、
  飞书会议妙记、本机录音 → 写入共享 Obsidian vault（增量拉取、无变化跳过、
  单源失败不阻断、企微自动退避）。
- 面部情绪识别网页版（face_mood）：浏览器端 MediaPipe 人脸检测 + 情绪识别，
  结果落盘 mood/ 目录。
- 测试：tests/run_all.py 全量 116 项通过。

尚未接入任何外部 LLM 供应商 API；StepFun 将作为第一个正式接入的推理/多模态
提供商，重点打通"采集 → 理解 → 沉淀 → 问答"闭环。
```

### 12. Github / Demo / 仓库 / 链接
```
Gitee: https://gitee.com/cpufreestyle/my-wiki
GitHub: https://github.com/cpufreestyle/my-wiki
（本地 Demo 可提供；如需可录制网页版演示视频）
```

### 13. 其他想告诉我们的
```
我是长期个人开发者，做 MyWiki 是因为自己确实有"信息进来很多、想再找到却
很难"的痛点，并希望把它做成多 AI Agent 共享的私人知识底座。StepFun 的多
模态 + 语音能力正好补上我目前最缺的三块：视频/图片理解、录音转写、更聪明
的语义问答。申请 Builder Program 后，我会优先把 2、3 两条（视觉理解 + ASR
转写）落地到真实每日使用流程里，并愿意把接入经验写成文档/示例回馈社区。
```

---

## 提交前确认清单
- [ ] 补充姓名、邮箱、联系方式、UID、过去 30 天用量
- [ ] 按实际勾选"使用的 StepFun 模型"
- [ ] 确认同意用户协议与隐私政策（页面声明数据不会用于模型训练）
