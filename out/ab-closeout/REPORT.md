# A/B/C 交付证据索引（补齐原先缺失入口）

本报告核实已有落盘日志，不重做 A/B 修复。原缺失的 REPORT.md 现已补齐。产品提交：A `88b2de2`，B `c141d0d`，C `25883ce`；三项 push 均 rc=0，原始远端行见 a-remote.log、b-remote.log 和 delivery-remote.log。

## A：代码块独立横向滚动

命令：`AI_UPPER_HOME=/tmp/ai-upper-code-scroll CODE_SCROLL_EVIDENCE=out/ab-closeout/a .venv/bin/python -m pytest app/tests/test_qml_code_scroll.py -q -s > out/ab-closeout/a-tests.log 2>&1; rc=$?`。
日志真实结果：

```text
CODE width=7321.0 viewport=682.5 contentX=0->120->6638.5 tail_local_x=630.78125 second_contentX=0.0 bodyY=0.0->0.0
VERTICAL bodyY=0.0->70.51579335804627 code_contentX=6638.5
.
1 passed in 6.14s
rc=0
```

长行 7321px、可见宽 682.5px；真实横向 QWheelEvent：contentX **0→120→6638.5**，另一代码块 **0→0**；正文 contentY **0→0**。
随后普通纵向滚轮正文 contentY **0→70.51579335804627**，代码 contentX 保持 6638.5；尾部 END 的局部 x=630.78125，在可视宽度内。
截图：[长行首](a/code-start.png)、[长行尾](a/code-end.png)。
回归命令：`AI_UPPER_HOME=/tmp/ai-upper-code-regression .venv/bin/python -m pytest app/tests/test_markdown_body.py app/tests/test_markdown_document.py app/tests/test_markdown_chunked.py app/tests/test_qml_code_scroll.py -q -ra > out/ab-closeout/a-regression.log 2>&1; rc=$?`；103 passed in 9.59s，0 skipped，rc=0。

## B：原生断图图标

使用 deva 默认 ReactMarkdown img 对应 Chromium 原生资源：14×16 PNG，16×16 内联槽，6px 容器圆角；裸 alt，无括号包装。细节来源、结构对照在 ../TEST-REPORT.md 的 B 节，DOM 原始值见 deva-image-live.json。
命令：`AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh chat out/ab-closeout/b-after/chat.png /tmp/ai-upper-residual-20261123 config.json > out/ab-closeout/b-after-shot.log 2>&1; rc=$?`，改前目录换为 b-before，两个 rc 均 0。
像素命令：`python3 out/ab-closeout/measure_b.py > out/ab-closeout/b-image-metrics.log 2>&1; rc=$?`，rc=0。

```text
deva bytes=158066 md5=fa884a918c9f9f8267d689c59a1147d1 green_pixels=43 green_bbox=(489, 612, 502, 616)
before bytes=164669 md5=e0a127e4773b01daf6cfddae6b1ad3eb green_pixels=0 green_bbox=None
after bytes=165232 md5=783154083938b2b1e76921e486f210e2 green_pixels=42 green_bbox=(485, 611, 498, 615)
before_after_changed_pixels=769 bbox=(484, 599, 541, 617)
```

断图区域绿色像素 **0→42**，deva 为43；前后变化769像素。图片：[改前](b-before/chat.png)、[改后](b-after/chat.png)、[原版](deva-image-live.png)。
`python3 -I scripts/parity/page_diff18.py out/latest-parity/deva out/ab-closeout/b-before > out/ab-closeout/b-before-diff.log 2>&1; rc=$?`（改后换 b-after），两个 rc 均0；chat严格差异 **112725px/10.74%→112844px/10.75%**，不是整页视觉已闭环。
命令：`AI_UPPER_HOME=/tmp/ai-upper-b-targeted BROKEN_IMAGE_EVIDENCE=out/ab-closeout/b-probe .venv/bin/python -m pytest app/tests/test_qml_broken_image.py app/tests/test_markdown_document.py app/tests/test_markdown_body.py app/tests/test_markdown_chunked.py app/tests/test_qml_code_scroll.py -q -s -ra > out/ab-closeout/b-tests.log 2>&1; rc=$?`；104 passed in 14.27s，0 skipped，rc=0。

## C：全量数字与真实工作区后续修复

历史最终 HEAD **25883cead40d791c006b38f83c5a45ffc13c1df6** 的全量入口：`AI_UPPER_HOME=/tmp/ai-upper-ab-final-head python3 out/ab-closeout/run_final_head.py > out/ab-closeout/final-head-run.log 2>&1; rc=$?`。
该命令使用同 HEAD 的源码快照，231 个 tracked 文件逐字节相同；**1357 passed, 5 skipped in 213.51s (0:03:33)，rc=0**。证据 final-head-verification.json / final-head.log / final-head.rc。
当时真实工作区仍为 **1 failed, 1356 passed, 5 skipped in 214.45s，rc=1**，原报告没有将快照绿冒充原地绿。

本次后续提交 `71ff27b` 已修正 Git 受控路径扫描，保留 .tmp 不清理。真实工作区命令：`AI_UPPER_HOME=/tmp/ai-upper-layout-full .venv/bin/python -m pytest app/tests -q > out/layout-closeout/full-step1.log 2>&1; rc=$?`，**1357 passed, 5 skipped in 211.83s (0:03:31)，0 failed，rc=0**。
变异验证：暂存含旧名的 app/src/brand_mutation_probe.py 后扫描 **1 failed / rc=1**，准确列出路径；已移除，原工作区扫描 **1 passed / rc=0**。原始证据在 ../layout-closeout/scan-mutant.log。

## 未闭环项

E3 组合布局、正文表格底边与间距：本次第3项处理中，最新结果追加到 ../TEST-REPORT.md，不把旧证据当作已修。
用户明确延期：emoji 缺字形、deva 2x 对照、CI 终态归因、settings 遮罩内部残差、long-mid 非悬停差异、18页全量重拍。
