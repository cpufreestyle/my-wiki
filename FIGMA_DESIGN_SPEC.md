# MyWiki UI — Figma 设计规范

> 统一设计系统（Apple 风浅色）。本文件用于在 Figma 中复刻/迭代 MyWiki 的三个界面，
> 之后可通过 `parse_figma`（Copy as JSON）或截图转代码回灌到代码。

## 1. 画板（Frames）

| 画板 | 尺寸 | 说明 |
|------|------|------|
| Quick Reminder（网页） | 480 × 自动高度 | 居中卡片容器，max-width 480 |
| Reminder（桌面） | 420 × 640 | Tkinter 窗口，macOS aqua |
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
| 类型 | 底色 | 文字 | 形状 |
|------|------|------|------|
| 主操作（确定/保存） | accent | 白 | 圆角 10px 实心 |
| 次操作（取消） | surface | text-primary | 圆角 10px + 1px border |
| 自定义提醒 | orange | 白 | 圆角 10px 实心 |
| 查看待发送 | green | 白 | 圆角 10px 实心 |

通用：字重 SemiBold，padding 14px，active 缩放 0.98。

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
- 深色模式：新增 `MyWiki/Dark` 变量集（bg `#1D1D1F`、surface `#2C2C2E` 等），切换集合即可。
- 响应式：网页版 <480px 时预设网格转单列。
