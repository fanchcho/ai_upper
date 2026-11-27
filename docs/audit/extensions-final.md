# 2026-11-27剩余差异与推送记录

## 对账

起始HEAD 99387aa826efd213fa52ac7fb19fb09120b74ea3；status --porcelain --untracked-files=no空。log -5：99387aa/4cb9887/68bb695/9ccd66f/1da3287。ls-remote：897702dd79ae82094ed62686999141543931b843 refs/heads/develop。fetch后ancestor验证成功，可正常快进推送。已闭环内容沿用此前报告，不回退、不重跑A/B。

## 动手前清单

- 可修：菜单is-open缺3px accent-tint外环，依据app.css:5988，tokens.css:59 light .1 /:127 dark .16；现在缺失。
- 可修：首行active背景缺失，Select.tsx:128打开时选中项为active、:298鼠标移动更新active；app.css:6150用bg-hover。
- 可修：所有角色缺check，角色用文本✓；Select/app.css:6185要求选中项显示Lucide Check。
- 待分析：dark圆底1蓝通道差，原版#3b3b55，Qt#3b3b54；相同RGBA20%和相同底色，属于合成取整候选，不能叫字体抗锯齿。
- 待分析：浅色阴影尾1灰阶差，原版#fcfcfc/Qt#fbfbfb；24px blur、12%黑及6px offset均一致，不改token凑像素。
- 未证明不可修：正文0/+1px，现有QTextDocument→HTML→QQuickTextEdit路径布局与字形影响未隔离。保留既有数值，不称不可修、不改字号或块。
- 环境未验证：原版密钥safeStorage不可用。需补无凭据时的错误UI验证，不伪造Saved。

## 实施

ExtensionDetail.qml仅角色控件：is-open主题外环/边框、展开箭头翻转、activeRow开时选中项初始化及鼠标移动、高亮背景、所有角色与指定角色统一Lucide check。不改SettingsModal、路由、既有测试。

首次截图因/tmp旧fixture已存在而失败，FileExistsError；换独立日期home，不删用户目录。

## 后续独立修复

密钥失败：ExtensionSettings.secret原本忽略available只报通用错误。现在available=false使用原版已有extensions.secretUnavailable文案；backend=none故障注入通过真实QML密码输入、600ms autosave，实际返回ok=false并显示错误，无Saved。此为失败路径测试，不是原版保存成功验证。证据dark/light-final.log与secret-unavailable截图。

圆底：相同CSS alpha合成结果应为round(42*.8+124*.2)=58、实际底色由Theme.bgElevated确定。本轮按实际RGB公式统一round后生成不透明圆底，保留原alpha和底色token，不改透明度来凑数；验证截图中的实际值后再作结论。

正文：没有找到足以证明所有1px为纯抗锯齿的依据；仍记未闭环，不贴“不可修”标签。浅色阴影尾部1灰阶：模糊token相同但缺核函数级对账，仍是未消除残差，不宣称不可修。原版已保存密钥态：环境未验证，与移植版backend=none故障注入严格区分。

## 合成实验结论

独立试验round(sum)得到#3a3a54，分别量化source/destination得到#3b3b54，仍未匹配原版#3b3b55。不能凭猜测修改主题颜色；实验实现已撤销，保持原CSS token。此项仍未闭环而非“不可修”。最终生产改动不含合成补丁，不以局部取色技巧冒充修复。

## 最终实测与未闭环边界

实际打开菜单，同fixture原版截图沿用out/extensions-finish/deva-{dark,light}-all-roles-popup.png。改前/改后并排图out/extensions-final/compare-{dark,light}-menu-{before,after}.png。pixels.json给完整采样，测量脚本scripts/parity/measure_extensions_final.py。

|位置|原版暗/浅|改前暗/浅|改后暗/浅|
|---|---|---|---|
|外环(700,325)|#333349 / #e7e7f5|#252528 / #f7f7f8|#333348 / #e7e7f4|
|边框(700,328)|#7c7cf0 / #5b5bd6|#3d3d42 / #d5d5db|#7c7cf0 / #5b5bd6|
|活动行(700,380)|#37373a / #f4f4f4|#2a2a2e / #ffffff|#37373a / #f4f4f4|
|圆底(480,343)|#3b3b55 / #ebebfa|#3b3b54 / #ebebfa|未改变|
|阴影尾(700,660)|#252529 / #fcfcfc|#252529 / #fbfbfb|未改变|

check墨迹：原版bbox[951,392,961,399]，改前缺失，改后[952,393,961,400]；暗浅相同。14px Lucide Check结构已补齐，但墨迹仍1px残差，不称像素归零。新发现外环合成也有1蓝通道差；与圆底一样保留为未闭环。

暗浅backend=none均实际输出：UNAVAILABLE backend none visible error ['Secure encryption is unavailable on this system; secrets cannot be saved.']。脚本通过真实键盘输入与600ms自动保存触发，断言没有Saved；截图dark/light-secret-unavailable.png。这是故障注入，非原版OS安全存储恢复；原版成功保存态仍未验证。页面没有空白、崩溃；提示语义与原版明确不可保存一致，错误框颜色/几何没有同状态原版新截图，仍未验证。

全量运行必须以pytest-publish.log最终结尾为准。命令：
```sh
AI_UPPER_HOME=/tmp/ai-upper-final-tests \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-final-tests/publish
```
旧测试及SettingsModal/Main路由无改动，依赖pin无改动。不得把本次菜单行为修复称为整体1:1完成。已授权本次正常推送origin develop，不force、不建tag。

最终全量：1429 passed, 9 skipped in 408.04s (0:06:48)，0 failed。测试未修改，git diff --check通过。针对中间版本的并行旧进程已停止，仅以上publish完整结果作为交付依据。
