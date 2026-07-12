# MyWiki UI — Figma 设计规范

> 统一设计系统（Apple 风浅色）。本文件用于在 Figma 中复刻/迭代 MyWiki 的三个界面，
> 之后可通过 `parse_figma`（Copy as JSON）或截图转代码回灌到代码。

## 1. 画板（Frames）

| 画板 | 尺寸 | 说明 |
|------|------|------|
| Quick Reminder（网页） | 480 × 自动高度 | 居中卡片容器，max-width 480 |
| Reminder（桌面） | min 760 × 620（默认最大化） | Tkinter 窗口（自绘 Label 按钮，绕过 macOS aqua 配色，跨平台一致） |
| Daily Journal（浮窗） | 560 × 460 | 置顶浮窗，顶部药丸标题栏 |

## 2. 颜色变量（Color Variables）

在 Figma 中建 Collection `MyWiki/Light`，以下均设为 **Light** 模式变量：

| 变量名 | 值 | 用途 |
|--------|-----|------|
| `bg` | `#F5F5F7` | 页面/窗口背景 |
| `surface` | `#FFFFFF` | 卡片/表面 |
| `text-primary` | `#1D1D1F` | 主文字 |
| `text-secondary` | `#86868B` | 次要文字 |
| `accent` | `#0A84FF` | 主强调（蓝） |
| `accent-hover` | `#0070E0` | 强调 hover |
| `orange` | `#FF9F0A` | 自定义提醒 |
| `orange-hover` | `#E88E00` | 橙 hover |
| `green` | `#34C759` | 查看/成功 |
| `green-hover` | `#2BB04E` | 绿 hover |
| `border` | `#E5E5EA` | 描边/分隔线 |

对比度：文字 `#1D1D1F` 在 `#FFFFFF` 上 ≈ 16:1（远超 WCAG AA 4.5:1）。

在 Figma 中另建 Collection `MyWiki/Dark`，以下均设为 **Dark** 模式变量（切换集合即可换肤）：

| 变量名 | 值 | 用途 |
|--------|-----|------|
| `bg` | `#1C1C1E` | 页面/窗口背景 |
| `surface` | `#2C2C2E` | 卡片/表面 |
| `text-primary` | `#F5F5F7` | 主文字 |
| `text-secondary` | `#98989D` | 次要文字 |
| `accent` | `#0A84FF` | 主强调（蓝，深浅一致） |
| `accent-hover` | `#409CFF` | 强调 hover（提亮） |
| `orange` | `#FF9F0A` | 自定义提醒 |
| `orange-hover` | `#FFB340` | 橙 hover |
| `green` | `#30D158` | 查看/成功（深底提亮绿） |
| `green-hover` | `#40D969` | 绿 hover |
| `border` | `#3A3A3C` | 描边/分隔线 |

## 3. 文字样式（Text Styles）

| 样式名 | 字体 | 字号 | 字重 | 颜色 |
|--------|------|------|------|------|
| Title/LG | Helvetica Neue | 21 | SemiBold(600) | text-primary |
| Title/MD | Helvetica Neue | 16 | SemiBold | text-primary |
| Body | Helvetica Neue | 13–15 | Regular | text-primary |
| Caption | Helvetica Neue | 11–12 | Regular | text-secondary |
| Card-Label | Helvetica Neue | 14 | SemiBold | text-primary |
| Accent-Time | Helvetica Neue | 12 | SemiBold | accent |

> macOS 下中文自动回退到 PingFang SC；Figma 中可设 Fallback 字体。

## 4. 半径 / 间距 / 阴影 / 模糊

- **圆角**：卡片 14px，按钮 10px，模态 18px，列表项 12px
- **间距**：区块间距 16–20px，卡片内边距 14px，网格 gap 12px
- **阴影**：
  - 卡片：`0 1px 3px rgba(0,0,0,0.08)`
  - 悬浮：`0 8px 24px rgba(0,0,0,0.06)`
  - 模态：`0 20px 60px rgba(0,0,0,0.20)`
- **模态遮罩**：`rgba(0,0,0,0.40)` + 背景模糊 `blur(4px)`
- **焦点环**：`0 0 0 3px rgba(10,132,255,0.15)`（输入框）/ 3px 蓝色描边（按钮 `:focus-visible`）

## 5. 组件规格

### 5.1 预设卡片（Preset Card）

- 白底 `surface`，1px `border` 描边，圆角 14px
- 左侧蓝色圆点 `●`（accent，Ø8）
- 标题：Card-Label（如「1 小时后」）
- 副文：Caption（如「快速稍后提醒」），text-secondary
- 状态：hover 上浮 2px + 阴影加深；active 缩放 0.98

### 5.2 按钮（Button）

桌面端按钮用 `tk.Label` 自绘（绕过 macOS aqua 对 `bg/fg` 的忽略，跨平台配色一致），共两类：

| 类型 | 底色 | 文字 | 说明 |
|------|------|------|------|
| 主操作（保存 / 启动 MCP 服务等） | `accent`（蓝 `#0A84FF`） | 白 `#FFFFFF` | 填充蓝，hover 加深为 `accent-hover`；白字 on 蓝达 Apple 系统按钮标准（大字号满足 WCAG AA） |
| 次操作（取消 / 语言 / 主题切换） | `bg`（页面背景） | `text-primary` | 1px `border` 描边，hover 变为 `BTN_HOVER` |

- 字重 SemiBold，padding 14px，圆角 10px，active 缩放 0.98。
- 语义色（橙 `orange` / 绿 `green`）用于网页端提醒类按钮的填充或描边；桌面端主操作统一用蓝色填充以保证可辨识度。

### 5.3 输入框（Input）

- 背景 `bg`，1px `border`，圆角 10px，padding 12px
- 聚焦：`border`→accent + 焦点环

### 5.4 模态（Modal）

- 居中白卡，圆角 18px，padding 24px，max-width 360
- 标题 Title/MD，副文 Caption
- 底部操作区：取消（次）/ 确定（主）并排
- 进场动画：scale 0.96→1 + 淡入 0.18s

### 5.5 列表项（Pending Item）

- 白卡，圆角 12px，padding 14×16
- 时间：Accent-Time（accent）
- 内容：Body（text-primary），自动换行

### 5.6 Toast

- 深色胶囊 `rgba(29,29,31,0.92)`，白字，圆角 12px，底部居中，2.4s 消失

## 6. 回流到代码

- **Figma → 代码（精确）**：在 Figma 选中 Frame → 右键 `Copy as JSON` → 交给 `parse_figma` 工具解析结构与样式 → `generate_component` 生成。
- **截图 → 代码（快速）**：导出 Frame PNG → 用截图转代码分析布局。
- **代码侧**：所有颜色/字体集中在 `theme.py`（桌面）/ `:root`（网页），改一处即全局生效。

## 7. 后续可扩展

- 深色模式：新增 `MyWiki/Dark` 变量集（bg `#1C1C1E`、surface `#2C2C2E` 等），切换集合即可。
- 响应式：网页版 <480px 时预设网格转单列。
