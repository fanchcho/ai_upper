# 全量测试与遗留缺陷复核报告

本轮测试与归因复核已落盘；**没有新增产品修复，不能据此宣称视觉对齐全部完成**。完整套件在同一基线、同一本地应用配置、隔离测试输出目录下为 **1349 passed / 0 failed / 5 skipped，rc=0**。10 个指定复核项逐项独立提交，2 项原“缺三行”描述不再复现，8 项仍保留差异/待处理状态。E1/E5 的段距与图片残差并未随计数纠正而消失。

## 0. 基线与工作树归属

- UTC 日期：2026-11-23。启动基线：`c660bf887aea5eb4e3e9c68f8c6833c95294bbb7`；分支 `develop`；远端 `origin/develop` 开工时同 hash。
- 首条仓库检查为 `git status --porcelain`。已跟踪文件修改 **0**；遗留未跟踪条目 **244**（目录条目不展开，不能称 244 个文件），均在 out 下，为前序探针/截图/日志。本轮未纳入、改写或删除它们。清单见 [git-status-initial.log](retest-20261123/logs/git-status-initial.log) 和 [ownership.log](retest-20261123/logs/ownership.log)。
- 本轮新增交付集中在 `out/retest-20261123/` 和本报告；临时数据位于 `.tmp/retest-20261123/`。启动检查的两份短日志随后立即收归该目录。
- 没有检查或修改 Codex 全局配置。本轮无源码、测试、应用配置修改；隔离检出仅复制仓库原有的 Git 忽略应用配置以恢复相同运行前提。
- 环境：Python 3.13.5、pytest 9.2.0；解释器 `.venv/bin/python`。测试工程师的 `6db617a` QML 生命周期修复已在基线祖先中。

## 1. 全量测试：保留每轮真实结果

| 运行 | rc | passed | failed | skipped | 耗时 | 归因 |
|---|---:|---:|---:|---:|---:|---|
| 首跑，主工作树 | 1 | 1348 | 1 | 5 | 170.05s | 仓库递归改名检查扫描到了 `.tmp/` 内旧名兼容测试自身生成的 pyproject 夹具 |
| 同基线隔离检出，尚未复制本地应用配置 | 1 | 1299 | 50 | 5 | 170.46s | Git 忽略的 app/pyproject.toml 未随 worktree 检出；50 项 traceback 为配置缺失 |
| 同基线隔离检出 + 相同本地应用配置 | **0** | **1349** | **0** | **5** | **167.94s** | 完整套件通过，无排除、无改测试、无源码修复 |

日志：[首跑](retest-20261123/logs/pytest-full.log)、[隔离首跑](retest-20261123/logs/pytest-isolated.log)、[最终完整复验](retest-20261123/logs/pytest-final.log)，各有同名 `.rc` 文件。主工作树首次失败的断言对象明确是 `.tmp/.../test_paths_reads_a_legacy_app_0/app/pyproject.toml`；这是测试输出放在被扫描仓库内部造成的污染，不能记为本轮产品回归。

最终命令（cwd 为 `.tmp/retest-20261123/baseline-checkout`，所有绝对路径仍在宿主工作区内）：

```bash
TMPDIR=/home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/tmp \
AI_UPPER_HOME=/home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/test-home-final \
/home/agent/shared_workspace/ai_upper/.venv/bin/python -m pytest app/tests -q -ra \
  --basetemp=/home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/pytest-final \
  > /home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/pytest-final.log 2>&1
retest_rc=$?
echo rc=$retest_rc
```

隔离检出是 `git worktree add --detach .tmp/retest-20261123/baseline-checkout c660bf887aea5eb4e3e9c68f8c6833c95294bbb7`。复制前后本地应用配置 SHA-256 均为 `fc979936f0cfba16d08e208aebd81bafb926528d4e59e4b22c97a729e5b7892c`。这修复的是检出前提，未变更原仓库配置。全量结果与前序同口径 **1349 passed / 5 skipped** 一致；没有用历史增强 PATH 环境的 1350/4 冒充当前结果。

5 个 skip：Windows 专属两项；需 `AI_UPPER_E2E=1` 的构建 E2E 两项；需 cc/patchelf/readelf 的 native 一项。最终原始日志列出完整 skip 原因。这些门禁未执行，不能算通过。

## 2. 截图与测量可比性

