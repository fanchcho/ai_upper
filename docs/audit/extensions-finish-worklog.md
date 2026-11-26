# 扩展详情续作工作日志

## 断点1：磁盘与证据

HEAD为4cb98879c16a1cfc66f8e84813f8126f2f6f46e0；未回退。已完成证据沿用out/extensions-calibration及docs/audit/extensions-calibration.md：字段坐标0px、多工具行距0px、锁纵向0px；正文仍0/+1px，不称归零。
未提交改动仅Avatar.qml与ExtensionDetail.qml：销毁后动态角色磁盘fallback修正、所有角色20px圆底/12px图标、下拉复用SoftShadow主题阴影。尚待最新截图及测试，不能预先称通过。
SettingsModal.qml、直达路由、依赖pin、既有测试不动。deva源码只读；全部运行指定/tmp下AI_UPPER_HOME。

原版依据：styles/app.css:46滚动条8px/透明2px边框/实际滑块4px；:4601顶栏是普通flex、非sticky；:4624标题分隔线随内容滚动；:6093圆底20px，:6123菜单阴影/12px圆角；tokens.css:82浅色0 6px 24px黑12%，:149暗色0 8px 30px黑50%。

## 断点2：首次新截图

暗亮实际渲染完成，无旧SVG报错；两份final.log只有runtime/list/wheel输出。所有角色圆底已绘出，但首次对照暴露菜单y差−6.5px、缺角色描述导致高度不足，继续修。SoftShadow已绘出，但不能仅凭有阴影称像素完全一致。

## 断点3：失败与修复

菜单补齐原版6px弹出间距、角色描述和26px头像。首次误把11.5赋给Qt整型pixelSize，QML明确报Invalid property assignment: int expected；该轮49 failed/1380 passed/9 skipped，保留pytest-final.log。已改用8.625pt表达11.5px，继续真实渲染后再跑全量，未修改测试断言。

## 断点4：滚动条实差

实际颜色一致不代表位置一致：原版正文滑块x972..975，Qt x968..971，均4px宽。查到Basic ScrollBar默认padding与implicitWidth叠加；显式padding=0/implicitWidth=8后重测位置，不能把旧数据当归零。

## 断点5：阴影与颜色实测

原版/Qt菜单下方(700,646)/(700,650)/(700,660)：dark均#1e1e21/#202023/#252529；light前两点均#efefef/#f3f3f3，第三点原版#fcfcfc、Qt#fbfbfb，保留1灰阶残差。圆底(480,343)：light同#ebebfa；dark原版#3b3b55、Qt#3b3b54，1蓝通道残差。视觉参数20px圆底+12px图标已一致。

Scrollbar去默认padding后x970..973，仍比原版左2px；只调整正文附着条rightMargin=-2，不改正文宽度或容器。再次实际截图确认。

## 断点6：附着条坐标绑定

ScrollBar附着对象管理x坐标，anchors.rightMargin未生效；改显式x绑定instructionsScroll.width-width+2。先前JSON不能作为最终位置结论，最终记录另存。

本轮复现命令（dark/light与不同临时home分别执行）：
```sh
AI_UPPER_HOME=/tmp/ai-upper-finish-dark6 \
XDG_DATA_HOME=$PWD/.tmp/extensions-finish/data \
XDG_CACHE_HOME=$PWD/.tmp/extensions-finish/cache TMPDIR=$PWD/.tmp/extensions-finish \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python scripts/parity/extensions_finish_evidence.py dark
```
实际原版启动命令沿用extensions-calibration.md，隔离DEVA_HOME；本轮CDP调用脚本scripts/parity/extensions_finish_reference.py，结果out/extensions-finish/reference.log与deva-*.json。

## 断点7：最终像素与销毁

scrollbar-final.json确认暗亮两端正文滑块x972..975、4px可见宽；暗#4c4c50，浅#d1d1d1，位置/宽/颜色均一致。轨道8px透明；圆角配置为胶囊形，端点抗锯齿未声称逐像素相同。正文QTextDocument字形仍沿用0/+1px残差，没有改字号、正文块或清零旧结论。

Avatar空图源使用原有纯色+首字母占位；bridge失效立即返回空source，不发起新磁盘读取。dark/light-delivery6.log两轮完整close/deleteLater无Cannot open或QML error。与原out/extensions-calibration/dark-delivery.log的reviewer/writer*.svg错误形成修前后证据。

MCP外层滚动仍185px，标题工具条与分隔线一起向上185px。原版provider-detail由y200变15，Qt Back文本y207变22；两者相对位移一致，未改为sticky/固定。截图compare-*-mcp-scroll.png左原版右Qt；同服务三工具fixture。

所有角色触发圆底原版/Qt均20×20、内Users12×12，dropdown内26×26圆底/14px图标；菜单12px圆角，位置y365.5（原来y359）；补充角色desc后同fixture菜单高度275.75。主题阴影数值见断点5；1灰阶/1蓝通道残差没有归零。菜单打开态的焦点外环/首行hover与check显示仍不是完整1:1，未在本次限定的阴影修复中声称已修；整页整体对齐保持open。

原版已保存密钥态仍未验证：既有实际返回{ok:false,available:false}，D-Bus/OS凭据不可用；沿用原始日志，不伪造。

截图目录：/home/agent/shared_workspace/ai_upper/out/extensions-finish/，compare-{dark,light}-{all-roles,all-roles-popup,scrollbar,mcp-scroll}.png共8张，左原版右Qt。visual-pixels.json保存阴影和圆底像素；deva-*-all-roles-popup.json保存DOM矩形与CSS实值。capture实际fixture扫描、运行态已输出在日志，非静态前端列表。

已完成A/B读取、真实目录清单与截图：docs/audit/icon-dpi.md、extensions-parity.md、extensions-runtime-parity.md及对应out。按用户要求本轮不重跑这些已经验证的工作。4cb98879保持祖先，三个额外导航入口/SettingsModal/Main和既有测试零改动。

最终回归命令：
```sh
AI_UPPER_HOME=/tmp/ai-upper-finish-tests \
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
.venv/bin/python -m pytest app/tests -q \
--basetemp=/tmp/ai-upper-finish-tests/delivery
```
输出out/extensions-finish/pytest-delivery.log，结束前不写通过。

## 断点8：回归与提交

最终完整回归：1429 passed, 9 skipped in 365.69s (0:06:05)，0 failed。既有测试未改。git diff --check通过；git merge-base --is-ancestor 4cb98879 HEAD返回0。最新源码的专门teardown-final.log无旧SVG报错。源码与证据脚本提交在本地develop；不push、不新建分支、不改依赖pin。整体目标继续open，不能把限定修复与测试通过替代菜单打开态等剩余实差。
