# 剩余五项专项执行报告（2026-11-23）

本轮完成 long-mid 悬停修复、设置内部缺失标题/阴影及基线偏移修复，并给出 E1/E3、E5 的逐带定位。**E4 图标和 E3 布局残差未闭环，不能报告五项全部修复。** 裸 alt 修复已在本轮起点 ab66967 中，由另一执行提交，本轮未重复修改。

最终完整回归：**1352 passed, 5 skipped in 190.08s (0:03:10)，rc=0**；0 failed。原始日志 [final-full.log](residual-20261123/modal/final-full.log)，退出码 [final-full.rc](residual-20261123/modal/final-full.rc)。

## 起点和边界

开工只读原始输出，三个命令 rc 均0：

```text
git rev-parse HEAD
ab66967621de70b683ef5afd807d4117f6b1852a
git ls-remote origin refs/heads/develop
ab66967621de70b683ef5afd807d4117f6b1852a	refs/heads/develop
git status --porcelain --untracked-files=no
```

最后一条无输出，document.py 对 HEAD 也无差异。这个起点在上一轮12个提交之后已有 ab66967，不能将 c660bf8 继续写成本轮起点。`document.py` 本轮始终未改；未改全局配置、未重做用户列出的提交、未 reset/rebase/force-push/amend，所有提交均在 develop，没有新建分支。deva 目录只读取源码。

运行应用和测试均显式设置 `/tmp/ai-upper-residual-*` 下的 AI_UPPER_HOME；临时脚本/工作日志在 `.tmp/residual-20261123/`，正式证据在 `out/residual-20261123/`。原来的未跟踪产物未删除或批量纳入提交。

## 五项结论、前后数字与提交

| 项 | 本轮结果 | 改前 → 改后 | 独立提交 |
|---|---|---|---|
| [1 E4](residual-20261123/E4.md) | 起点已有裸alt修复验收；断图图标仍缺 | 本轮 chat **112725→112725 px，10.739806%→10.739806%**；起点前旧包装113088px，减少363px属于ab66967 | `ae5eed6` |
| [2 E1/E3](residual-20261123/E1-E3.md) | 逐带映射排除分段丢行；定位行推进/表格/列表/引用布局，未修复布局 | 原始 **18→18 带**（deva19）；首带 `[40,43]` 对 `[43,45]`；非均匀偏移仍为−28..−1px；chat百分比不变 | `1a8ac73` |
| [3 E5](residual-20261123/E5.md) | 复现下部15/16带并定位额外断图图标；无搜索专属丢行 | **15→15 对16**（y200..699）；全正文18对19；search-none **84812→84812 px，8.080412%→8.080412%** | `8fa0fe5` + `8065d86` |
| [4 long-mid](residual-20261123/LONG-MID.md) | 悬停缺口已修复，绑定随contentY更新 | **0→54行，(668,721)**；**142100→130345 px，13.538491%→12.418540%** | `c1fdbf1` |
| [5 设置/删除确认](residual-20261123/MODALS.md) | 修复About标题、General选中阴影、3页标题2px leading；其他残差逐项分类 | 详见下表；遮罩未改 | `8c880e6` |

E5 初始文档对旧区域说明不准确，另用独立追加提交补齐 y[200,700) 坐标表，没有 amend 已推送历史。该区域末两带来自输入框提示，不全是正文；缺少的额外带位于 deva y602（断图图标），alt文字为y606–619。逐带坐标详见链接文档和 [E1/E3 坐标表](residual-20261123/e13/bands.md)。

## 弹窗内部实测

| 页 | 全页差异 px 前→后 | 百分比前→后 | 内部 >8 px 前→后 | 判定 |
|---|---:|---:|---:|---|
| settings-general | 315274→311758 | 30.037538%→29.702553% | 5732→3122 | 缺选中阴影和标题基线2px，已修；余下字形/圆角差仍在 |
| settings-extensions | 305797→305414 | 29.134623%→29.098133% | 4777→4250 | 标题2px已修；行/徽标字体尺寸量化与字形仍有差 |
| settings-about | 302389→302188 | 28.809928%→28.790777% | 2114→1773 | 缺失About标题已补；品牌SVG等光栅残差仍在 |
| settings-models | 300497→300497 | 28.629668%→28.629668% | 1596→1596 | 未见缺控件；名称/count文字度量及边缘差，未强行调色 |
| delete-confirm | 382289→382289 | 36.422351%→36.422351% | 6645→6645 | 未见缺按钮/文案；文字光栅及1–2px定位差，不能算遮罩取整 |

四页设置 outside_diff 均保持 **297039**、outside_le2 均保持 **248842**。总差异减少来自内部修改，没有修改 rgba(0,0,0,0.42)。delete-confirm 本轮起点全页382289与用户引用旧382652相差363px，来自此前ab66967裸alt修复，不归到本轮设置修改。

归因使用每个>8像素的双向1/2px邻域匹配、局部平坦性、40px网格定位与文字bbox。邻域匹配不从原始差异中扣除，也不能独自证明纯光栅舍入。原始数值在 [modal/summary.log](residual-20261123/modal/summary.log)、[最终前后数值](residual-20261123/modal/final-summary.log) 和每页JSON；三页标题最终bbox逐坐标一致，见 [title-final-bbox.log](residual-20261123/modal/title-final-bbox.log)。

## 修改文件

产品源码仅两份：
- `app/src/qml/Main.qml`：long-mid 强制悬停从固定11改为随contentY计算当前可见行；不改滚动距离。
- `app/src/qml/SettingsModal.qml`：About标题、选中项复用SoftShadow、三页标题leading。

