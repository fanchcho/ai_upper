# 四项技术边界推进回执

基线6da7b81。已验收81项、手机5提交等不重做，不重盘点。应用 app/、依赖pin、既有测试断言相对基线零改动；本轮变更均为探针与证据。deva只读，全部应用/测试home在/tmp，临时依赖和大core保留仓库.tmp。

| 项 | 提交及该次远端SHA | 证据 | 结论 |
|---|---|---|---|
| Electron core | 0318003bef9cb357429e0b9c4c0e59ca398f3c7f；补证 d4c316de296845edced68298d365842350a597ee；报告2b9df161681e10995ca15831ce5332ff967d5cea | electron-core.md、core-gdb.log、core-instructions.log、core-matching-electron.log、minimal-shutdown.json、graceful-shutdown.json | 触发路径闭环：相位实验收尾X11断连，Electron Ozone shutdown fatal。最小空白窗口断X返回-5，先app.quit返回0。深层Ozone栈未符号化，不关联Python历史段错误 |
| GTK原生选择器 | 58e388fc32665ce42ea83b5eddd0f9fffc04e9ed | chooser.md、chooser-dark/light.log与png | 隔离原生选择器真实键盘选择+Electron读盘闭环。警告仍可出现且不阻止成功；不是CDP文件注入 |
| F84真实输入链路 | e1736b65d1fd73a18ab4bbcf964b4e38f1a3555b | ime.md、ime-dark/light-dbus.log、readback.json、preedit/commit.png；qml-ime-dark/light.log | 系统Qt6.8.2真实fcitx preedit/commit中文闭环。默认应用ABI不兼容；旧系统Qt加载Main.qml又受topPadding阻塞，完整应用未验证 |
| 像素残差 | 9e2528944e713ccf53dfed06810445dad351b3c5 | ../extensions-rounding.md新增段，pixel/measurements.json、composition.json、shadow-color-difference.json及暗亮截图 | 未归零。定位颜色入口量化差异，排除采样点圆角/描边与默认source-over差异；未发现可证生产样式错，没有坐标补偿或改token |

push-receipts.txt 保留专题推送原文与紧随的ls-remote行。core.md初始被core.*忽略规则挡住，改名electron-core.md后已单独补交，不把未跟踪文件说成已提交。

## 回归

确认轮命令：

```bash
AI_UPPER_HOME=/tmp/ai-upper-deep-full-confirm PYTHONFAULTHANDLER=1 \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
.venv/bin/python -m pytest app/tests -q
```

ulimit -c unlimited；无预载Qt；无测试断言修改。full-confirm.log完整结果：**1486 passed, 9 skipped in 556.29s (0:09:16)**，0 failed；full-confirm.exit=0。本轮第一次full.log也输出1486/9、557.42s，但工具会话最终返回143，故不作为正常退出验收；异常如实保留，具体退出143来源未归因。确认轮通过不等于历史崩溃已修复。

两次回归针对同一应用代码树；git diff 6da7b81 -- app 与依赖文件为空。本轮没有再次出现Python段错误。历史 test_bot_roundtrip.py:48 与 test_qml_links.py:143 保持未复现、未归因、仍属风险；已有原始日志/core保持不动。

## 未完成

- 完整应用F84：默认Qt系统fcitx插件仍报 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API`；系统Qt6.8.2的真实中文成功不冒充默认应用通过。实际Main.qml系统Qt加载错误 `Cannot assign to non-existent property "topPadding"` 已落盘。
- 正文与阴影像素未归零：hinting、alpha入口与更深栅格/blur差异没有形成完整修复。原版对照图使用既有基准，本轮没有声称重新跑了完整同场Electron对照。
- GTK内部WIDGET_REALIZED_FOR_EVENT警告来源未归因，但本轮真实选择成功态可核验。
- 两处历史Python段错误未归因。本次首次会话退出143来源未归因，确认轮退出0已记录。
- 真手机扫码、第二台物理设备LAN、公网relay/移动网络、外部推送、iOS/Android系统安装均未验证，本轮不重试。F06无macOS宿主，保持Linux分支证据。

## 文件与限流处置

本轮生成的有效日志、JSON、暗亮截图和脚本均提交；临时依赖、失败中间探针、原core与readelf大输出保留.tmp/deep-boundary及.tmp/environment-closeout，未删除外部改动。本轮未发现非本执行新增提交。最后工作树状态以终端最终git status为准。

网页工具曾返回429 gateway_concurrency_limit；当时断点保存.tmp/deep-boundary/checkpoint.md，直接获取官方同版本源码成功后继续。本轮未丢弃已完成证据。
