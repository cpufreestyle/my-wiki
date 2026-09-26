

## Codely Structured Memories

### User

### Feedback

### Project
- [2026-08-15 23:26:32] MyWiki 用户习惯：任务完成后期望主动提出 commit（中文 conventional 风格）并 push 到远程 gitee (cpufreestyle/my-wiki)。**Why:** 前两轮任务用户均确认"提交并推送"。**How to apply:** 完成代码任务后主动给出 commit message 草稿并询问是否 push。
- [2026-08-15 23:26:32] MyWiki 测试环境：本机未安装 Node.js（node: command not found），tests/run_all.py 仅运行 Python 测试；tests/*.logic.test.mjs 无 JS 运行器可执行。**Why:** 2026-08-15 验证 face_mood 改动时发现。**How to apply:** 验证 JS 改动用括号配对/结构性 Python 测试，勿尝试 node 命令。
- [2026-08-16 14:32:13] 拆分 wiki_app.py 后，根目录新增 wiki_data/wiki_theme/wiki_i18n/wiki_paths/wiki_tabs_* 模块。**命名坑：** 根目录不可新建 wiki_core.py —— modules/shared-wiki/ 已有同名包，Share 页经 sys.path.insert 动态加载它，根目录同名文件会被 sys.modules 缓存遮蔽导致加载错模块。**Why:** 拆分时初版命名为 wiki_core.py 触发冲突，已改名 wiki_data.py。**How to apply:** 在此项目新增根目录 wiki_*.py 时先确认不与 modules/ 下模块重名。
- [2026-08-16 14:43:30] MyWiki 打包版 (.app) 的 shared-wiki 模块加载约定：spec 不把 modules/shared-wiki 打进签名包（防运行时写 registry.json 破坏签名），改由 wiki_tabs_share._resolve_shared_dir() 五级查找（仓库根 → MYWIKI_SOURCE_DIR → Application Support 用户副本 → _MEIPASS 拷贝到用户目录 → 开发机路径兜底）。**Why:** 2026-08-16 用户截图报错 "No module named 'wiki_core'"（打包版共享页缺运行时回退）。**How to apply:** 改动 shared-wiki 加载/打包逻辑时保持"只读打包+运行时拷贝到用户目录"模式；重建 .app 用 .venv 跑 pyinstaller MyWiki.spec。
- [2026-08-16 15:05:34] MyWiki 人像抠图采用 macOS Vision 官方分割：vision_segment.py（PyObjC）+ web_server /api/vision/segment（JPEG→RGBA mask PNG），前端 120ms 节流轮询，不可用时降级 MediaPipe。**PyObjC 坑：** VNGeneratePersonSegmentationRequest 必须 alloc().initWithCompletionHandler_(None)（init/new 均 NS_UNAVAILABLE）；quality 属性只读，用 setQualityLevel_ + 常量 VNGeneratePersonSegmentationRequestQualityLevelBalanced；CVPixelBufferGetBaseAddress 在 pyobjc 返回 objc.varlist 装箱，须 ctypes.CDLL(CoreVideo) 直接调 C 符号拿裸指针。**Why:** 2026-08-16 接入时逐个踩坑。**How to apply:** 改 vision_segment.py 或新增 Vision 调用时沿用这些姿势。
- [2026-08-16 20:59:07] MyWiki 面部情绪页自拍画面约定：前置摄像头整条管线统一镜像（自拍惯例）——所有 drawImage(video, w, 0, -w, h) 水平翻转 + detect 后 landmark 坐标 x→1-x。**Why:** 2026-08-16 用户反馈"移动和人物反了"（此前非镜像他人视角）。**How to apply:** 新增任何 video 绘制/坐标计算必须镜像同源，否则运动补偿与抠图方向错乱；改 face_mood_web.html 时勿破坏该约定。
- [2026-09-03 20:55:01] MyWiki 网页版主题约定：深浅色逻辑统一在 assets/web/theme.js（localStorage "mywiki-theme"，DOMContentLoaded 绑定 #themeToggle），6 个 *_web.html 引用它而非内联。结构测试 test_dark_mode_support 断言页面含 "assets/web/theme.js" 引用。**Why:** 2026-09-03 抽取共享脚本消除 6 页重复时同步改了测试断言。**How to apply:** 新增网页页面引入 theme.js 即获得主题支持，勿再内联；test_dark_mode_support 断言针对 theme.js 引用而非内联 data-theme 代码。
- [2026-09-04 23:23:57] MyWiki 新增四大功能（2026-09-04）：菜单栏速记（QSystemTrayIcon + osascript 通知，速记写入日记引用块）、情绪自动记录（face_mood_web 开关 localStorage "mywiki-auto-mood"，60s 节流 POST /api/face_mood source=auto）、情绪报表（mood_report_web.html + GET /api/mood/range?days=N 按日聚合）、自动备份（backup_snapshots.py → backups/ keep=7，桌面端启动 30s + 24h 定时）、MCP wiki_daily_briefing 工具。**How to apply:** 改动相关功能时注意备份 zip 已 gitignore、报表依赖 /api/mood/range 聚合格式 {date, count, moods{}}。

### Reference

