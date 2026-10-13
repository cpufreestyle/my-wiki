# SPEC.md — MyWiki 项目契约规格

> 本文档记录**可核对的契约**：进程入口、HTTP 路由、目录边界、打包资源清单、验收命令。
> 它是「改代码时必须守住什么」的清单，不是使用教程——使用说明见 [README.md](README.md)，
> Agent 协作规则见 [AGENTS.md](AGENTS.md)。
>
> 写作原则：**每条契约都指向仓库里可执行或可断言（assert）的源码/测试**，不写无法验证的描述。
> 契约与实现冲突时，以本文档 + 对应测试为准，先改实现再改文档。

---

## 1. 项目定位与技术栈

MyWiki 是个人知识库系统，同时作为多个 AI Agent 的共享知识中枢。三种形态共用同一份核心代码：

- **桌面端**：PySide6 GUI（日记 / 心情 / 提醒 / 待办 / 搜索 / 标签 / 报告）
- **网页端**：标准库 http.server 提供的本地 Web UI（端口 8082）
- **CLI**：wiki_tool.py 子命令

| 项 | 值 |
|---|---|
| Python | >= 3.9（CI 用 3.12） |
| 版本号 | pyproject.toml 的 [project].version（**唯一数据源**） |
| 许可证 | MIT |
| 依赖 | 见 requirements.txt / pyproject.toml |

---

## 2. 三个可执行入口

定义于 pyproject.toml，是唯一权威来源：

| 命令 | 目标 | 形态 |
|---|---|---|
| mywiki | wiki_tool:main | CLI |
| mywiki-app | wiki_app:main | 桌面 GUI（PySide6） |
| mywiki-server | web_server:main | 本地 Web 服务器 |

### CLI 子命令契约（wiki_tool.py）

update / daily / search <query> / capture <文本> / links <笔记> / backlinks <笔记> / orphans / publish [--root DIR] [--out DIR] [--clean] [--source a,b] [--name X] / clip <url> [--title T] / review / cards / digest [YYYY-MM-DD] [--no-ai]。

注意：内置子命令**不认 --help**，无参数或 help 时才打印用法；未知命令打印
[ERROR] 未知命令: <x> 后附用法。publish / clip / review / cards / digest 五个子命令
委托各自 argparse，支持 --help。由 tests/test_wiki_links.py 冒烟覆盖。

---

## 3. Web 服务契约（web_server.py）

### 3.1 监听与端口

- 默认端口 **8082**：main() 取 sys.argv[1]（可解析为 int 时）覆盖默认值。
- 启动脚本 scripts/launch_web.sh 读环境变量 MYWIKI_PORT（默认 8082）。
- 桌面端 wiki_app.py 关闭时会一并停止后台 Web 服务（同生命周期）。

### 3.2 GET 路由

| 路径 | 作用 |
|---|---|
| / 、 /index.html | 门户页 |
| /favicon.ico | 204 空响应（避免控制台 404 噪声） |
| /api/rag | 语义检索（BM25 / Ollama embedding） |
| /api/graph | 知识图谱数据 |
| /api/modules | 模块清单 |
| /api/mood/range | 按日聚合心情（?days=N），供情绪报表 |
| /api/vision/status | 人像分割后端可用性 |
| /api/health | 健康检查 |
| /api/face/camera | 摄像头占用/权限/取图自检 |
| /api/face/deps | 面部后端各依赖（mediapipe / cv2 / Vision）可用性 |
| /api/todos | 待办列表 |

### 3.3 POST 路由

| 路径 | 作用 |
|---|---|
| /api/voice/start | 开始录音（duration 有上下限钳制） |
| /api/voice/stop | 停止并等待识别（最长 30s） |
| /api/qa | 问答（依赖 llm_qa.py） |
| /api/mood | 心情记录 |
| /api/face_mood | 面部情绪记录（source=auto 为自动采集） |
| /api/vision/segment | 单帧 JPEG → 人像 alpha mask（RGBA PNG） |
| /api/vision/cutout | 人像抠图 |
| /api/face/mood | 摄像头抓帧做面部情绪识别 |
| /api/todos | 新增/更新待办 |

