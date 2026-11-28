# 全前序顺序二分实际执行

从迁后pytest --collect-only取得1495个node，按原顺序切分目标之前的全部前序。plan.json保留每个node；order_prefix_bisect.py可复跑。每组独立进程、/tmp home、faulthandler/core启用、offscreen/software，不预载Qt，不改断言。

|组|原序前序范围（零基）|含目标总数|实际结果|
|---|---|---|---|
|bot-first|0..24|26|26 passed，0.90秒|
|bot-second|25..50|27|26 passed / 1 failed，1.89秒；迁移文档裸旧名断言|
|qml-first|0..483|485|480 passed / 4 skipped / 1 failed，42.54秒；同一文档断言|
|qml-second|484..968|486|480 passed / 5 skipped / 1 failed，185.27秒；MCP取消消息语言断言|

首次收集器误以为node带app/前缀，实际pytest以app为root返回tests/，原ValueError保留collection-format-error.log，已只修正审计脚本路径解析。首次组结果没有覆盖。

文档旧别名裸写触发既有仓库命名检查：已将路径写成完整历史路径并把JSON字段改成legacyEntry，doc-fix.log证实1 passed。没有改测试断言。

MCP失败是另一个确定的测试顺序/语言状态问题：mcp_runtime.py:171抛出tr('legacy.be14f46f4f53')，zh-CN.json:1508翻译为“MCP 取消或超时；执行结果可能未知”，test_plugin_runtime.py:91匹配英文cancelled。该分组拿到中文，单独运行cancel-isolated.log为1 passed/0.59秒。未更改产品翻译或既有断言；这不是Qt段错误归因，不用全量通过抹去此失败。

历史两目标在四组均执行且未SIGSEGV。完整前序组合也由本轮全量覆盖，但仍无稳定崩溃oracle，故不能继续选出“失败半区”；继续机械切更小组不会构成因果定位。不能排除跨半组组合、异步时序、对象销毁后定时器或第三方库缺陷。只排除“本次这些固定子序列必然崩溃”这一很窄的假设。

既有core直接故障为notifyInternal2读取空QObject私有指针+0x58（remaining-boundaries/receiver-instructions.log），尚无谁清空该指针的记录。下一步需与当前PySide6/Qt6.11.2一致、aarch64带调试符号的QtCore/QtGui/QtQml/QtQuick/QtTest及Shiboken/PySide配套构建，启用ASAN并保证整个进程一致使用，记录QObject创建/销毁、timer receiver地址；不能只混入系统Qt6.8符号或LD_PRELOAD掩盖。bot还需可归属的原生core。根因未完成、未修复。

最终全量日志另见pc-migration/full-final.log；即使通过，上述分组失败与生命周期警告仍保留。

最终入索引后全量：1486 passed / 9 skipped / 0 failed，557.96秒，exit0；未发生SIGSEGV。分组的MCP语言断言失败仍保留，不以全量通过消除风险。
