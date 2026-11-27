# 第3项：实现残差与最终回归

源码复核：原版styles/tokens.css:47/115 bg-selected与Theme.qml:21/37逐值相同；:59/127 accent-tint对应ExtensionDetail.qml:121的.1/.16；:82/149 shadow与SoftShadow.qml:22–24的light blur24/y6/alpha.12、dark blur30/y8/alpha.5一致。Check在ExtensionDetail.qml:186/208均size15（原版Select.tsx:306），不回退已修项。生产ExtensionDetail/Theme/SoftShadow/正文文件与070eb0a零差异。

本轮该组未发现新的可证实token/尺寸差，不作无依据修改。沿用extensions-rounding.md和out/extensions-rounding原始实验：暗圆底#3b3b55/#3b3b54，外环dark #37374e/#37374d/light #eeeefb/#eeeefa，light阴影尾部#fcfcfc/#fbfbfb，正文六块+1/+1/0/+1/+1/0px；全部未归零。没有重新测量后假称已归零。新发现的设置路由绑定断开属于实现问题，已在第1项0263dbd修复并通过真实点击返回验证。

最终全量命令：
```
AI_UPPER_HOME=/tmp/ai-upper-shell-full LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest app/tests -q --basetemp=$PWD/.tmp/extensions-shell/full
```
输出1429 passed, 9 skipped in 365.26s (0:06:05)，0 failed，out/extensions-shell/pytest.log。原测试零修改；导航+插件页面focused 6 passed。git diff --check通过。

第1项真实磁盘复读：out/extensions-shell/disk-readback.json从两主题临时home的config.json pluginScopes和deva/personas/fixture-persona.md读取，模型fixture-model、MCP fixture、角色正文Persistent persona fixture均落盘。三个顶级导航撤下，但独立插件模型配置/注册approval/角色文本能力继续可达；其保留页面不声称与原版表单完全等价。

第2项真实OS成功，但原版Electron safeStorage仍没有接入本次私有D-Bus做同状态截图，原版成功态像素对照未验证。与上轮替身证据分开，真实日志out/extensions-os/session.log。每项分别提交并立即正常push，原始push-1.log/push-2.log/push-3.log保留。