当前代码重新拍摄 9 页：chat、search-none、long-mid、long-bottom、设置四页、delete-confirm。每页真实 headless 运行 rc=0，1280×820。新生成夹具显示 `21 hr ago`，与历史 `yesterday` 参考标签不同；首先逐像素证明只有侧栏时间标签受影响，再只将临时夹具时间戳前移 6 小时。归一化后 **9/9 新 QML 图 MD5 与对应已跟踪 QML 图完全一致**，证据 [compare-normalized.log](retest-20261123/logs/compare-normalized.log)。所以本轮改前→改后计数不变是实测结果，不是复制旧图冒充重拍。

deva 使用已跟踪参考 PNG，本轮没有访问或重新运行工作区外的 deva。其 SHA-256 与 QML 的 SHA-256 均记录在 [measure-current.json](retest-20261123/logs/measure-current.json)。该比较验证当前 QML 对仓库参考的状态，不宣称外部 deva 最新版同场景验收。

复现测量：

```bash
python3 out/retest-20261123/measure.py out/retest-20261123/qml > .tmp/review-measure.json 2> .tmp/review-measure.err
echo rc=$?
```

实际运行时插桩入口 [runtime_probe.py](retest-20261123/runtime_probe.py) 只观察窗口/文档，不更改页面状态。chat/search-none/long-mid 的日志含真实活动会话、contentY、contentHeight、完整文档文本与块坐标。采样结果不依赖单元测试通过来推断视觉一致。

## 3. 指定项逐项结论与独立提交

下表“前→后”是基线截图重读→当前代码重拍；**本轮未做产品修复**。每项 commit 为独立复核文档提交；共同原始证据提交为 `738e3f5`。历史 `dc05e31` 修改了块间距/图片路径，`2a6e2a3` 只改表格，不能把 E1/E3/E4/E5 整体归功于后者。

| 项目 | 当前结论 | 改前→改后实测 | 独立 commit |
|---|---|---|---|
| [E1](retest-20261123/E1.md) | 原缺三行已不存在；段距残差归 E3 | 原始带 18→18（deva 19）；图标/文字聚合 18→18（deva 18） | `f1f8818` |
| [E3](retest-20261123/E3.md) | 仍存在，未修复 | 首带 −3→−3 px；18 带位移范围 −28..−1→−28..−1 px | `25983b4` |
| [E4](retest-20261123/E4.md) | 仍存在，未修复 | 占位文本 8→8 字；目标裸 alt 3 字 + broken-image 图标 | `314073f` |
| [E5](retest-20261123/E5.md) | 原缺三行已不存在；共享 E3/E4 | 原始带 18→18（deva 19）；聚合 18→18；chat/search-none 文档相同 | `14580a6` |
| [long-mid](retest-20261123/long-mid.md) | 仍存在：两端会话/滚动/hover 不一致 | 差异 142444→142444 px；hover 0→0 行（deva 54） | `6049ac8` |
| [settings-general](retest-20261123/settings-general.md) | 残差仍存在；遮罩量化已归因 | 差异 315274→315274 px；内部 >8 为 5732→5732 px | `cbd9cba` |
| [settings-models](retest-20261123/settings-models.md) | 残差仍存在；遮罩量化已归因 | 差异 300497→300497 px；内部 >8 为 1596→1596 px | `59ce692` |
| [settings-extensions](retest-20261123/settings-extensions.md) | 残差仍存在；遮罩量化已归因 | 差异 305797→305797 px；内部 >8 为 4777→4777 px | `f4024b5` |
| [settings-about](retest-20261123/settings-about.md) | 残差仍存在；遮罩量化已归因 | 差异 302389→302389 px；内部 >8 为 2114→2114 px | `7a1ac0e` |
| [delete-confirm](retest-20261123/delete-confirm.md) | 残差仍存在；遮罩量化已归因 | 差异 382652→382652 px；内部 >8 为 6645→6645 px | `b3fe97f` |

E1/E5 的证据纠正：原始暗像素带为 18 对 19，参考图最后一行的 broken-image 图标单独形成 y602 带，alt 文字为 y606–619。按不超过 3 个空白像素行聚合后为 18 对 18；这只是避免把图标分裂计成正文行，不代表所有段距一致。旧报告 search-none 的 15/16 也不符合当前同区域重测，已在独立复核中更正。

