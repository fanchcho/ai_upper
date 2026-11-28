# 默认 Qt 6.11.2 真实 fcitx 输入收尾

本轮 A 主线已闭环：隔离构建 Qtbase 6.11.2 开发 SDK、fcitx 插件，默认 venv 生产入口真实 preedit/commit，经真实 ChatHost 与 **本地 HTTP fixture** 完成中文消息及重开存储读回。全量回归通过。未升级任何真机、公网、外部模型或像素结论。

## 提交与即时远端回执

|事项|提交及推送后远端完整 SHA|证据|
|---|---|---|
|实际私有 ABI 归因|89f6e104785b17936e623ed56e6b6f2e37816aaf|abi.md、plugin-loader.log、push-abi.log、remote-abi.log|
|隔离 SDK/插件构建与默认运行时加载|a564efa01aadc2d3ae70e4ee638b684e7955d765|build.md、sdk-targets.log、fcitx-configure.log、fcitx-build.log、new-plugin-loader.log、push-build.log、remote-build.log|
|生产入口暗亮真实中文及 ChatHost 回合|59172c5112f2eba5edae29b6f8ce1c87db1f19d0|input.md、ime-*-dbus.log、*-preedit/commit/roundtrip.png、*-session.json、independent-readback.json、push-input.log、remote-input.log|

上述提交均为 develop 的顺序追加，未回退、改写已验收的 5f7bad2 或其祖先；没有本执行之外的新提交。本轮开始工作树干净；新增证据/脚本均归档提交，构建产物保留于 `/tmp/ai-upper-qt611-sdk`，未污染系统或 venv。旧先验版本的 SDK 不存在结论已由本轮构建事实更新，旧原始失败日志保留。

## 全量回归

实际执行：

```sh
ulimit -c unlimited
AI_UPPER_HOME=/tmp/ai-upper-qt611-regression PYTHONFAULTHANDLER=1 \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" \
.venv/bin/python -m pytest app/tests -q
```

原始 full.log、退出码 full.exit：

```
1486 passed, 9 skipped in 633.03s (0:10:33)
```

**1486 passed / 9 skipped / 0 failed；633.03 秒；exit 0。** 本轮未出现段错误，没有新 core。不预载 Qt，不修改任何既有断言。全量在构建期间执行；之后仅增加构建/验证脚本与证据，没有修改生产代码或测试。application-baseline.log 与 application-final.log 完全相同：`app` tree 为 `949b72118c9d4ce939b4c6e7ab36e3c09af14c96`，application-diff.log 为空，故此次结果对应最终应用代码。

## 可用性与未完成边界

- 本轮新插件的 X11 真实输入链路已完成；需按 build.md 设置独立插件与 venv 库搜索路径。原系统 fcitx Qt6 插件仍与默认 Qt ABI 不匹配；没有替换它，也没有宣称裸默认启动会自动采用新插件。
- SDK/插件在 `/tmp`，不是持久系统安装；清理后用脚本重建。Wayland 与物理桌面输入未验证，本轮不推断其成功。
- **未完成：** `test_bot_roundtrip.py:48` 与 `test_qml_links.py:143` 历史段错误仍未归因；本轮全量未复现不等于已修复。
- **未完成：** 正文与阴影像素残差仍未归零；本轮没有改坐标、token 或样式。
- **未完成/未验证：** F06 macOS 红绿灯、真手机扫码、第二台物理设备 LAN、公网 relay/移动网络、外部推送送达、iOS/Android 安装、真实外部模型。缺相应宿主、设备或凭据，本轮不重试、不升级结论。

本轮 `deva` 未做任何修改；所有应用/测试数据位于 `/tmp`，没有访问真实 `~/.ai_upper`。已验收功能和手机协议未重跑。
