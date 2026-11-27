# 本轮独立收口报告

本轮没有宣称整份移植任务完成。盘点判定完成，功能补齐和像素仍有下述未完成部分。

## 全量计数

| 范围 | 已实现且可用 | 只有界面 | 未移植 | 不适用 | 合计 |
|---|---:|---:|---:|---:|---:|
| 全量当前功能候选 | 43 | 1 | 43 | 2 | 89 |
| 原先未判定的 59 项 | 23 | 1 | 33 | 2 | 59 |

四态之外没有待判定。原来的 85 项之外补出 Git 面板及当前原版工作树 3 个真实新通道。部分实现的组合项保守记未移植；web 入口单列，现有 mvvm/webui 后端不能算 QML UI。完整清单和源码/接线/搜索/验证证据见 feature-parity-gap.md/.json。

## 逐项提交与验证

| 项目 | commit / 已核验远端 SHA | 验证结果 | 证据 |
|---|---|---|---|
|全量盘点|`25c04ab8ff43d996553e7321a21ded11bf21aa8c`|89 项完整四态，原 59 项全部判定；172 IPC 与 189 preload 调用；270 源文件、1097 非 IPC hook 行|[feature-parity-gap.md](/home/agent/shared_workspace/ai_upper/docs/audit/feature-parity-gap.md)|
|系统代理与 NO_PROXY|`e90dcb17759b05dbdb79b869305dc5070fcc68c2`|真实 PAC/libproxy/WebKit 与 loopback 验证环境代理、直连、换路由、origin 记忆、反向换回；不重放已送达请求|[final-port-network.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-network.md)|
|系统代理兼容层|`1ab1b28a05dde9d2e24fcd5d6d5abd9bdd3a2332`|仅改 Qt 导入路径，真实网络脚本复跑 PASS|[proxy-routes.json](/home/agent/shared_workspace/ai_upper/docs/audit/evidence/proxy-routes.json)|
|定时任务入口|`11839f8a743db506111fafd1ef47bcc6f858c588`|真实点击创建/暂停/恢复，到时真实宿主执行，历史写盘、打开和删除|[final-port-tasks.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-tasks.md)|
|定时任务兼容与时区|`19479eb07d998063a2d7aab4c1dc6e295ff5420f`|真实 cron 下一分钟自动执行；星期与 DST 检查；无效时区拒绝|[cron-timer.json](/home/agent/shared_workspace/ai_upper/docs/audit/evidence/cron-timer.json)|
|机器人入口|`1c64ffda7889d2662fe2de5125081d087bd7ab0b`|真实配置列表/回复模式/范围/删除读回；外部配对收发未验证|[final-port-bots.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-bots.md)|
|机器人原生控制器|`34b91329cdecabe146e36fb69e510f1403d69710`|延迟构建真实 QObject，去除未核验的空 Signal 兜底，暗亮交互复跑|[bots-ui.json](/home/agent/shared_workspace/ai_upper/docs/audit/evidence/bots-ui.json)|
|@ 候选|`7a9aeb33fb99cd4b3d43b8473c6409b4e6a69b71`|光标处成员/角色候选，选择替换并保留后文；后台成员语义未移植|[final-port-mentions.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-mentions.md)|
|候选菜单可见性与 /compact|`da31437ecb7229cfe10f00de0ac765384a9d0750`|修正真实父级坐标错误；真实鼠标选择候选；未替换的压缩服务与磁盘摘要读回|[final-port-compact.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-compact.md)|
|同数据布局与菜单上下展开|`8c85c29c8431f59d4a2de11c7c011d89c2692b6e`|字段几何复核一致；上/下展开真实点击、暗亮截图|[extensions-rounding.md](/home/agent/shared_workspace/ai_upper/docs/audit/extensions-rounding.md)|
|未读与待处理|`2c78f343e4ed773217c078b9a7bb42c321fd3d0e`|后台事件发布修复；真实 pending 文件、点击/回答读回；两主题红点|[final-port-unread.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-unread.md)|
|托盘/通知修正|`2c0c0867ec10c21966cff6d88b4be8dd10e93132`|补真实任务菜单、无托盘不隐藏窗口、后台通知和点击定位；宿主成功态未验证|[final-port-tray.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-tray.md)|
|单实例兼容与复核|`aa826409bef2851e6459de2f7298ebe078ad9fec`|两个真实应用进程，第二个退出 0，首进程收到 socket 激活；真实 WM 焦点未验证|[final-port-single-instance.md](/home/agent/shared_workspace/ai_upper/docs/audit/final-port-single-instance.md)|

