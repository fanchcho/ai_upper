# @ 候选补齐

原版 Composer.tsx:399-419 在光标处识别 / 与 @，前缀优先、子串次之；:440-450 采纳只替换当前 token 并保留后文。新 mentionCandidates 从当前会话真实 members 与角色清单取候选，同名去重。QML 共用候选浮层，支持光标中段触发、上下选择、Tab/Enter、Esc；选中 @ 只写回输入，不触发发送。中文输入法 composing 时不截获 Enter。

`AI_UPPER_HOME=/tmp/ai-upper-mentions-ui QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/final_port/mentions_ui.py`

结果：`PASS real keyboard trigger/filter/Tab insertion; suffix preserved; no message sent`。真实 QTest 键盘输入 `Ask @Rev after`，移动光标、弹候选、Tab 选中后得到 `Ask @Reviewer after`，消息数仍为零。暗亮截图 out/final-port/mentions-dark.png / mentions-light.png，完整候选/结果 out/final-port/mentions-ui.json。

范围限制：成员/角色联想和文本插入已实现；原版自动创建成员及 @ 后台分派调用尚未移植，不能把 F14 的整个提及执行语义算成完成。未添加“新建成员”的空转候选。

截图独立复核发现旧 SlashMenu 作为 SoftShadow 子项时重复应用了 composer 坐标，导致菜单落到窗口外；visible 属性虽然为真，却不能证明可见。现把菜单与输入框放在同一父级坐标系，没有新增坐标补偿。mentions_ui 增加屏内几何断言，并真实鼠标点击候选后读回文本；暗亮截图已经重拍，能直接看到 @Reviewer 候选。
