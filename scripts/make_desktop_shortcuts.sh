#!/bin/bash
# make_desktop_shortcuts.sh — 在 macOS 桌面生成 MyWiki 启动快捷方式
#
# 零构建 .app 包裹器（不经 PyInstaller，双击始终运行仓库最新代码）：
#   ~/Desktop/MyWiki.app        桌面端 GUI（run-mywiki.command → wiki_app.py）
#   ~/Desktop/MyWiki网页版.app  网页版（scripts/launch_web.sh → web_server.py :8082）
#
# 用法: bash scripts/make_desktop_shortcuts.sh   （可重复执行，覆盖旧快捷方式）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESKTOP="$HOME/Desktop"

make_icns() {
  # $1=输出 .icns 路径；用仓库 icon.png 生成，不改动仓库内文件
  local out="$1" iconset
  iconset="$(mktemp -d)/MyWiki.iconset"
  mkdir -p "$iconset"
  for s in 16 32 128 256 512; do
    sips -z "$s" "$s" "$REPO/icon.png" --out "$iconset/icon_${s}x${s}.png" >/dev/null
  done
  for s in 16 32 128 256; do
    sips -z $((s * 2)) $((s * 2)) "$REPO/icon.png" --out "$iconset/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$iconset" -o "$out"
  rm -rf "$(dirname "$iconset")"
}

write_plist() {
  # $1=app 路径  $2=CFBundleName  $3=CFBundleIdentifier
  cat > "$1/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$2</string>
  <key>CFBundleDisplayName</key><string>$2</string>
  <key>CFBundleIdentifier</key><string>$3</string>
  <key>CFBundleVersion</key><string>2.10.1</string>
  <key>CFBundleShortVersionString</key><string>2.10.1</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>MyWiki.icns</string>
  <key>LSMinimumSystemVersion</key><string>10.13</string>
</dict>
</plist>
PLIST
}

build_app() {
  # $1=.app 路径  $2=名称  $3=bundle id  $4=入口脚本（启动时 exec）
  local app="$1" name="$2" bid="$3" entry="$4"
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  make_icns "$app/Contents/Resources/MyWiki.icns"
  write_plist "$app" "$name" "$bid"
  cat > "$app/Contents/MacOS/launcher" <<LAUNCHER
#!/bin/bash
exec "$entry"
LAUNCHER
  chmod +x "$app/Contents/MacOS/launcher"
}

chmod +x "$REPO/scripts/launch_web.sh" "$REPO/run-mywiki.command" 2>/dev/null || true

echo "REPO=$REPO"
echo "DESKTOP=$DESKTOP"
build_app "$DESKTOP/MyWiki.app" "MyWiki" "com.cpufreestyle.mywiki" "$REPO/run-mywiki.command"
build_app "$DESKTOP/MyWiki网页版.app" "MyWiki网页版" "com.cpufreestyle.mywiki.web" "$REPO/scripts/launch_web.sh"

echo "✅ 已生成桌面快捷方式："
echo "  $DESKTOP/MyWiki.app"
echo "  $DESKTOP/MyWiki网页版.app"