E3 的起点差不是统一 3 px：逐带范围 −28 至 −1 px；运行时正文已经在真底。long-mid 则更严重：QML 仍是 parity-000，而 deva 参考已选中第 6 个会话；侧栏首完整会话 026/027 不同，强制 hover=11 已滚出视口。不能把其整页差异归到 Markdown 引擎。

## 4. 设置四页与 delete-confirm 拆层

| 页 | 全页差异 px | 弹窗外 px | 外部 ≤2 px | 弹窗内 px | 内部 >8 px |
|---|---:|---:|---:|---:|---:|
| settings-general | 315274 | 297039 | 248842 | 18235 | 5732 |
| settings-models | 300497 | 297039 | 248842 | 3458 | 1596 |
| settings-extensions | 305797 | 297039 | 248842 | 8758 | 4777 |
| settings-about | 302389 | 297039 | 248842 | 5350 | 2114 |
| delete-confirm | 382652 | 375172 | 301200 | 7480 | 6645 |

设置四页外部差异完全相同，取样 `(60,120)` 的 QML `(143,143,144)` 与 deva `(144,144,144)` 相差 `(-1,-1,0)`，支持共享遮罩量化来源；但外部并非全部 ≤2，面板内部还各有不同残差。不能把“主要是遮罩”扩展成“内部没有缺口”。delete-confirm 标题/说明暗像素包围框还有 1–2 px 差，数据见独立文档，未以调色压低总差异。

## 5. 完成度与未解决项

- [x] 固定真实基线并判断遗留工作树归属。
- [x] 先运行完整 pytest，保存所有真实 rc/统计；同基线证明环境失败原因，不改测试。
- [x] 10/10 指定复核项形成独立实测结论与 commit；9/9 页面重拍及哈希校验。
- [x] 完成总报告、原始日志、测量脚本和运行时证据。
- [x] 10 个独立复核提交及共同证据已 push；原始 ls-remote 与本地提交一致。总结提交的最终核验随交付保存。

**复核覆盖率 10/10；本轮产品修复数 0。不能报告“视觉缺陷全部关闭”。** E1/E5 原缺行描述不再复现；E3、E4、long-mid 及 5 个模态页的残余差异仍在。

待解决/卡点：

1. E3 需同步 deva DOM 与 QTextDocument 的逐块几何，处理非均匀段距及视口裁切；当前没有工作区内可运行的 deva 同场景环境，只有已跟踪截图和历史证据。
2. E4 需区分 URL 策略拦截的 data URI 与一般 missing image，再明确 broken-image 图标/alt 语义；现有通用占位测试契约未变更。
3. long-mid 需统一两端选中会话、滚动行身份和鼠标位置，当前两侧不是同一状态。
4. 设置和确认弹窗内部 >8 差值仍需按控件/字形定位；已测数量不足以断言全部是光栅差，也不能等价成对应数量的功能缺陷。
5. 5 个 pytest 环境门禁用例仍跳过。本轮不涉及此前报告中的其他开放项，不替它们宣称完成。

本轮范围按用户原文“全量测试 → 遗留项归因复核 → 完成度总结 → 独立 commit/push”执行。没有将测试复核冒称实现修复。未改变产品代码，所以完整基线套件已经覆盖本轮产品树，后续只校验文档/证据一致性。

## 6. 提交与远端核验

逐项完整 commit 映射：[review-commits.json](retest-20261123/review-commits.json)。第一批 11 个提交（共同证据 + 10 项独立复核）已执行 `git push origin HEAD:develop`，rc=0；`git ls-remote origin refs/heads/develop` rc=0，原始行：

```text
b3fe97f9462618afb6a2c911143c3bb28c7f31f9	refs/heads/develop
```

见 [push-reviews.log](retest-20261123/logs/push-reviews.log)、[ls-remote-reviews.log](retest-20261123/logs/ls-remote-reviews.log)。总结报告随后另作一个提交并推送；最终报告提交 hash、push rc 和最新 ls-remote 原始行由交付时的 `out/retest-20261123/publish-verification.txt` 保存。该运输回执是本地交付文件，不纳入它自身要证明的提交，避免自引用 hash；最终回复引用该文件和原始行。

交付校验：[verification.log](retest-20261123/logs/verification.log)。已验证 9/9 截图/哈希/退出码、3/3 全量测试统计、10/10 独立提交归属、报告链接存在，以及产品和测试树相对基线差异为零。
