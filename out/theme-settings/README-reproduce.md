# 复现环境

工作目录 `/home/agent/shared_workspace/ai_upper`。使用现有 `.venv`，未改依赖 pin。

```bash
mkdir -p .tmp/theme-settings
curl -L --fail https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf -o .tmp/theme-settings/NotoSansCJKsc-Regular.otf
AI_UPPER_HOME=/tmp/ai-upper-theme-render QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python out/theme-settings/render.py before
AI_UPPER_HOME=/tmp/ai-upper-theme-render QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python out/theme-settings/render.py after
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python out/theme-settings/contrast.py
.venv/bin/python out/theme-settings/run_tests.py
```

render 使用测试装配生成 `/tmp/ai-upper-theme-*` 独立配置；所有测试 basetemp 也位于 `/tmp`，从未访问真实 `~/.ai_upper`。字体仅加载到证据进程，不安装到系统、不改应用依赖。

截图分辨率固定 1420×1076，DPR=1；设置弹窗保持产品原有 720×560，未为截图改变产品几何。用户截图是弹窗局部/高 DPI；Linux before 不复现 macOS 的黑色圆角残留，但能直接观察默认控件不跟随深色。原始截图另存 user.png。

before 复制 QML 到 `.tmp/theme-settings/before-qml` 并覆盖三份保存的修改前源文件；Python bridge 使用当前代码，但 before 仅显式 light/dark，不影响颜色基线。after 在同一窗口切主题，无重启。

像素算法：遍历真实 QML 可见文本项取得几何；裁取该区域的截图像素，众数为底色，最接近实际 Text.color 的已渲染像素为字形内部颜色。两者按 sRGB 线性化 WCAG 公式计算。非全部覆盖率的抗锯齿边缘不作为字形内部；原始色距 distance 在 contrast.json 可审计。遮挡、图标、滚动条非文字不算文字对比度。全部采样按更严格 4.5 检查，不放宽大字到 3。

Qt 系统配色 API 依据：https://doc.qt.io/qt-6/qstylehints.html#colorScheme-prop 。Context7/smart-search 当前未提供，使用官方文档及已安装 Qt 实际运行验证。
