# F84：真实 fcitx 中文事件，隔离组合通过；默认应用尚未通过

系统 /usr/bin/python3 + PySide6/Qt 6.8.2，系统 libfcitx5platforminputcontextplugin.so，Xvfb X11 与私有 D-Bus。没有降级仓库依赖、没有构造 QInputMethodEvent。fcitx5 profile 显式选择 pinyin；键盘注入放在独立 worker，Qt 主线程持续处理输入上下文/焦点事件。探针读取 QLineEdit 的真实 inputMethodEvent，并从实际 text 写 JSON 后重新读取断言中文。

两主题均有：

- xdotool getwindowfocus getwindowname 返回 IME_ISOLATED，fcitx5-remote 返回 2（激活）。
- ime-{dark,light}-dbus.log：CreateInputContext 的 display=x11:，FocusIn，CurrentIM=Pinyin，ProcessKeyEvent，UpdateFormattedPreedit，CommitString。
- ime-{dark,light}.log：真实 preedit n / ni / ni h / ni ha / ni hao，然后 commit 你好，QT 6.8.2 FINAL '你好'，CHINESE_DISK_READBACK_OK。
- ime-{dark,light}-readback.json：落盘并重读 text=你好，保留所有事件。ime-{dark,light}-{preedit,commit}.png 为实际 Qt widget 截图，中文字体从已有 .tmp/theme-settings/NotoSansCJKsc-Regular.otf 加载。

这是 fcitx Qt 平台插件经 D-Bus 的 X11 输入上下文，不是 XIM fallback；守护进程的 Failed to open wayland connection 原文保留，因为本轮不是 Wayland 会话。初始同步键盘方案仍得到 nihao，记录 ime.log；异步首次真实事件记录 ime-async.log。激活 pinyin 和异步输入同时调整，不能把改善完全归于单一因素。

另外尝试了系统 Qt 6.8.2 加载真实 Main.qml（scripts/parity/qml_real_ime_probe.py）。先隔离解包缺失的 Controls/Dialogs/Layouts/Shapes 等模块，无系统安装；最后明确失败：Main.qml:43:5: Cannot assign to non-existent property "topPadding"。完整输出 qml-ime-dark.log / qml-ime-light.log。没有修改 Main.qml 来绕开，也没有伪造应用成功态。

结论：本轮“匹配 Qt/fcitx 的真实中文 preedit/commit”已闭环，暗亮两轮均真实读回中文；仓库默认 Qt+系统插件仍受旧 ABI 错误限制，完整应用 F84 **未完成/未验证**。原始 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API` 仍保留 docs/audit/environment-closeout/ime-abi.log。独立 widget 成功不冒充 Main.qml 或默认发行配置成功。

## 复现

scripts/parity/real_ime_session.sh 创建隔离 profile、启动 fcitx 和 D-Bus monitor，再运行 scripts/parity/environment_ime_probe.py。暗亮分别设置 PROBE_THEME，命令：

```bash
AI_UPPER_HOME=/tmp/ai-upper-ime-final-dark PROBE_THEME=dark \
TMPDIR=$PWD/.tmp/deep-boundary \
PATH=$PWD/.tmp/icon-dpi/runtime/usr/bin:$PWD/.tmp/wm/usr/bin:$PWD/.tmp/secret-service/root/usr/bin:$PATH \
LD_LIBRARY_PATH=$PWD/.tmp/secret-service/root/usr/lib/aarch64-linux-gnu:$PWD/.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.tmp/wm/usr/bin/xvfb-run -a .tmp/secret-service/root/usr/bin/dbus-run-session \
--config-file=$PWD/.tmp/secret-service/bus.conf -- bash scripts/parity/real_ime_session.sh
```
