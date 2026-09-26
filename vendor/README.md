# vendor/ — 第三方前端运行时依赖（本地化，禁止改动文件内容）

本目录存放**第三方二进制运行时**，内容与上游发布包逐字节一致，仅作同源伺服，
目的是让 `face_mood_web.html`（面部情绪识别页）完全不依赖公网 CDN。

> 背景：本地网络/VPN 环境下 `cdn.jsdelivr.net`、`storage.googleapis.com` 长期无响应，
> 导致页面卡在「正在加载 MediaPipe 模型…」。改为同源加载后即可离线秒开。

## mediapipe/

来源（上游 npm 包，按版本号整体取用，禁止混版）：

| 文件 | 大小 | 上游 |
|---|---|---|
| `vision_bundle.mjs` | 136993 | `@mediapipe/tasks-vision@0.10`（解析为 0.10.35） |
| `wasm/vision_wasm_internal.js` | 322044 | 同上 |
| `wasm/vision_wasm_internal.wasm` | 11153617 | 同上 |
| `wasm/vision_wasm_nosimd_internal.js` | 321847 | 同上 |
| `wasm/vision_wasm_nosimd_internal.wasm` | 10481398 | 同上 |
| `selfie_segmentation.js` | 44542 | `@mediapipe/selfie_segmentation@0.1`（解析为 0.1.1675465747） |
| `selfie_segmentation_solution_simd_wasm_bin.js` | 276493 | 同上 |
| `selfie_segmentation_solution_simd_wasm_bin.wasm` | 5694839 | 同上 |
| `selfie_segmentation_solution_wasm_bin.js` | 276488 | 同上 |
| `selfie_segmentation_solution_wasm_bin.wasm` | 5587523 | 同上 |

`*_nosimd_*` 是 SIMD 不可用时的回退，Chromium/Safari/Firefox 现代版本默认走 simd 分支。

## 升级方式

```bash
cd vendor/mediapipe
for f in wasm/vision_wasm_internal.js wasm/vision_wasm_internal.wasm \
         wasm/vision_wasm_nosimd_internal.js wasm/vision_wasm_nosimd_internal.wasm \
         vision_bundle.mjs; do
  curl -fSL --retry 3 -o "$f" "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10/$f"
done
for f in selfie_segmentation.js \
         selfie_segmentation_solution_simd_wasm_bin.js \
         selfie_segmentation_solution_simd_wasm_bin.wasm \
         selfie_segmentation_solution_wasm_bin.js \
         selfie_segmentation_solution_wasm_bin.wasm; do
  curl -fSL --retry 3 -o "$f" "https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation/$f"
done
```

下载后务必核对大小与上表一致（半截文件会让页面静默卡死），
`tests/test_face_mood_web.py::TestFaceMoodWebLocalAssets` 会守住这一点。

人脸模型本体 `models/face_landmarker.task` 不在此目录，沿用仓库既有的 `models/` 位置。