未知路径一律 404。

### 3.4 静态文件白名单

服务器以**仓库根**作为静态目录（directory=ROOT），因此必须限制可下载范围——
否则局域网内任何人可拉取 .git/HEAD、config/（含本机绝对路径）与全部源码。

- 放行目录：STATIC_ALLOWED_DIRS = ("assets", "models", "vendor")
- 放行扩展名：.html .js .css .json .png .jpg .jpeg .gif .svg .ico .task .woff .woff2 .ttf
- 隐藏文件/目录（.git、.venv 等）与 .. 穿越**一律 403**。

改动此白名单等于放宽攻击面，必须同步更新 tests/test_web_server.py。

---

## 4. 目录边界（可写 / 只读）

| 目录 | 权限 | 说明 |
|---|---|---|
| brain/ daily/ wiki/ | **只读** | 用户内容（概念/日记/项目/Obsidian Vault）。Agent 不得创建、修改、删除 |
| vendor/mediapipe/ | **只增不改** | 第三方运行时，与上游逐字节一致；升级按 vendor/README.md 整体重下，禁止手改、禁止改回 CDN |
| backups/ dist/ build/ logs/ __pycache__/ | 生成物 | 不入库 |

根目录新增 wiki_*.py 前需确认**不与 modules/ 下模块重名**：modules/shared-wiki/ 已有
wiki_core.py，根目录同名会被 sys.modules 缓存遮蔽导致加载错模块。

---

## 5. 扩展模块（modules/）

| 模块 | 职责 | 主要入口 |
|---|---|---|
| shared-wiki/ | 共享知识内核（所有 Agent 访问 Wiki 的统一入口） | wiki_core.py / agent_registry.py / obsidian_bridge.py / mcp_server.py |
| memo-sync/ | 本地 Markdown ↔ MemoAI SQLite 双向同步 | sync.py（push/pull/list/search） |
| obsidian-sync/ | Wiki → 外部 Obsidian Vault 目录映射同步 | sync.py（冲突时本地优先） |
| a2a-agent/ | A2A 协议节点索引 | 代码不在本仓库，仅文档 |
| video-analysis/ | FFmpeg 抽关键帧 → Vision 逐帧分析 → Markdown 报告 | analyze.py |
| skills-loader/ | 发现/查询/调用 ~/AI Shared/skills 下技能 | loader.py（list/show/run） |

---

## 6. 打包契约（MyWiki.spec）

打包版把 web_server.py 及其本地依赖当作**数据文件**塞进 .app 资源目录。
PyInstaller 的静态分析**不跟踪数据文件里的 import**，因此漏列即静默降级：
页面裸样式、接口 404、面部识别只能联网下载模型。以下清单是硬契约。

### 6.1 必带资源清单

| 资源 | 打包目标 | 缺失后果 |
|---|---|---|
| assets/web/*（theme.js、apple-ui.css） | assets/web | 全部页面裸样式（9 个 HTML 都 link 它） |
| voice-controller.js | . | mood/daily/reminder/rag 四页语音输入失效 |
| models/*.task | models | face_mood.py 无关键点模型，只能运行期下载 |
| vendor/mediapipe/*（整棵树） | vendor/mediapipe | 面部页卡在「正在加载 MediaPipe 模型…」，离线不可用 |
| 每个 *_web.html + index.html | . | 对应页面 404 |
| llm_qa.py face_mood.py vision_face_mood.py wiki_paths.py wiki_data.py wiki_i18n.py | . | /api/qa、面部接口、路径/数据层静默降级 |

hiddenimports 还需显式列出原生重依赖（cv2 mediapipe numpy Vision Quartz PIL）
与本地运行时模块，否则裸机启动崩溃。

### 6.2 版本单一数据源

pyproject.toml 的 [project].version 是唯一数据源；MyWiki.spec 的 VERSION 常量
须与之相等，且被 BUNDLE(version=...) 与 info_plist['CFBundleShortVersionString']
共同引用（此前是硬编码 2.9.0，与 README 的 2.10.1 漂移，用户无法判断装的是哪版）。

### 6.3 为什么不打包 modules/shared-wiki/ 进签名包

该目录含运行时会写入的 registry.json 等可变数据，打进签名 app 会破坏代码签名密封
（"a sealed resource is missing or invalid"），双击被 Gatekeeper 拦截。改为运行时按
五级查找回退加载：仓库根 → MYWIKI_SOURCE_DIR → Application Support 用户副本 →
_MEIPASS 拷到用户目录 → 开发机路径兜底。**保持「只读打包 + 运行时拷贝」模式**。

---

## 7. 验收 harness

### 7.1 本地两条命令（提交前必跑）

    python tests/run_all.py              # Python 全套（自动发现 tests/test_*.py）
    node --test "tests/**/*.test.mjs"    # Node 端纯逻辑（从 HTML 抽取函数运行）