每次 git push 原始输出与紧随的 git ls-remote 行见 final-port-pushes.md；push-manifest.json 记录所有提交均存在于 origin/develop。此前外部执行的 bbe9603、4bee356、dfd6c05、68abc0a、2880334、a27d0c8 保留，但不冒领其原始推送记录。独立复核发现并修复了候选菜单屏外、后台红点不发布、托盘菜单缺项等问题。

## 原版成功态和相位边界

真实私有 D-Bus/GNOME Secret Service：Electron safeStorage available=true / saved.ok=true / has=true，Qt keyring 保存后读回成功，两端实际 Saved 可见。相同 fixture，1280×820，滚动 142。字段 y = 233.5 / 304 / 374.5 / 490.5 / 614.5 两端一致，未发现仍存在旧报告的 63px 纵向差异，没有改字段 token 或加补偿。

同尺寸图：[暗色同数据对照](/home/agent/shared_workspace/ai_upper/out/final-port/same-fixture-dark.png)、[亮色同数据对照](/home/agent/shared_workspace/ai_upper/out/final-port/same-fixture-light.png)。

正文与阴影 **未归零**：0.5 相位六段文字起始行重合，0/1 相位部分行差 1px；亮色阴影采样 137 vs 138。相位只在实验脚本改变，没有进入生产布局。详见 extensions-rounding.md 末节与 evidence/phase-measurements.json。

## 原始残留与并发处理

812fd57 及 electron_safe_storage_session.py 保留、不回退、不删除；旧脚本不是本轮隔离验证入口。本轮入口是 scripts/parity/final_port/identical_os.py。原审计覆盖差异保存在 evidence/parity-overwrite.diff。执行中仍出现未由本执行生成的提交/未提交改动；未核验兼容补丁 diff 保存在 evidence/unverified-compatibility.diff，去掉空 Qt 替身和静默时区回退，逐项复跑后提交。

deva 保持只读；实际原版工作树已有其他来源改动，依据磁盘快照枚举并记录 SHA256，收尾发现 4 个文件漂移与 1 个新增 member-folder 模块；重新枚举后仍是 172 IPC / 189 preload / 1097 hooks，源文件增为 270，见 evidence/reference-drift.json。应用/测试 AI_UPPER_HOME 均隔离到 /tmp；没有写真实 ~/.ai_upper。没有 force push、分支/tag、依赖 pin 变更，也没有修改既有测试断言。evidence/tests-since-handoff.diff 只有其他执行添加的四个新测试文件。

## 未完成（不能写成已完成）

- /rewind 与技能指令集合未移植；/compact 已真实验证。
- @ 候选与文本替换已接，自动创建成员与后台提及分派未移植。
- 机器人配置管理已可用；真实 Telegram 凭据/配对/外部收发/流式更新未验证，飞书/Web 适配器未移植。启用无密钥的真实错误为“机器人密钥不存在或系统密钥库不可用”。
- 定时任务入口、once/cron 执行已验证；完整任务详情编辑、原版主对话结果交接、远程推送仍未完成。
- 系统托盘和系统通知成功态未验证：真实 offscreen 宿主 isSystemTrayAvailable=False。单实例的真实 WM 聚焦效果也未验证。
- 正文与阴影栅格残差未归零。Windows/macOS 系统代理未在对应宿主验证；Linux PAC 依赖宿主 libproxy，仓库运行库只用于本轮实证。
- 单独运行 test_mvvm.py::test_every_mvvm_module_imports 曾在既有 humation.py 的模块级 QtQml 导入处失败；全套执行因模块预载能通过。这是独立测试的顺序依赖，未为变绿更改既有测试或无关模块。

最终固定源码全量回归：

```sh
AI_UPPER_HOME=/tmp/ai-upper-final-stable TMPDIR=$PWD/.tmp/final-port \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-final-stable-tests
```

```text
1445 passed, 9 skipped in 440.75s (0:07:20)
```

failed = 0，exit code = 0。原始日志 out/final-port/pytest-final.log，已复制到 evidence/pytest-final.log。运行期间 app/src 与 app/tests 相对 da31437 无变化；后续只提交文档与证据。
