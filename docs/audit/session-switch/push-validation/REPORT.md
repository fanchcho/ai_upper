# 最终 develop 推送前验证

用户明确覆盖此前“不 push”的限制，授权验证通过后只执行 git push origin develop。目标 origin 为 git@github.com:fanchcho/ai_upper.git。没有 force、标签、其它分支或 deva 操作。

## 版本与保留范围

本轮未修改产品代码。接受验证的代码 HEAD 为 9b5775a06ae0e0314e9f396773fb91f29da6c760。推送前远端 develop 为 a27ee635e1ba6219a002c58707cb7c47aab59dc8，本地包含其祖先，可正常快进。报告提交只增加文档和验证数据。

最终保留：
- 5f45c28 批量归档最终状态一次发布（前序工作，非本轮新修复）。
- 11c63f2 单次 renderer 内复用纯文本表格单元格测量。
- 67edda7 多选原地数组更新、全选 ID 准备及全选 delegate 快路径。
- bbd3e3f 后台正文准备，返回 fragment/image 值对象，GUI 独占显示文档。
- 965c385 恢复单次 GUI 挂接，撤回分段。

已回退且不在最终运行时代码：O(1) 查询候选、0037a65 的两阶段挂接、跨线程 QTextDocument QObject 移交、屏蔽表格格式通知、倒序网格处理和无稳定收益的 undo 修改。0037a65 等历史提交仍在历史中，遵守“不改写历史”；它们的运行时效果已由后续提交撤回。失败候选的补丁/文字只作为审计文件，不被产品导入。

slices/ 在 80bc3b5 已提交，本轮保留全部历史证据。最终报告中不将被拒绝候选的数据称为已交付性能。

## 三组最终性能与帧验证

运行代码保持不变。使用 costs/switch.py，同一 24 条真实落盘会话、每条 30 轮正文、相同顺序与 offscreen/software 后端；等待 rendered 完成后抓帧。每组新进程、独立 /tmp home，每侧没有并发 pytest/profile。notify 记录 GUI 最长单次事件。

|组|N|完整帧中位 ms|P95 ms|最长 GUI 事件 ms|RGB 对照|
|---|---:|---:|---:|---:|---|
|1|24|133.720|138.963|71.962|bbox=None|
|2|24|134.551|161.656|94.585|bbox=None|
|3|24|139.289|172.215|88.364|bbox=None|
|合并|72|136.442|161.656|94.585|三组一致|

点击派发中位 11.232 ms。三组截图分别与已提交 costs/sync-{1,2,3}.png 比较，RGB 每个像素一致；每次点击目标正文末轮文本、标题和 activeId 断言全部通过。所有测量子进程退出码 0。

目标中位≤60、P95≤80、最长事件≤16.7 ms 均未达。本次是确认最终保留代码的功能和真实性能，不把未达性能阈值写成达成，也不把这项测试通过理解为延迟已解决。A 维持用户裁决，100000 行前轮最长点击事件 17.030 ms 的边界证据仍保留。

复现命令（仓库根）：

```bash
python .tmp/push-closeout/verify.py
# 每组子进程：
AI_UPPER_HOME=/tmp/ai-upper-push-final-1 \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python docs/audit/session-switch/costs/switch.py .tmp/push-closeout/final-1
```

原始输出 final-{1,2,3}.log（含退出码），数据同名 JSON，聚合 summary.json；verify.py/verify.log 保留断言和命令。运行时临时文件在 .tmp/push-closeout。

## 推送收据

本报告随验证提交推送。实际 push 命令、完整输出、最终本地 HEAD 和 ls-remote 结果在工作区 `.tmp/push-closeout/PUSH-RECEIPT.md` 保存，并在最终答复提供绝对路径。收据在 push 后生成，不为把最终 hash 写回自身而追加递归提交；工作树仍保持干净。只有推送命令成功且 ls-remote hash 等于本地 HEAD 才报告已推送。


## 最终全量 pytest

验证时运行代码未改动，性能测量结束后才运行全量测试，没有并发干扰：

```bash
AI_UPPER_HOME=/tmp/ai-upper-push-full-tests QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest --basetemp=/tmp/ai-upper-push-full-pytest -q
```

真实输出：`1396 passed, 9 skipped in 271.24s (0:04:31)`；failed=0，进程退出码 0。跳过项沿用项目条件，未把 skip 当作执行通过。完整 stdout 在 pytest-full.log。git diff --check 无输出。

本轮仅新增验证文档，产品源码相对验证 HEAD 完全不变。已明确记录性能阈值未达，不把它当作缺失测试；本轮功能回归、进程退出、最终帧一致性和证据均通过，按最新授权推送最终保留提交。