run_all.py 按文件名**自动发现** test_*.py：**新增测试文件无需注册**，
也不要在文档或 CI 里另维护测试清单——手工清单会漏注册，使失败测试被静默跳过。

### 7.2 冒烟脚本

    QT_QPA_PLATFORM=offscreen python scripts/smoke_desktop_qt.py

等价复刻 wiki_app.py 的 __main__ 启动链路（QApplication → apply_qss → WikiApp →
WelcomeDialog），无头验证界面构建、QSS、语音信号槽、主题/语言切换、MCP 启动、
标签页滚动区包裹与小窗卡片叠放。

### 7.3 CI（.github/workflows/ci.yml）

push / PR 到 main 时依次执行：Python 3.12 + Node 20 → run_all.py →
node --test → 装 libgl1/libglib2.0-0/libegl1/libdbus-1-3 + PySide6 →
冒烟脚本 → python rag.py "本地模型 ollama 配置" --limit 3（BM25 零依赖）→
python -c "import theme; assert theme.LIGHT and theme.DARK"。

### 7.4 打包校验为何用符号执行而非真机构建

CI 跑在 Ubuntu，无法产出 macOS .app；真机构建又需 ~120s 且依赖 PyInstaller。
因此 tests/test_packaging_spec.py 用**哑 PyInstaller 符号执行 spec**（占位
Analysis/PYZ/EXE/COLLECT/BUNDLE 捕获实参），断言 datas 覆盖 §6.1 清单、
hiddenimports 覆盖本地模块与原生依赖、VERSION 与 pyproject.toml 一致。
真实构建作为**发布前人工步骤**（.venv/bin/pyinstaller MyWiki.spec）执行。

---

## 8. 已知限制与降级策略

**设计上允许缺失、运行期降级**（因此打包日志里这 4 条 ERROR 可接受：
Hidden import 'mcp_server'/'watchdog'/'watchdog.observers'/'watchdog.events' not found）：

| 缺失依赖 | 降级行为 |
|---|---|
| mcp | mcp_server.py 退化为 JSON-RPC stdio |
| watchdog | obsidian_bridge.py 退化为轮询 |
| SpeechRecognition | 语音接口返回不可用；语音识别需联网 |
| static-ffmpeg | 依赖系统 ffmpeg |
| pyobjc Vision（非 macOS） | /api/vision/segment 返回 503，前端降级浏览器端 MediaPipe |
| cv2 / mediapipe | /api/face/deps 报告 mediapipe_usable=false，面部页面禁用 |

其他已知约束：

- **前置摄像头整条管线统一镜像**（自拍惯例）：drawImage(video, w, 0, -w, h) 水平翻转 +
  detect 后 landmark x→1-x。新增任何 video 绘制/坐标计算必须镜像同源，否则运动补偿与
  抠图方向错乱。
- 网页主题统一走 assets/web/theme.js（localStorage mywiki-theme），**勿再内联**。
- backups/ 中的备份 zip 已 gitignore；情绪报表依赖 /api/mood/range 的
  {date, count, moods{}} 聚合格式。

---

## 9. 修改本文件的规则

改动以下任一项时，**必须同步更新 SPEC.md 对应小节**：入口（§2）、路由与白名单（§3）、
打包资源清单（§6）、验收命令（§7）。若新增资源被打进 .app，请同时补一条
tests/test_packaging_spec.py 断言——契约没有测试守门就等于没有契约。
