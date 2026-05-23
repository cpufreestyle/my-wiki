# PSVR2 Panel

## 项目概述

- **名称**: PSVR2 Panel
- **类型**: PSVR2 设备管理工具
- **版本**: v4.0.0 (2026-05-06)
- **状态**: 已完成
- **路径**: D:\qclaw-workspace\psvr2-panel

## 核心功能

1. **驱动管理**: 备份/恢复 PSVR2 驱动设置
2. **VRCFaceTracking 集成**: 面部追踪配置
3. **SteamVR 监控**: 自动检测 SteamVR 状态
4. **PSVR2 设备检测**: 自动识别头显连接
5. **系统托盘**: 最小化到托盘（PySimpleGUI 风格）
6. **日志记录**: 内置 logging 模块

## 技术架构

### 主要模块

- `main.py` - 主程序（956行，完整重写 v4.0.0）
- `README.md` - 项目文档
- `PSVR2-Panel-v4.0.0.spec` - PyInstaller 构建配置

### 技术栈

- **GUI**: tkinter
- **构建**: PyInstaller
- **平台**: Windows

## 版本历史

### v4.0.0 (2026-05-06)

- 完整重写 UI
- 添加备份/恢复功能
- 集成 SVsettings
- 性能优化
- 添加日志记录系统

### v3.6.0 (2026-05-06)

- 清理 dist/build 文件
- 只保留源码在 git
- 构建 exe 并推送到 Gitee

## 部署状态

- **GitHub**: https://github.com/cpufreestyle/psvr2-panel
- **Gitee**: 已推送
- **构建产物**: dist/PSVR2-Panel-v4.0.0.exe (11.8MB)
- **Git 跟踪**: exe 文件在 .gitignore 中（不跟踪）

## 使用方式

1. 运行 `PSVR2-Panel-v4.0.0.exe`
2. 主界面显示设备状态
3. 点击"备份驱动"保存当前设置
4. 点击"恢复驱动"还原设置

## 相关项目

- [[projects/stock-crewai.md|stock-crewai]] - 另一个活跃项目
- [[people/Michael_Qiu.md|Michael Qiu]] - 开发者

## 最后更新

2026-05-22 22:56
