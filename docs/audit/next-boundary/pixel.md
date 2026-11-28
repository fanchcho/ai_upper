# 版本与调用链

详见extensions-rounding.md本轮追加段。deva pnpm-lock与真实electron/dist/version=33.4.11；Electron DEPS→Chromium130.0.6723.191→Skia d41eba845cdb7ade07e68f20676675c25e2734fc。

sources下保存官方原文（带原版权声明），draw_looper.cc来自同Chromium tag cc/paint，skia_utils.h来自同tag third_party/blink/renderer/platform/graphics/skia。Blink CSS参数sigma=blur/2，Qt Canvas是取整box radius，数值对照blur-parameters.json。

调用链取证完成；实际完整kernel/字体后端的像素一致性未完成，不归零。没有新生产样式变更。
