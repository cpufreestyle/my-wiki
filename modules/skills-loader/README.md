# Skills Loader 模块

把一个集中的**统一技能目录**作为技能根，让 MyWiki（及任意 Agent）统一发现、查询、调用技能。

## 统一技能根目录

默认：`~/AI Shared/skills`

定位优先级：

1. 环境变量 `MYWIKI_SKILLS_ROOT`
2. `~/AI Shared/skills`
3. `~/.qclaw/skills`（兼容旧路径）

## 目录约定

```
<SKILLS_ROOT>/
    huashu-design/
        SKILL.md          # frontmatter: name / description(含触发词)
        scripts/*.mjs …
    video-analysis/
        SKILL.md
        scripts/analyze_video.py
```

每个技能是一个子目录，`SKILL.md` 顶部的 YAML frontmatter 提供 `name` 与 `description`。

## 使用

```bash
# 显示当前技能根
python modules/skills-loader/loader.py root

# 列出所有技能
python modules/skills-loader/loader.py list

# 查看某技能的 SKILL.md
python modules/skills-loader/loader.py show huashu-design

# 运行某技能脚本（默认取 scripts/ 下第一个 .py）
python modules/skills-loader/loader.py run video-analysis --script analyze_video.py -- <video>
```

## 作为库调用

```python
import sys
sys.path.insert(0, "modules/skills-loader")
import loader

loader.SKILLS_ROOT              # 当前技能根
loader.discover_skills()        # 列出全部技能 (list[dict])
loader.get_skill("huashu-design")
loader.read_skill_md("video-analysis")   # 载入 SKILL.md 到上下文
loader.run_skill_script("video-analysis", "analyze_video.py", ["a.mp4"])
```

## 文件

- `loader.py`: 加载器（发现 / 查询 / 运行）
- `README.md`: 本文件
