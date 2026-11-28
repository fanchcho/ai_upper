# Wayland：隔离嵌套合成器真实输入已验证

隔离解包 weston/libweston-14-0 14.0.2，未安装系统。下载与所有失败日志保留：weston-download.log、weston-version.log（首次缺libexec_weston.so）、weston.log（首次backend使用绝对路径被拒绝）。修正LD_LIBRARY_PATH与WESTON_MODULE_MAP后，headless/Pixman启动成功（weston-second.log）。完整生产入口暗亮渲染成功（wayland-dark/light.png/log），但headless未提供wl_seat，不能宣称有键盘输入。

继续用Xvfb承载Weston x11 backend，应用仍明确QT_QPA_PLATFORM=wayland。启动脚本scripts/parity/wayland_nested_session.sh；生产探针scripts/parity/wayland_turn_probe.py。原实际命令与环境由nested-session-second.log的bash -x完整记录，首次嵌套启动退出127但未捕获有效stderr，nested-session.log为空；补齐隔离运行库路径后第二次启动成功，不能将首次失败断言为某一具体缺库。nested-xvfb.log为第二次的空错误日志。默认.venv Qt6.11.2，匹配fcitx插件沿用已验收产物；私有D-Bus与独立XDG目录，无真实用户配置。

xdotool在Weston外层窗口真实点击输入区并键入nihao/空格/Return；nested/dark.log与light.log包含wl_keyboard.enter/key事件和REAL_PREEDIT_SCREENSHOT 'ni hao'、REAL_APP_COMMIT '你好'、REAL_HTTP_MESSAGE_READBACK True；nested-dbus.log包含两个CreateInputContext及两个CommitString“你好”。暗亮退出均0。生产入口qml_shell.run(False)，ChatHost真实HTTP请求对接本机fixture，不算外部模型。

nested/*-preedit.png、*-commit.png、*-roundtrip.png为真实应用截图。wayland-independent.json是应用退出后新进程重开ChatSessionStore的读回：两主题标题及用户正文“你好”、助手“本地 fixture 收到你好”，原始会话副本逐字节一致；maps验证加载venv Qt6WaylandClient。

边界：已验证嵌套Weston的Wayland客户端键盘事件到fcitx D-Bus插件，不是物理Wayland桌面，也不是证明原生text-input-v3/input-method-v2适配成功。headless无seat分支仍只验证渲染。日志中的Desktop portal ServiceUnknown及退出期Main.qml:69 saveError of null原文保留，未作为输入失败或已修复事项处理。没有生产改动。
