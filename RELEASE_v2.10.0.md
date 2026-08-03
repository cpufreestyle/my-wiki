# MyWiki v2.10.0 — 采集器优化 + 工程化增强

> 本文件记录 v2.9.0 之后的累计变更。本次为**优化与工程化版本**：聚焦多源上下文采集器（v2.9.0 新增）的增量拉取、无谓写入消除、企业微信退避与频率收敛；同时补齐构建配置（`pyproject.toml`）、Agent 协作指南（`AGENTS.md`）、RSS 订阅配置与两套核心模块单元测试，为后续可维护性与打包分发打底。

## ✨ 核心改进

### 多源上下文采集器优化（`scripts/collect_context.py`）

基于 5 轮实跑（`13/0/1/0` 稳定）暴露的浪费点，做四项优化：

1. **增量拉取**：每会话在笔记 frontmatter 持久化 `last_synced`（上次同步到的最新消息时间），下一轮仅拉取该时间之后的增量，告别每轮全量 7 天窗口。
   - 关键修复：原 append 模式只追加正文、**丢弃 meta，导致 `last_synced` 每轮读回都是 `None`、增量形同虚设**。已新增 `_merge_frontmatter()` 在追加后把 `last_synced` 等字段写回 frontmatter，并经两轮实跑验证窗口已收窄。
2. **无变化跳过写入**：正文内容一致时直接 `[skip] 无变化`，不再每轮刷新 mtime 触发 Obsidian 无谓同步。
3. **企业微信退避与失败区分**：显式区分「CLI 调用失败（未登录 / 授权过期 / 网络异常）」与「真·无会话」；连续 3 次无数据时进入**每日退避**（当日不再重试），状态存于 `config/.collect_backoff.json`（已加入 `.gitignore`）。
4. **采集频率收敛**：自动化由每 4 小时一次降为每日一次（`rrule: FREQ=DAILY;INTERVAL=1`），配合增量拉取进一步降低 CLI 调用开销。

特性保持不变：幂等去重（原地更新）、标准 frontmatter、故障隔离、支持 `--dry-run`。

```bash
python3 scripts/collect_context.py              # 默认最近 7 天（增量）
python3 scripts/collect_context.py --days 3     # 指定窗口
python3 scripts/collect_context.py --dry-run    # 只看不写
```

### 工程化

- **新增 `pyproject.toml`**：setuptools 构建配置、运行时依赖声明，并暴露命令行入口 `mywiki`（`wiki_tool:main`）、桌面 GUI 入口 `mywiki-app`（`wiki_app:main`）、本地服务入口 `mywiki-server`（`web_server:main`）。
- **入口重构**：`wiki_app.py` / `web_server.py` 将 `if __name__ == "__main__"` 块抽取为 `main()`，与 `pyproject.toml` 的入口声明对齐，便于程序化调用与打包。
- **新增 `AGENTS.md`**：项目 Agent 协作指南——不可变目录边界、Python 代码约定、各扩展模块职责说明。
- **新增 `config/rss_feeds.json`**：RSS 聚合订阅源配置（Hacker News / GitHub Blog / MIT Tech Review / Real Python / Planet Python / OpenAI / Anthropic / Python Insider 共 8 源，按 `tech` / `python` / `github` 打标签，可单独启停）。

### 测试

- **新增 `tests/test_rag.py`**：`rag.py` 纯逻辑单测，覆盖 `tokenize` / `cosine` / `chunk_text` / `RAGEngine.search`（BM25），纯标准库、无第三方依赖（27 cases）。
- **新增 `tests/test_reminder_manager.py`**：`reminder_manager.py` 纯逻辑单测，mock 替换 Windows 专属调用与硬编码路径，在 macOS/Linux 验证 `load` / `save` / `add` / `cancel` / `get_pending` / `preset`（14 cases）。
- **`tests/run_all.py`** 已接入上述两套新测试。

## 🐛 关键修复

- **采集器增量失效**：append 模式未将 `last_synced` 等 meta 写回 frontmatter，导致每轮退化为全量拉取（见上文「增量拉取」）。
- **`.gitignore`**：新增 `config/.collect_backoff.json`（采集器退避状态）与 `.qoder/`（工具缓存），二者均属本机运行态、非仓库产物。

## 📦 完整变更清单

### 新增文件

- `pyproject.toml`：构建与入口配置（version 2.10.0）
- `AGENTS.md`：Agent 协作指南
- `config/rss_feeds.json`：RSS 订阅源配置
- `tests/test_rag.py`：RAG 核心逻辑单测
- `tests/test_reminder_manager.py`：提醒管理器单测
- `RELEASE_v2.10.0.md`：本发布文档

### 修改文件

- `scripts/collect_context.py`：增量拉取 + 跳过无变化 + 企微退避 + meta 持久化修复
- `web_server.py`：抽取 `main()` 入口
- `wiki_app.py`：抽取 `main()` 入口
- `tests/run_all.py`：接入 `test_rag` / `test_reminder_manager`
- `.gitignore`：忽略退避状态与 `.qoder/`
- `README.md`：版本徽章与目录说明更新至 v2.10.0

## ⚡ 升级指南

```bash
cd my-wiki
python -m pip install -r requirements.txt

# 如需以可安装包方式使用（可选）
pip install -e .            # 提供 mywiki / mywiki-app / mywiki-server 命令
mywiki-server               # 启动本地 Web 服务
mywiki-app                  # 启动桌面 GUI

# 启用上下文采集（可选）
cp config/examples/collect_context.example.json config/collect_context.json
python3 scripts/collect_context.py --dry-run   # 先预演确认

# 启用 RSS 聚合（可选）
# 编辑 config/rss_feeds.json 启停订阅源后由对应模块加载
```

**采集功能前置条件**：本机需已安装并登录 `lark-cli` / `wecom-cli`；录音转写需 `pip install openai-whisper`。未启用的来源在配置中置 `false` 即可跳过。

**建议**：采集脚本已配置为每日一次定时任务（增量拉取），无需再高频轮询。

---

### 历史版本参考

- v2.9.0：多源上下文采集 + 网页版一体化（采集脚本 / 桌面内置网页版 / 知识图谱与 RAG 页）
- v2.8.0：稳定性、兼容性与工程化增强（wiki-root 解析修正 / Obsidian 多盘符检测 / 桌面端 CI 冒烟）
- v2.7.0：PySide6 迁移 + 语音声学分析增强
- v2.6.0：网页版功能扩展（日记/心情网页版）
- v2.5.0：三端配色对齐 + 录音权限修复
