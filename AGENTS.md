# AGENTS.md — MyWiki Agent Guide

## 项目概述

**MyWiki** — Personal Knowledge Wiki

MyWiki 是一个个人知识管理系统，同时作为多个 AI Agent 的共享知识中枢。它提供：

- Markdown 笔记管理（日记、项目、概念、人物）
- Obsidian Vault 双向同步
- MCP 协议暴露，供各类 AI Agent 读写
- RSS 聚合、RAG 语义检索、知识图谱可视化
- 视频分析、Memo 同步等扩展模块

## 不可变目录（只读）

以下目录包含用户内容，**Agent 不得修改、创建或删除其中的文件**：

| 目录 | 说明 |
|------|------|
| `brain/` | 知识库核心内容（概念、日记、项目、人物等） |
| `daily/` | 每日笔记与 RSS 聚合结果 |
| `wiki/` | Obsidian Vault 数据（含 `.obsidian/` 配置） |

这些目录的内容由用户通过 Obsidian 或同步模块管理，Agent 仅可**读取**，不可写入。

这条规则由 `tests/run_all.py` 强制：跑全套前后对这三个目录各做一次快照（只 stat）并比对，
任何用例真的写进了用户内容目录，运行器会指名打印该路径并以非零码退出。
实现见 `tests/_immutable_guard.py`，行为见 `tests/test_immutable_guard.py`。
写内容的测试请把目标重定向到临时目录（参考 `modules/shared-wiki/test_shared_wiki.py`
对 `wiki_core.WIKI_ROOT` 的做法）。

## 第三方前端运行时（`vendor/`）

`vendor/mediapipe/` 存放 MediaPipe Tasks Vision 与 Selfie Segmentation 的 JS/WASM，
与上游 npm 包逐字节一致，供 `face_mood_web.html` 同源加载。**只增不改**：升级请按
`vendor/README.md` 的方式整体重新下载，不要手改文件内容，也不要换回 CDN 引用——
本地网络环境下 CDN 不可达会让页面卡在「正在加载 MediaPipe 模型…」。
`tests/test_face_mood_web.py` 会守住「无外网 CDN 引用 + vendor 文件完整」。

## Python 代码约定

- **Python 版本**: 3.10+
- **编码**: UTF-8
- **风格**: 遵循 PEP 8，使用 4 空格缩进
- **依赖管理**: `requirements.txt`（通过 `pip install -r requirements.txt` 安装）
- **模块导入**: 使用相对路径或 `sys.path.insert` 引入 `modules/` 下的子模块
- **Frontmatter**: Markdown 文件使用 YAML frontmatter（需 `pyyaml`）
- **命令行入口**: 统一通过 `wiki_tool.py` 提供子命令
- **注释与文档**: 函数和模块需有 docstring，中文注释

## 测试命令

```bash
python tests/run_all.py              # Python 全部单元测试（自动发现 tests/ 与 modules/ 两处）
node --test "tests/**/*.test.mjs"    # Node 端纯逻辑测试
```

`tests/run_all.py` 按文件名自动发现两处测试：**本目录**的 `tests/test_*.py`，以及
与被测代码同目录的 **`modules/<模块>/test_*.py`**（如 shared-wiki 内核测试）。
**新增测试文件无需注册**，也不要在文档或 CI 中另行维护测试清单——手工清单会漏注册，
使失败测试被静默跳过。CI（`.github/workflows/ci.yml`）同样调用 `python tests/run_all.py`，
因此与该命令保持同源。

CI 的单元测试步骤在任何依赖安装之前运行，所以**测试用例只允许 import 标准库与仓库内一方
模块**；确需第三方库时，要在 `.github/workflows/ci.yml` 单元测试步骤前补 `pip install`。
`tests/test_ci_dependency_contract.py` 会逐个测试文件核对这件事，漏改在本地就报红，不用等
推送后 CI 失败。它只看测试文件自身的 import，看不出「用例 import 的一方模块再去 import
第三方库」——那一类由 `tests/test_ci_parity.py` 守住：它起一个子进程，把本机装了但 CI 没装的
第三方库全部拦成 `ModuleNotFoundError`，原样再跑一遍全套（约 +4s）。本地绿、这条红，就是
「推上去 CI 必红」，不用等真跑 CI。桌面端冒烟 `scripts/smoke_desktop_qt.py` 同理不得写坏被 git 跟踪的用户偏好
（`config/theme_pref.txt` 会重定向到临时目录）。

## 项目规格（SPEC.md）

改动**入口 / HTTP 路由 / 静态白名单 / 打包资源清单 / 版本号** 前，先看 [SPEC.md](SPEC.md)——它是可核对的硬契约：

- 打包必带资源（`assets/web/*`、`voice-controller.js`、`models/*.task`、`vendor/mediapipe/*`、每个 `*_web.html`、接口本地依赖）由 `tests/test_packaging_spec.py` 守门：**新增打包资源必须同步补一条断言**。
- HTTP 路由表（3.2 / 3.3）、静态文件白名单（3.4）、「版本号只在 `pyproject.toml`」（6.2）由
  `tests/test_spec_contract.py` 与 `web_server.py` / `MyWiki.spec` **双向**核对：改了路由或白名单
  就得同步改本文件，反之文档里多写一条实际不存在的路由（客户端只会拿到 404）同样会报红。
- 版本号单一数据源是 `pyproject.toml`；`MyWiki.spec` 的 `VERSION` 与 `BUNDLE` 必须引用它，不得硬编码。
- 另两份手工清单由 `tests/test_module_manifest_completeness.py` 守门：`pyproject.toml` 的
  `py-modules` 必须覆盖入口 import 闭包（漏一个 = 装完就 `ModuleNotFoundError`，盘上却一切正常）、
  不得留盘上已不存在的名字；`requires-python` 下限不得低于根模块实际用到的语法。
- 真机打包（`.venv/bin/pyinstaller MyWiki.spec`，~120s）是**发布前人工步骤**；CI 在 Ubuntu 上跑不了 macOS `.app`，故用符号执行替代。

## 模块边界说明

所有扩展模块位于 `modules/` 目录下，各子模块职责独立：

### `modules/shared-wiki/`
**共享知识内核**。提供 Wiki 读写 API（`wiki_core.py`）、Agent 自动发现（`agent_registry.py`）、Obsidian 桥接（`obsidian_bridge.py`）和 MCP Server（`mcp_server.py`）。这是所有 Agent 访问 Wiki 的统一入口。

### `modules/memo-sync/`
**Memo 双向同步**。将本地 Markdown 与 MemoAI 应用的 SQLite 数据库双向同步，支持 push / pull / list / search 操作。

### `modules/obsidian-sync/`
**Obsidian Vault 同步**。将 Wiki 内容同步到外部 Obsidian Vault（如 `~/Documents/Obsidian Vault/`），按目录映射保持一致，冲突时本地优先。

### `modules/a2a-agent/`
**A2A Agent 网络**。Google Agent-to-Agent 协议的本地节点，提供中央编排、本地推理、嵌入、3D 渲染等 Agent 的互联。项目代码不在本仓库内，此模块仅作文档索引。

### `modules/video-analysis/`
**视频分析**。通过 FFmpeg 提取关键帧，送入 Vision 模型逐帧分析，生成结构化 Markdown 报告并保存到 `daily/`。

### `modules/skills-loader/`
**技能加载器**。统一发现、查询、调用分布在 `~/AI Shared/skills` 下的各类 Agent 技能，提供 `list` / `show` / `run` 命令。