测试仅新增：
- `app/tests/test_qml_sidebar.py`：30行，真实滚动后检查悬停及回到chat。
- `app/tests/test_qml_settings_overlay.py`：17行，断言右侧About标题实际存在。

相对起点测试删除行数0。源码/测试 `git diff --check` rc0。保留的原始 `modal/change.patch` 内有diff上下文空白行，针对整个证据目录运行 `git diff --check` 会提示4处尾随空格；这是原始补丁内容，不是产品源码空白错误，未修改原始证据来掩盖。

## 测试原始结果

| 验证 | 原始结果 | 进程rc |
|---|---|---:|
| 正文Body/Document | 82 passed in 0.45s；0 skipped | 0 |
| 新long-mid测试修复前 | 1 failed in 5.20s | 1 |
| sidebar模块修复后 | 2 passed in 9.96s；0 skipped | 0 |
| shell模块 | 49 passed in 15.28s；0 skipped | 0 |
| long-mid后的完整套件 | 1351 passed, 5 skipped in 174.06s | 0 |
| About标题新测试修复前 | 1 failed in 5.15s | 1 |
| 设置/服务商/右键组合（含阴影） | 56 passed in 68.96s；0 skipped | 0 |
| 最终标题overlay模块 | 3 passed in 14.37s；0 skipped | 0 |
| **最终完整套件** | **1352 passed, 5 skipped in 190.08s** | **0** |

**非零退出也保留**：sidebar+scrollbar+shell组合两次分别53 passed后rc139；scrollbar单跑2 passed后rc139。将未修改的改前Main.qml复制到临时资源目录、运行同一未改scrollbar测试，也2 passed后rc139。因此特定退出路径的Qt生命周期问题在hover修复前可复现，但底层原因未修。不能把这些运行写成rc0。最终完整套件正常退出。所有原始日志和rc均保留在 long-mid/。

最终测试命令在之前已有的隔离检出执行，临时检出未提交、未新建分支。主工作树 `.tmp/` 已含旧名兼容夹具，会污染递归改名测试，因此把当前7份变化的产品/测试文件逐字同步到已有隔离检出；[SHA-256清单](residual-20261123/modal/final-regression-manifest.log) 与最终工作树一致。

```bash
# cwd: /home/agent/shared_workspace/ai_upper/.tmp/retest-20261123/baseline-checkout
AI_UPPER_HOME=/tmp/ai-upper-residual-final-full /home/agent/shared_workspace/ai_upper/.venv/bin/python -m pytest app/tests -q -ra > /home/agent/shared_workspace/ai_upper/out/residual-20261123/modal/final-full.log 2>&1
retest_rc=$?
echo rc=$retest_rc
# rc=0
# 1352 passed, 5 skipped in 190.08s (0:03:10)
```

5个skip：Windows专属2项、需AI_UPPER_E2E=1的构建2项、需cc/patchelf/readelf的native1项。没有删除、过滤、放宽测试。

## 未闭环及具体限制

- **E4图标未实现**：裸alt已验收；直接QTextImage插入会产生U+FFFC，实际最小实验 `existing_bare_alt_contract=False`，见 [image-object-contract.log](residual-20261123/e4/image-object-contract.log)。现有测试要求裸纯文本，保持此契约还需独立绘制标记；本轮未完成，不能用已修文案代替图标验收。
- **E3布局未修复**：行推进及表格/列表容器段后距路径已具体定位，仍需逐块实现和验证；没有通过全局contentY补偿掩盖非均匀差。
- **E5共享残差**：没有额外搜索丢行；图标和间距仍随E4/E3开放。
- **long-mid其他状态差**：本项0/54悬停缺口关闭；活动会话与参考不同、首完整行身份026/027不同仍未改，整页不算像素闭环。
- **模态其余残差**：Models/delete-confirm内部未得到每个像素的唯一归因；没有发现缺控件但仍有文字/小几何残差。General/Extensions/About修复后也未清零。
- **测试退出问题**：部分QML模块组合退出139在改前资源也可复现，未修；最终全量rc0不代表消除此问题。

本轮无权限/网络推送阻塞。上述未完成项属于实现尚未闭环，已与完成的定位和修复分开，任务不能标记“全部修复”。

## 每项push与远端原始行

每个commit完成后立即单独 `git push origin HEAD:develop`；全部push rc0。每次紧接 `git ls-remote origin refs/heads/develop`，原始行如下（不是将最终HEAD重复填给每项）：

```text
ae5eed62ed7e99c7b9321b2e8ee0ad353393ad59	refs/heads/develop
1a8ac73936a2446168fd1a886a7657461f1b4214	refs/heads/develop
8fa0fe509aa4730a40a9e360822f2e9e69322a15	refs/heads/develop
8065d86420f276d056a02bd74cff24089af7499a	refs/heads/develop
c1fdbf1c3e407c5fc42ce3871ecbb50140129f1a	refs/heads/develop
8c880e61f3cfae2638b45ed742101d6ec0a35130	refs/heads/develop
```

顺序依次为E4、E1/E3、E5、E5坐标补充、long-mid、模态。原始push/ls-remote日志在 [receipts](residual-20261123/commits.json) 对应映射目录。总报告随后独立提交推送；最终HEAD和远端原始行由本地交付文件 `out/residual-20261123/publish-final.txt` 记录，不把该回执纳入它自身证明的commit，避免自引用hash。
