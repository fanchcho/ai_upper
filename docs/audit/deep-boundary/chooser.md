# 原生 GTK 选择器真实键盘闭环

隔离组合：Electron 自带 Chromium，GTK 3.24.49-3（.tmp/extensions-complete/libgtk-3-0t64_3.24.49-3_arm64.deb），Xvfb X11，openbox 子进程；GSettings schemas 在 .tmp/environment-closeout/runtime 编译。没有更改系统安装或仓库依赖。openbox/windowactivate 仍有 _NET_ACTIVE_WINDOW 警告，因此不能把 WM 激活声明为完全成功。

本轮将 xdotool 自动化从 Electron 主进程同步 execFileSync 改为独立异步 worker，避免主进程等待自动化时阻塞 GTK 事件循环。原生 dialog.showOpenDialog 真实展示目录列表，外部键盘 Ctrl+L 输入磁盘路径，Return 确认；Electron 返回 canceled=false、filePaths，再 fs.readFileSync 读回 NATIVE_CHOOSER。没有 CDP、setInputFiles 或合成 dialog 返回值。

暗、亮原始日志 chooser-dark.log / chooser-light.log 均有 NATIVE_GTK_FILE_READBACK_OK，截图 chooser-dark.png / chooser-light.png 是 X11 根窗口实际抓取。中性首次成功日志 chooser.log 也保留。实际选择路径 .tmp/environment-closeout/chosen.txt。截图证明真实窗口；应用返回与读盘证明完成选择。

暗色成功轮仍出现 WIDGET_REALIZED_FOR_EVENT，因此该警告不是本探针失败的充分条件；不能宣称 GTK 内部警告根因已修复。同步主进程自动化的旧失败与本轮异步成功构成可复核差异；没有证据证明是缺 WM 或窗口从未 map。原始 GSettings 崩溃不改写，仍见 docs/audit/phone-extensions/file-chooser-failure.log。

结论：隔离 Linux 原生 GTK 选择器的真实选择与应用读回已闭环；GTK 警告内部来源未归因。没有修改产品行为。

复现：创建 .tmp/environment-closeout/chosen.txt 内容 NATIVE_CHOOSER（无换行），设置 AI_UPPER_HOME=/tmp/ai-upper-gtk-{theme}、PROBE_THEME=dark/light、GTK_THEME=Adwaita:dark/light、TMPDIR=$PWD/.tmp/deep-boundary、GSETTINGS_SCHEMA_DIR=$PWD/.tmp/environment-closeout/runtime/usr/share/glib-2.0/schemas、GSETTINGS_BACKEND=memory；PATH 追加 .tmp/icon-dpi/runtime/usr/bin 与 .tmp/wm/usr/bin；LD_LIBRARY_PATH 包含 .tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu、.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu、.tmp/wm/usr/lib/aarch64-linux-gnu。运行 .tmp/wm/usr/bin/xvfb-run -a .tmp/extensions-complete/browser/node_modules/electron/dist/electron --no-sandbox --disable-gpu scripts/parity/environment_chooser_probe.cjs。
