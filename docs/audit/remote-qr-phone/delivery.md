# 本轮交付与保留边界

基线 `ea5bf9dacb695fa771c86849a975c87cd8d15572`，开始工作树为空；无外部并发提交、无上一轮未提交残留。未重做81项盘点或其它已验收验证。

F62 功能提交 `60ebbfcad3fd0dd8f4fe555f144f8af20f1ba123`，随后原始输出：
```
To github.com:fanchcho/ai_upper.git
   ea5bf9d..60ebbfc  develop -> develop
60ebbfcad3fd0dd8f4fe555f144f8af20f1ba123	refs/heads/develop
```
F64 功能提交 `a49cd378a4582f0c1673c075cd9c37f165e31bbd`，随后原始输出：
```
To github.com:fanchcho/ai_upper.git
   60ebbfc..a49cd37  develop -> develop
a49cd378a4582f0c1673c075cd9c37f165e31bbd	refs/heads/develop
```

- F62：新增真正设备授权扫码路径，本地协议 fixture + 真实 QML 点击 + 重新开文件/密钥库读盘已验证。真实飞书注册服务器返回 QR，但无人扫码批准；真实应用创建/真人邀请兑换 **未验证**。不能等同于手填凭据。
- F64：QR、一次链接、LAN/relay、设备状态与撤销、文字主会话往返，本机真实端口闭环已验证（暗亮各两通道）。公网 relay、真手机扫码、第二台设备 LAN 与移动网络 **未验证**。完整原版手机页面的附件/交付文件/交互卡/任务/主屏幕安装扩展帧 **未完成**，具体缺口见 F64.md。
- F84：保留 `../bot-detail/ime-abi.log:434` 原始 ABI 错误 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API`。本轮不重试、不合成事件冒充，**真实 fcitx preedit 环境未验证**。
- F06：保留已有 Linux 非 macOS 分支证据；**macOS 未验证**，不改成不适用。
- 历史 `test_bot_roundtrip.py:48` 段错误：既有五轮独立执行未复现，不宣称修复；**未复现、未归因，仍属风险**。
- 正文/阴影像素：保留**未归零**；本轮不重跑、不改 token、不补坐标。

交互日志保留了 QML 关闭期间的 `saveError of null` 和 Qt socket disconnect 警告，以及浏览器缺 system D-Bus 的原始诊断；没有删掉警告制造干净成功态。实际完成判断依据四条端到端读盘断言，而非无警告。

运行均隔离 `AI_UPPER_HOME=/tmp/...`；deva 只读，依赖 pin 和既有测试文件无修改。新增唯一测试 `test_phone_sessions.py` 验证 scope 拒绝与非法 sid。


QR Python 3.8 兼容性修复提交 `5f1ef4882b18153de4e339810b9f962ef6a47580`：
```
To github.com:fanchcho/ai_upper.git
   a49cd37..5f1ef48  develop -> develop
5f1ef4882b18153de4e339810b9f962ef6a47580	refs/heads/develop
```
既有 `test_import_time_type_expressions_are_python38_safe` 发现供应商代码的 `class _BitBuffer(list[int])`。修实现为 `typing.List[int]`；断言未改。兼容性从 1 failed / 4 passed 到 5 passed，三组 QR 矩阵与未修改编码器逐格一致，见 compat-before.log / compat-after.log / qr-compat-check.log。

首次全量原始命令：
```
AI_UPPER_HOME=/tmp/ai-upper-remote-final-20261128 PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest app/tests -q
```
`full-regression.log`：先命中上述兼容性失败，之后在 `test_qml_links.py:143` 的 `QTest.mouseClick` 发生 Segmentation fault，进程退出 139，没有产生完整套件最终计数。core 留在 `.tmp/phone-evidence/crash/pytest-qml-links.core`（未提交大文件）。随后该文件独立执行 `2 passed in 5.87s`，日志 links-isolated.log。这个新崩溃点 **未归因、仍属风险**；没有证据证明与历史 bot_roundtrip 崩溃同因。

重跑使用既有 UI 证据环境：`QT_QUICK_BACKEND=software` 与仓库隔离运行库，不预载 Qt、不改既有测试。切换渲染环境不能作为“已修复段错误”的证据。


F64 撤销后新 QR 续配修复提交 `e286d6e8548e14c77b36b30bc01811599668394b`：
```
To github.com:fanchcho/ai_upper.git
   5f1ef48..e286d6e  develop -> develop
e286d6e8548e14c77b36b30bc01811599668394b	refs/heads/develop
```
同一浏览器标签使用新票据代替旧设备密钥，fragment 改变触发重新握手；四组真实 UI/浏览器场景均重新配对出不同设备 id，读盘记录在 phone-readback.json。


最终全量重跑命令：
```
AI_UPPER_HOME=/tmp/ai-upper-remote-final-retry PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -m pytest app/tests -q
```
原始结果（full-regression-retry.log）：
```
1481 passed, 9 skipped in 555.40s (0:09:15)
```
即 **1481 passed / 9 skipped / 0 failed**，退出码 0。较此前1480新增一个权限测试。运行期间的最后改动只涉及浏览器重新扫码逻辑与其证据脚本，已完成四组真实 UI/HTTP/存储专项复验；Python 功能源码在本次回归开始前已确定，既有断言没有改动。首次全量崩溃仍保留，不据这次成功宣称修复。

结论：F62 设备授权扫码代码与本地持久化已补齐，外部真人授权未验证；F64 本轮指定的两通道文字会话链路本地闭环，真手机/公网未验证，原版手机扩展帧仍未完成。项目总体目标保持开放。
