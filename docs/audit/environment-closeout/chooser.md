# 原生GTK文件选择器隔离尝试

通过 apt-get download（仓库 .tmp/apt/lists）获取 gsettings-desktop-schemas、libgtk-3-common、libglib2.0-bin/dev-bin/0t64，仅 dpkg-deb -x 到 .tmp/environment-closeout/runtime，无系统安装和依赖pin修改。glib-compile-schemas 生成 runtime/usr/share/glib-2.0/schemas/gschemas.compiled。

设置 GSETTINGS_SCHEMA_DIR 为该目录、GSETTINGS_BACKEND=memory、AI_UPPER_HOME=/tmp/ai-upper-native-chooser；Xvfb启动真实Electron，dialog.showOpenDialog调用GTK原生窗口，xdotool Ctrl+L输入真实磁盘路径再Return。未调用CDP文件注入。脚本 scripts/parity/environment_chooser_probe.cjs，日志 chooser.log / chooser-retry.log；第二次加openbox及windowactivate仍在15秒超时退出2。

已排除原始“No GSettings schemas are installed on the system”致命错误；但出现原文 `Gtk: gtk_widget_event: assertion 'WIDGET_REALIZED_FOR_EVENT (widget, event)' failed`，没有返回选中文件，未得到写盘读回成功。结论：schemas缺失已在隔离环境补齐；原生选择器成功态仍未验证，未完成。旧崩溃日志docs/audit/phone-extensions/file-chooser-failure.log与两份.tmp/phone-extensions/file-chooser*.core保持，不以超时或窗口创建替代成功。
