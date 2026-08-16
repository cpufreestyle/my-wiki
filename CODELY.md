

## Codely Structured Memories

### User

### Feedback

### Project
- [2026-08-15 23:26:32] MyWiki 用户习惯：任务完成后期望主动提出 commit（中文 conventional 风格）并 push 到远程 gitee (cpufreestyle/my-wiki)。**Why:** 前两轮任务用户均确认"提交并推送"。**How to apply:** 完成代码任务后主动给出 commit message 草稿并询问是否 push。
- [2026-08-15 23:26:32] MyWiki 测试环境：本机未安装 Node.js（node: command not found），tests/run_all.py 仅运行 Python 测试；tests/*.logic.test.mjs 无 JS 运行器可执行。**Why:** 2026-08-15 验证 face_mood 改动时发现。**How to apply:** 验证 JS 改动用括号配对/结构性 Python 测试，勿尝试 node 命令。
- [2026-08-16 14:32:13] 拆分 wiki_app.py 后，根目录新增 wiki_data/wiki_theme/wiki_i18n/wiki_paths/wiki_tabs_* 模块。**命名坑：** 根目录不可新建 wiki_core.py —— modules/shared-wiki/ 已有同名包，Share 页经 sys.path.insert 动态加载它，根目录同名文件会被 sys.modules 缓存遮蔽导致加载错模块。**Why:** 拆分时初版命名为 wiki_core.py 触发冲突，已改名 wiki_data.py。**How to apply:** 在此项目新增根目录 wiki_*.py 时先确认不与 modules/ 下模块重名。

### Reference

