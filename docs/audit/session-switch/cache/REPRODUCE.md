# 复现

在仓库根目录运行，先保存未提交改动。基线 468f5b7，候选是当前工作树。不要并行跑 pytest。

```bash
mkdir -p .tmp/hot-cache
cp docs/audit/session-switch/cache/{measure.py,accepted-runs.py,summarize.py,profile.py,stress-flush.py} .tmp/hot-cache/
git show 468f5b7:app/src/qml_shell.py > .tmp/hot-cache/bridge-before.py
git show 468f5b7:app/src/markdown/body.py > .tmp/hot-cache/body-before.py
python .tmp/hot-cache/accepted-runs.py > .tmp/hot-cache/accepted-runs.log 2>&1
python .tmp/hot-cache/summarize.py
```

runner 顺序运行六次、临时换源码且 finally 恢复；不可在它运行期间编辑源码。证据生成时 runner 使用固定的 /tmp/ai-upper-finaldisplay-* 未存在目录；交付 runner 仅将这些应用目录后缀改为随机值，允许再次执行而不与上次目录冲突。timing/夹具不变。LD_LIBRARY_PATH 为本机已有 Qt 运行库路径，无依赖 pin 变更。跨机器需要同样的 Qt/字体/窗口尺寸；不可把跨机器结果与本报告绝对值直接比较。

压力与 profile 需独立的新 AI_UPPER_HOME，均在 /tmp。stress-flush.py 与初始 stress.py 的唯一区别是每轮清空 DeferredDelete，以模拟真实 app.exec 的延迟销毁。压力样本不替代 24 会话标准口径。

全仓库：

```bash
AI_UPPER_HOME=/tmp/ai-upper-display-full QT_QPA_PLATFORM=offscreen \
LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 \
.venv/bin/python -m pytest --basetemp=/tmp/ai-upper-display-full-base -q
```

再次执行请选择新的 /tmp 应用/pytest 目录。实际日志 pytest-full.log；没有按文件筛选。


最终复测与释放修复：`final-release.py` 依次生成 release-after-{1,2,3} 再执行全量pytest；这一次pytest失败记录保留在 final-release-exits.json，不能当通过。之后仅修改审批用例的异步等待方式，再执行以下最终全量命令：

```bash
AI_UPPER_HOME=/tmp/ai-upper-cache-final-suite QT_QPA_PLATFORM=offscreen LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu" PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest --basetemp=/tmp/ai-upper-cache-final-suite-base -q
```

最终逐项退出码以 FINAL-EXITS.json 为准；产品源码在release-after三组之后未变化，仅测试等待方式调整。
