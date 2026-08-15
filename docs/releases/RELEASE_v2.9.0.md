# MyWiki v2.9.0 — 多源上下文采集 + 网页版一体化

> 本文件记录 v2.8.0 之后的累计变更。本次为**功能性版本**：新增多源上下文自动采集（飞书/企业微信聊天、飞书会议妙记、本地录音转写 → 共享 Obsidian vault），桌面端内置网页版一键直达，网页端补齐知识图谱与 RAG 检索页面，并修复 macOS 代码签名打包被 Gatekeeper 拦截的问题。

## ✨ 核心新功能

### 多源上下文自动采集

新增 `scripts/collect_context.py`，把散落在各个 IM / 会议系统里的上下文统一沉淀进共享 Obsidian vault，供 QClaw 记忆系统与 Obsidian 双向联动。

| 来源 | 采集方式 | 落地目录 |
|---|---|---|
| 飞书聊天 | `lark-cli`（复用本机已登录态） | `chat/` |
| 企业微信聊天 | `wecom-cli`（复用本机已登录态） | `chat/` |
| 飞书会议妙记 | `lark-cli` minutes | `meetings/` |
| 本机录音 | `whisper` CLI 转写 mp3/m4a/wav | `recordings/` |

特性：

- **无需自建应用凭证**：直接复用本机 QClaw 已登录的 CLI，省去 app id/secret 配置与授权维护
- **幂等去重**：按 `chat_id` / `conversation_id` / `minute_token` 匹配，重复采集**原地更新**已有笔记而非堆叠副本
- **标准 frontmatter**：每篇笔记带 `source` / `category` / `date` / `tags` 等字段，Obsidian 与 RAG 均可直接索引
- **故障隔离**：单一来源授权过期或网络失败只记录错误，不阻断其余来源
- **时间窗可调**：聊天默认最近 7 天（`--days N`），妙记默认 14 天（配置项 `feishu_meeting.days`）
- **支持 `--dry-run`**：预演采集结果而不写盘

```bash
python3 scripts/collect_context.py              # 默认最近 7 天
python3 scripts/collect_context.py --days 3     # 指定窗口
python3 scripts/collect_context.py --dry-run    # 只看不写
```

### 桌面端内置网页版

- 启动 `wiki_app.py` 时**自动拉起 web_server**：打包态用守护线程内嵌启动，源码态起子进程并优先选用 `.venv` 解释器
- 顶栏新增「🌐 网页版」按钮，一键在浏览器打开；应用退出时自动清理服务进程
- 缺少 PySide6 时给出明确的 `.venv` 启动指引（终端输出 + 弹窗双提示），不再静默失败

### 网页端新页面

- **知识图谱页** `graph_web.html`：可视化知识关联
- **RAG 检索页** `rag_web.html`：语义检索入口
- **导航动态渲染**：`index.html` 改为从新增的 `GET /api/modules` 拉取模块列表，服务端依据 `MODULE_REGISTRY` 扫描 `*_web.html` 真实存在性，只返回可用模块 —— 新增/删除页面入口自动同步，无需手改首页；离线（`file://`）时降级为默认静态卡片，避免白屏

## 🐛 关键修复

- **macOS 代码签名被破坏导致 Gatekeeper 拦截**：`modules/shared-wiki` 此前被打进签名包内，运行时写入 `registry.json` 会破坏代码签名密封。现已移出签名包；知识图谱数据同步改用用户目录可写副本，不再写入包内资源
- **签名配置外提**：`MyWiki.spec` 抽出 `codesign_identity` / `entitlements_file` 配置项，新增 `MyWiki.entitlements`

## 📦 完整变更清单

### 新增文件

- `scripts/collect_context.py`：多源上下文采集脚本
- `config/examples/collect_context.example.json`：采集配置示例（真实配置 `config/collect_context.json` 已加入 `.gitignore`）
- `MyWiki.entitlements`：macOS 签名 entitlements
- `graph_web.html`、`rag_web.html`：知识图谱页与 RAG 检索页
- `tests/test_graph_web.py`、`tests/test_rag_web.py`：对应测试
- `RELEASE_v2.9.0.md`：本发布文档

### 修改文件

- `wiki_app.py`：自动拉起 web_server、「🌐 网页版」按钮、退出清理、PySide6 缺失指引
- `web_server.py`：抽出 `make_server()` 支持 GUI 进程内启动（不 chdir）、新增 `GET /api/modules`、图谱数据改用用户目录可写副本
- `MyWiki.spec`：移除 `modules/shared-wiki` 打包、抽出签名配置、版本号 → 2.9.0
- `index.html`：导航改为动态渲染 + 离线降级
- `.gitignore`：忽略 `config/collect_context.json`、`.codebuddy/`
- `README.md`：版本号更新至 v2.9.0
- `tests/run_all.py`、`tests/test_index.py`：接入新测试

## ⚡ 升级指南

```bash
cd my-wiki
python -m pip install -r requirements.txt

# 启用上下文采集（可选）
cp config/examples/collect_context.example.json config/collect_context.json
# 按需编辑：开关各来源、调整 vault 路径与时间窗
python3 scripts/collect_context.py --dry-run   # 先预演确认

# 启动应用（网页版会自动拉起）
python wiki_app.py
```

**采集功能前置条件**：本机需已安装并登录 `lark-cli` / `wecom-cli`；录音转写需 `pip install openai-whisper`。未启用的来源在配置中置 `false` 即可跳过。

**建议**：可将采集脚本配置为定时任务（如每 4 小时一次）持续沉淀上下文。

---

### 历史版本参考

- v2.8.0：稳定性、兼容性与工程化增强（wiki-root 解析修正 / Obsidian 多盘符检测 / 桌面端 CI 冒烟）
- v2.7.0：PySide6 迁移 + 语音声学分析增强
- v2.6.0：网页版功能扩展（日记/心情网页版）
- v2.5.0：三端配色对齐 + 录音权限修复
