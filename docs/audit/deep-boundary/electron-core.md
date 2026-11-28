# Electron core实际取证

用隔离解包的gdb16.3，对 .tmp/environment-closeout/probe.core 与原electron可执行文件执行 info proc cmdline / info proc mappings / thread apply all bt / info registers pc / x/8i。完整映射和各线程栈见core-gdb.log，指令见core-instructions.log；readelf -n 原始大输出保留.tmp/deep-boundary/core-notes.txt。

core命令行明确含 --password-store=gnome-libsecret、--remote-debugging-port=9344、.tmp/feature-review/electron-profile、deva/apps/desktop/out/main/index.js。这与phase-session.py的原版相位/安全存储会话启动命令一致，不是独立chooser.cjs实验进程。信号SIGTRAP，PC 0xaaaac1c8c200；二进制缺调试符号，主线程地址栈不能直接解析源码函数。

结论：已定位到原版相位/安全存储共用Electron进程，排除独立GTK选择器探针和Python测试进程。尚不能在该共用进程里区分具体是哪次DOM相位操作或退出触发，不能把--password-store参数当成safeStorage崩溃证据。原生SIGTRAP而非普通JS异常；Chromium/Electron具体断言及最小复现未归因、仍属风险。没有据此修改应用代码。

## 补充取证：触发路径已收敛到 X11 断连 shutdown fatal

前文“不能区分具体退出触发”现由新增证据收敛：

1. out/parity-close/electron.log（本轮复制为 core-matching-electron.log）同 PID **296305** 在 **09:47:20.699956** 输出 `FATAL:electron_browser_main_parts.cc(502)] Failed to shutdown.`。原 core mtime 为 **09:47:20.776 +0800**；与日志相差约 76ms。
2. 对应运行时 Electron 33.4.11 官方源码：<https://github.com/electron/electron/blob/v33.4.11/shell/browser/electron_browser_main_parts.cc#L500>。Linux 分支将该 fatal shutdown callback 传给 Ozone 的 PostCreateMainMessageLoop；不是页面 JS 抛异常。官方原始源码下载位于 .tmp/deep-boundary/electron_browser_main_parts.cc。
3. scripts/parity/closeout/phase-session.py 最后对整个 electron/xvfb-run 进程组发 SIGTERM，会同时结束 X server。此前 safeStorage 已返回 available=true、saved.ok=true、has=true；不能据此断言它导致 core。
4. 新最小复现 **不加载 deva，不调用 safeStorage，不做 DOM 相位操作**。真实 BrowserWindow ready 后仅终止 Xvfb，得到同一 fatal 行和 electron_exit=-5（SIGTRAP）。minimal-shutdown.json、minimal-electron.log 与 scripts/parity/electron_x_disconnect_probe.{py,cjs} 可复核。
5. 对照：同一个最小窗口先 app.quit，再退出 Xvfb，graceful-shutdown.json 显示 exit=0、fatal_shutdown=false。

结论：这个 Electron core 的触发路径已闭环为相位实验收尾造成 X11 显示服务断连，进入 Electron Linux Ozone shutdown fatal；不再归为未知的 GTK 选择器或 safeStorage 功能失败。core 的 brk #0 是原生终止，具体 stripped PC 无源码符号。寄存器附近 string_view::substr 字符串不能覆盖同 PID fatal 日志的证据，亦不能据此另造越界根因。未定位 Ozone 内部更深层调用栈，也没有据此宣称修好了历史 Python segfault。

复现命令（AI_UPPER_HOME 均 /tmp）：python3 scripts/parity/electron_x_disconnect_probe.py 与其 graceful 参数。首次原 core 保留不动；这个主动触发 SIGTRAP 的最小复现禁用重复 core，避免再生成约 0.5GB 副本；日志完整保留。
