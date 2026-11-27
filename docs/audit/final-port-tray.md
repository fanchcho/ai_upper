# 托盘与回复通知复核（未验证系统成功态）

原版 index.ts:235-272 托盘显示/定时任务/退出；:164-173 关闭驻留；reply-notify.ts:15-80 未聚焦时通知、点击回到会话。

复核 2880334 后补齐：持有 QMenu 防止 Python 对象被回收；托盘菜单增加真实定时任务入口；只有真实托盘可用才拦截关闭，防止窗口消失后无法唤回；通知点击显示窗口并切到对应会话；后台任务完成及待处理状态进入通知路径。

真实宿主探测：`AI_UPPER_HOME=/tmp/ai-upper-tray-probe QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python` 创建实际 QApplication、QQuickWindow、TrayController 后调用 install/notify。

原始输出 out/final-port/tray-probe.log：

```
TRAY UNAVAILABLE platform=offscreen isSystemTrayAvailable=False
NOTIFY UNAVAILABLE tray_available=False supportsMessages=True
{"installed": false, "notify": false}
```

没有托盘宿主，系统托盘图标、菜单交互、通知展示/点击均 **未验证**，不计入“已实现且可用”。保留实际代码路径，不使用替身通知或绘制托盘图片作为成功证据。
