# 429 后收尾复核

本轮起点 HEAD 与远端均为 `6c62ff9891c2b8dd0b5036fbf2608677a1331c68`，工作树干净。该提交实际已推送，不能写成“最终报告未提交”。`git show --stat 6c62ff9` 确认 delivery.md、delivery.json、pushes.md、full.log 四份材料已在 Git 中；五份专题报告与原有20组证据在此前功能提交中。五个功能 SHA 的祖先检查全部通过，没有外部并发提交、回退或半截残留。

上一轮收尾原始 push 回执（.tmp/phone-extensions/report-push.log）：
```
To github.com:fanchcho/ai_upper.git
   b53779c..6c62ff9  develop -> develop
```
本轮远端实际查询：
```
6c62ff9891c2b8dd0b5036fbf2608677a1331c68	refs/heads/develop
```

五份专题报告逐项补入全 SHA 与远端包含关系，原版文件/行号、验证方式、读盘/截图路径均保留。功能提交依次是 564d226（上传）、b5d2c30（下载）、b3885d0（交互卡）、cd28ad9（任务）、b53779c（安装）。完整 SHA 在 delivery.json / pushes.md 及专题报告中。

## 证据复核与实际补缺

`recovery-audit.json` 保存报告/日志/JSON/PNG 的大小和 SHA256；JSON 完整解析、PNG 通过 Qt 实际解码。原有20组结果均检查重新打开会话、撤销记录与专题状态。下载样本仍在磁盘，文本和256000字节二进制再次逐字节比较并记录双方 SHA256。审核脚本 `scripts/parity/phone_evidence_audit.py` 可重跑。

原有交互卡只真实点击过 approve。本轮仅补 keep/ignore，分别执行：
```
PLAN_DECISION=keep AI_UPPER_HOME=/tmp/ai-upper-phone-recovery-keep QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py cards
PLAN_DECISION=ignore AI_UPPER_HOME=/tmp/ai-upper-phone-recovery-ignore QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py cards
```
每项LAN/relay×暗亮四组真实浏览器鼠标，真实 ChatHost 工具回合，重新打开 Interactions JSON 和会话 plans 边车，分别确认为 keep/ignore；不产生允许/拒绝写入样本文件。新增8组证据在 cards-keep/、cards-ignore/（cards-*.json、phone-readback.json、phone-browser-keep/ignore-*.png、run.log）。本机模型与 relay fixture 标识未改变；不是外部模型或真机成功。

上传设备归属/顺序/完成消费、下载路径约束、卡片越界与重放拒绝、任务完成态、安装TTL与二维码取消独立性的本轮专项检查为 `6 passed in 1.05s`，见 recovery-tests.log。只运行既有检查，未改断言。

## 全量结果对应关系

`full.log` 已完整提交，Git blob 为 `07c08bc155ffefd9245783ce9ff7004b7770499d`，结尾：
```
1486 passed, 9 skipped in 556.32s (0:09:16)
```
即 1486 passed / 9 skipped / 0 failed。`git diff b53779c HEAD -- app/src app/tests` 为空；recovery-audit.json 同时保存两个 app tree，值相同。本轮仅修改证据脚本和报告，没有应用或测试实现修改，因此确认并沿用这份全量结果，不将旧日志说成本轮重新执行。补充专项测试退出0；新增真实交互两套脚本退出0。本轮没有新的段错误。

## 未完成 / 未验证

原有 delivery.md 的所有环境边界继续有效：真手机扫码、第二台设备、公网 relay/移动网络、外部推送、iOS/Android系统主屏幕安装均未验证；这些外部验证未完成。F84真实fcitx preedit未取得，保留 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API`，合成不算成功；F06无macOS。test_bot_roundtrip.py:48与test_qml_links.py:143历史段错误未归因，归因工作未完成。正文/阴影及MCP像素残差未归零，没有坐标补偿。文件选择器 GSettings 两次Electron崩溃日志与core继续保留，不能算原生选择器成功。
