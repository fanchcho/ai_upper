# 本轮后端实验

完整结论追加docs/audit/extensions-rounding.md。font_backend_probe.py与blur_backend_probe.py为独立可复现脚本，均用AI_UPPER_HOME=/tmp/...、offscreen/software，无生产token修改。

font-results.json：两主题renderType切换0像素变化。blur-differences.json：原blur+0.2/+0.8不变，+1出现离散跳变。blur-profile.json保留真实扫描线数据。截图是本轮Qt实验，不是新Electron对照，不宣称归零。

Qt6.11.2源码来源：https://github.com/qt/qtdeclarative/blob/v6.11.2/src/quick/items/context2d/qquickcontext2dcommandbuffer.cpp 。观察到boxblur取整半径；更深Skia版本对应与字体轮廓后端仍未完成。
