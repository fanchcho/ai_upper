# long-mid：修复滚动后悬停行绑定

## 根因及修复

`Main.qml::forceHoverRow` 把 long-mid 和 chat 一起固定为 11。long-mid 的 contentY=1386 后，第 11 行已滚出视口，所以无 hover 带；不是 HoverHandler 收到状态后未重绘，也不是需要改变滚动位置才能出现。保持原 contentY，以现有截图指针 y700、列表 y56、行高54计算当前行索引，并让绑定随 contentY 更新。

只改 Main.qml 的 long-mid 分支。新增 test_long_mid_hover_tracks_the_visible_row_after_scrolling：先证明 long-mid y680 悬停色存在，再滚动20px验证新/旧区域着色，最后返回 chat 证明原 y660 悬停不回归。没有删除或放宽任何旧测试。

## 实测

| 指标 | 改前 | 改后 | deva |
|---|---:|---:|---:|
| 精确悬停色行数 | 0 | 54 | 54 |
| 悬停带范围 | 无 | (668,721) | (668,721) |
| 全页差异 px | 142100 | 130345 | — |
| 全页差异 % | 13.538490853658537 | 12.418540396341463 | — |

本轮改前值已包含起点 ab66967 的裸 alt 修复，所以不是上一轮旧图的 142444。只重拍 long-mid 改前/改后，命令退出码均0，数据来自 long-mid/before.json 和 after.json。

活动会话 parity-000 与参考的第6个会话不一致、首完整行026/027不同，属于页面驱动的其他残差；此修复只关闭所请求的0/54行悬停缺口，不把整页称为对齐。

## 命令与退出码

```bash
AI_UPPER_HOME=/tmp/ai-upper-residual-long-tests .venv/bin/python -m pytest app/tests/test_qml_sidebar.py::test_long_mid_hover_tracks_the_visible_row_after_scrolling -q > out/residual-20261123/long-mid/test-before.log 2>&1
echo rc=$?
# 1 failed in 5.20s，rc=1；(247,247,248) != (236,236,237)
AI_UPPER_HOME=/tmp/ai-upper-residual-long-tests-after .venv/bin/python -m pytest app/tests/test_qml_sidebar.py app/tests/test_qml_scrollbars.py app/tests/test_qml_shell.py -q > out/residual-20261123/long-mid/test-after.log 2>&1
echo rc=$?
# 53 passed in 34.91s，进程退出时段错误，rc=139，不能算进程通过
AI_UPPER_HOME=/tmp/ai-upper-residual-long-isolated .venv/bin/python -m pytest app/tests/test_qml_sidebar.py -q > out/residual-20261123/long-mid/test-sidebar.log 2>&1
echo rc=$?
# 2 passed in 9.96s，rc=0
AI_UPPER_HOME=/tmp/ai-upper-residual-long-shell .venv/bin/python -m pytest app/tests/test_qml_shell.py -q > out/residual-20261123/long-mid/test-shell.log 2>&1
echo rc=$?
# 49 passed in 15.28s，rc=0
AI_UPPER_HOME=/tmp/ai-upper-residual-long-scroll .venv/bin/python -m pytest app/tests/test_qml_scrollbars.py -q > out/residual-20261123/long-mid/test-scroll.log 2>&1
echo rc=$?
# 2 passed in 10.64s，但退出段错误 rc=139
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh long-mid out/residual-20261123/long-mid/after.png /tmp/ai-upper-residual-20261123 > out/residual-20261123/long-mid/after.log 2>&1
echo rc=$?
# rc=0
```

旧基线组合 52 passed / rc=0，没有证明本机退出崩溃在旧基线同组合必现；不能擅称为既有问题。所有失败退出记录保留。完整回归使用之前已有的隔离检出，将当前5份变化源码/测试逐字复制进去（regression-manifest.log 含SHA-256），避免主工作树 .tmp 中兼容夹具被仓库递归测试扫描；没有新建分支或改变任何 Git 历史，全部提交仍在 develop。

最终完整回归：**1351 passed, 5 skipped in 174.06s (0:02:54)，rc=0**，日志 test-full.log/test-full.rc。相较旧1349，新加2条分别是起点 ab66967 的图片测试和本轮悬停测试，未删测。

进一步排除本轮 hover 变更：临时复制 QML 资源并将 Main.qml 取自本项改前 HEAD，不改变工作树，再用 qml_shell.qml_main 指向这份只读资源运行未改动的 scrollbar 模块，得到 **2 passed in 10.31s 后 rc=139**（test-scroll-baseline.log）。说明该退出崩溃在旧 Main.qml 也能复现；组合重跑则53 passed后rc139。此退出问题没有修复，作为特定模块顺序/生命周期残留记录，不掩盖也不据其修改测试。完整回归本次正常退出。
