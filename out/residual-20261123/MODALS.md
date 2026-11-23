# 设置与删除确认：只处理弹窗内部，不改遮罩

## 前后实测

| 页面 | 全页差异 px | 全页百分比 | 内部最大通道差 >8 的像素数 |
|---|---:|---:|---:|
| settings-general | 315274 → 311758 | 30.037538% → 29.702553% | 5732 → 3122 |
| settings-models | 300497 → 300497 | 28.629668% → 28.629668% | 1596 → 1596 |
| settings-extensions | 305797 → 305414 | 29.134623% → 29.098133% | 4777 → 4250 |
| settings-about | 302389 → 302188 | 28.809928% → 28.790777% | 2114 → 1773 |
| delete-confirm | 382289 → 382289 | 36.422351% → 36.422351% | 6645 → 6645 |

设置四页 outside_diff 均保持 **297039**，outside_le2 均保持 **248842**。delete-confirm 当前 outside=374809/≤2=301190，和该页本轮改前完全相同。删除确认旧382652→当前382289的363px变化来自起点 ab66967 的裸alt修复，本项未修改删除确认。全部测量边界和阈值见 measure_page.py，右下坐标为不含边界。

## 逐页归因

1. **General：确认结构/效果缺口，已部分修复。** deva `.cf-seg__opt.is-on` 明确使用 `box-shadow:var(--shadow)`，tokens.css 的浅色值是0/6/24/0.12；QML旧实现只有白色 Rectangle，没有该阴影。内部5732个>8像素中1423个在两边都是局部平坦区域，不是文字抗锯齿。复用现有 SoftShadow 后5732→3501；再纠正标题2px行盒偏移后→3122。剩余包含选项文字、圆角和边缘光栅差，未宣称清零。
2. **About：确认缺少结构，已修复标题。** deva SettingsPane.tsx:859 有 `<h2 className="cf-pane__title">`，QML AboutPane 只从居中品牌Column开始。新增标题并校准2px leading；暗像素 bbox QML/deva均为 `(469,204,518,215)`，340/334个暗像素体现剩余光栅差。内部2114→1773；品牌SVG像素、导航文字等仍有残差。
3. **Extensions：标题基线2px几何差已修复，行文字/徽标量化仍在。** 标题 bbox 从 `(470,202,559,213)` 到 `(470,204,559,215)`，后者与deva一致，内部4777→4250。三行名称/徽标的暗像素左右边界仍差1–2px，当前代码将deva 10.5px badge字号取整到11px，这是明确字体尺寸量化，不能称为背景遮罩取整。未缺少三个扩展行或开关。
4. **Models：没有发现缺失控件，残差属于文字/图标边缘及字体度量，保留开放。** Providers标题 bbox 两端完全相同 `(470,207,548,218)`；provider名称及count字符的y/末端仍有1–2px级差异。内部1596个>8像素中，825个在双向2px邻域能找到≤8颜色差的对应像素；两边都平坦的>8像素为0。证据支持字形/小位移成分，不能证明剩余771全部是无害舍入。没有重做已完成的Models布局提交，也未改视觉token。
5. **delete-confirm：没有发现缺失文案/按钮，主要为文字光栅及小几何偏移，不能归为1级遮罩取整。** 标题bbox QML `(450,341,798,377)` vs deva `(451,340,800,377)`；说明 `(450,399,753,432)` vs `(451,399,755,432)`；Cancel `(697,462,738,471)` vs `(696,462,737,471)`。6645个>8内部差异中3412个能在双向2px邻域找到≤8的匹配，平坦对平坦差为0。对剩余3233个像素尚未得到逐字形唯一归因，因此不标记像素闭环。

**邻域检验仅用于归因**，从未把可匹配像素从原始总数中扣除，也不把“附近有同色”当作证明纯取整。分布和40px格网定位在每页 `*-metrics.json`；区域文字bbox在 regions.json；标题最终bbox在 title-final-bbox.log。General和About的缺项由源码、截图、变更前后数值三方确认。

## 实施与验证

修改 `app/src/qml/SettingsModal.qml`：选中segment复用SoftShadow、补About标题、General/Extensions/About标题补2px leading。遮罩、modal位置/尺寸、Models和delete-confirm均不变。

新增 `test_about_pane_includes_its_content_heading`，缺标题时 **1 failed in 5.15s, rc=1**；新增后设置/服务商/右键组合 **56 passed in 64.02s, rc=0**；加入选中阴影后同组合 **56 passed in 68.96s, rc=0**；最终三个标题基线微调后overlay模块 **3 passed in 14.37s, rc=0**。全部0 skipped。旧测试无删除无放宽。

```bash
AI_UPPER_HOME=/tmp/ai-upper-residual-modal-final .venv/bin/python -m pytest app/tests/test_qml_settings_overlay.py app/tests/test_qml_settings_models.py app/tests/test_qml_settings_provider.py app/tests/test_qml_context_menu.py -q > out/residual-20261123/modal/tests-final.log 2>&1
echo rc=$?
AI_UPPER_HOME=/tmp/ai-upper-residual-title-tests .venv/bin/python -m pytest app/tests/test_qml_settings_overlay.py -q > out/residual-20261123/modal/title-tests.log 2>&1
echo rc=$?
# 各页真实截图命令，page取具体页名；AI_UPPER_HOME始终在/tmp
AI_UPPER_HOME=/tmp/ai-upper-residual-20261123 bash scripts/parity/qml_page_shot.sh "$page" "out/residual-20261123/modal/$page-final.png" /tmp/ai-upper-residual-20261123 > ".tmp/residual-20261123/$page-shot.log" 2>&1
echo rc=$?
python3 out/residual-20261123/modal_probe.py settings-general > .tmp/residual-20261123/general-probe.json 2> .tmp/residual-20261123/general-probe.err
echo rc=$?
```

前5页/修改后3页截图均rc0。首次将5页合并运行modal_probe的进程收到SIGTERM（工具返回143，stderr为空，原因未确定）；改为每页独立命令后5/5 rc0，输出落盘，未拿空文件充当测量。

最终完整回归：**1352 passed, 5 skipped in 190.08s (0:03:10)，rc=0**，日志 modal/final-full.log 和 final-full.rc。全部当前源码/测试字节经 final-regression-manifest.log 校验。相对上一项1351新增的1条即About标题测试，旧测试未删除。
