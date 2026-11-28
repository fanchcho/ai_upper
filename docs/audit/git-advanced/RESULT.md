# Git高级交互增量收尾
版本台阶仅引用已核实事实：用户客户端未知／本地副本0.1.17+75提交／上游main0.1.17／移植声明基线0.1.16。本轮不重新猜测或更新版本。

| 要求 | 交付 | 边界 |
|---|---|---|
| 旧表单不可达 | REACHABILITY.md、reach暗亮截图和visible=false | 兼容Popup留给旧内部测试，无UI接线 |
| 尺寸表 | GEOMETRY.md、主148×219、分支300×295 | 固定分支宽、筛选样式、字体行盒仍未完全同构，未完成 |
| 强制删除 | FORCE.md、force暗亮JSON/confirm图 | 独有1提交，取消保留、确认消失 |
| 远程删除 | REMOTE.md、remote暗亮JSON/confirm/failure图 | 本地bare真实push --delete；失败原文可见，不算公网 |
| 合并冲突 | MERGE.md、merge暗亮JSON/conflict图 | 真实冲突a；中止后status空/MERGE_HEAD128；Toast外观仍有差异 |
| 身份select | IDENTITY.md、identity暗亮JSON/missing/scope图 | 真缺身份才显示，选全局写/tmp隔离Git配置并读回；本地定制来源，不冒称上游main |
| AI生成停止 | AI.md、ai暗亮JSON/running/stopped图 | 真HTTP请求，阻塞时取消线程已退出；未验证真实模型返回 |

所有PNG为1280×1060、Linux软件渲染完整QML窗口；脚本advanced_interaction.py通过真实QTest鼠标键盘调用ShellBridge及git进程。未修改依赖pin、Theme token、旧断言、deva或真实~/.ai_upper。运行清理时Main.qml:69 saveError-null警告保留原日志。

第一轮全量约62%被SIGTERM终止，工具exit143；没有完整结果，没有Python崩溃栈；保留pytest-interrupted-143.log。不能推断终止来源，也不把它写成通过。最终重跑日志pytest-final.log，结果完成后追加。应用代码自8b966b6冻结；其后只有文档/证据脚本变更。

未完成：原版macOS同状态像素对照（无宿主）；菜单自适应宽、筛选字段严格样式和行盒DOM量取；冲突toast完整视觉；外部真实模型返回；浅色warning按原版规则2.494:1保留。历史段错误未归因，本轮不升级结论。

最终重跑原文：1486 passed, 9 skipped in 560.64s (0:09:20)，进程exit0，即1486通过/9跳过/0失败。最终应用代码与8b966b6相同，git diff 8b966b6 -- app/src app/tests app/pyproject.toml为空。首轮SIGTERM原因未归因，重跑通过不覆盖该风险。没有本轮Python段错误栈或core产生证据，不宣称历史崩溃已修复。
