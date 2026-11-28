# 默认 venv 6.11.2：真实 fcitx 中文输入与 ChatHost 回合已闭环

验证入口是 `qml_shell.run(False)`，脚本 `scripts/parity/full_app_local_turn.py` 在真实 ticker 初始化后安排窗口操作，未替换 ShellBridge、ChatHost、模型适配器或存储。模型端为 **127.0.0.1 OpenAI SSE 本地 fixture**，明确不算外部模型成功态。

## 真实链路

`bash scripts/parity/qt611_input_run.sh` 启动独立 Xvfb 与私有 D-Bus，独立 XDG/fcitx5 pinyin 配置和 `/tmp/ai-upper-qt611-<theme>-*` 数据目录。脚本使用默认 `.venv/bin/python`，`QT_QPA_PLATFORM=xcb`、`QT_QUICK_BACKEND=software`，显式加载新插件，Qt 库始终来自 venv。

xdotool 对真实窗口执行 windowfocus、mousemove/click，键入 `nihao`，空格提交，再 Return 发消息。fcitx5 守护进程通过 D-Bus 创建并处理 input context；没有调用 QInputMethodEvent 注入文字，没有直接设置输入框文本。应用的 `preeditTextChanged` 实际记录为：

```
['n', 'ni', 'ni h', 'ni ha', 'ni hao', '']
REAL_APP_COMMIT '你好'
```

暗色原始 D-Bus 日志 ime-dark-dbus.log:143、165：

```
interface=org.fcitx.Fcitx.InputContext1; member=UpdateFormattedPreedit
   array [
      struct {
         string "ni hao"
         int32 24
      }
   ]
interface=org.fcitx.Fcitx.InputContext1; member=CommitString
   string "你好"
```

两套最终日志各有 CreateInputContext **1**、FocusIn **16**、ProcessKeyEvent **13**、UpdateFormattedPreedit **6**、CommitString **1**。见 ime-dark-dbus.log、ime-light-dbus.log、independent-readback.json。qml-dark.log、qml-light.log 均显示新插件已加载，退出码均为 0。

## 会话与 HTTP 读回

真实 ShellBridge.renameSession 将提交文字作为标题写盘；真实 Return 进入 ChatHost，经 OpenAI 适配器向 loopback 发 HTTP，再消费 SSE 回复。http-request-*.json 保存实际请求正文（全部仅为本地 fixture）。重新实例化 ChatSessionStore 后读回：

|主题|最终 sessionId|标题|用户正文|助手正文|
|---|---|---|---|---|
|暗|qml-mwzuqkjue37226|你好|你好|本地 fixture 收到你好|
|亮|qml-mwzutfjz9c88bc|你好|你好|本地 fixture 收到你好|

应用退出后，另启 `.venv/bin/python`，重新创建 ChatSessionStore，逐一读取上述文件，验证标题/正文，再逐字节比对归档会话 JSON。independent-readback.json 保留路径、SHA256、正文、`copiedSessionByteEqual=true`。dark-session.json / light-session.json 是原始落盘副本，dark-readback.json / light-readback.json 为读取结果。

dark-maps.log / light-maps.log 给出完整进程映射；独立核对其中全部 libQt6 路径为 `.venv/lib/python3.13/site-packages/PySide6/Qt/lib/`，包括 QtQuick、Widgets、XcbQpa；不存在系统 6.8 或新 SDK 运行库混入。加载的新 fcitx 插件路径为 `/tmp/ai-upper-qt611-sdk/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so`。

## 截图与一次补证

- dark-preedit.png / light-preedit.png：真实 preedit `ni hao`。
- dark-commit.png / light-commit.png：真实 fcitx 提交 `你好`。
- dark-roundtrip.png / light-roundtrip.png：中文用户消息与本地 fixture 回复。

截图均为应用 `grabWindow()` 真实渲染的 1280×820 图像。第一次亮色定时截图实际已进入 commit 状态，不能作为 preedit 图；该轮原始材料保留在 first-light-timing/，包括原错误时点截图。改为在真实 `preeditTextChanged` 且值为 `ni hao` 时延迟 150ms 截图，只补跑亮色；最终 qml-light.log 有 `REAL_PREEDIT_SCREENSHOT 'ni hao'`，light-readback.json 中 `preeditScreenshot=["ni hao"]`。暗色原图经逐图检查本就是 preedit，未重跑。

## 结论边界

**默认 venv Qt 6.11.2 + 本轮隔离插件 + X11/Xvfb + 真实 fcitx5** 的 preedit、commit、重命名落盘、真实 ChatHost HTTP 回合与重开存储读回已闭环。此结论不覆盖未启用该插件环境的原系统插件组合，不覆盖 Wayland/物理桌面/外部模型；没有改系统目录、仓库依赖 pin、应用实现或既有测试断言。
