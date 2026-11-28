# 主菜单与分支尺寸核对（非逐像素闭环）
原版固定上游013c5d7，路径相对apps/desktop/src/renderer/src；QML相对app/src/qml。没有改Theme token或坐标补偿。本轮主要改高级交互，以下量取不冒充重新实现已验收尺寸。

| 上游文件:行 | 上游规则 | QML文件:行 | 当前值 | 处置 |
|---|---|---|---|---|
| redesign.css:447 | min-width148 | GitMenu.qml:28 | 主148、分支300 | 主一致；分支固定宽容纳用户要求upstream数字，非原版自适应，未完成 |
| redesign.css:450 | padding5+border1 | GitMenu.qml:28/32 | padding6、border1 | 内容起点同为外框6px，不额外加坐标 |
| redesign.css:458 | padding7px 9px；font13；line-height继承 | GitMenu.qml:96/102 | 行33、字13；默认Qt行盒 | 上游app.css:23 body行高1.5，浏览器继承计算仍需实际DOM核验；不凭公式宣称33严格相等 |
| redesign.css:466 | gap space2=8 | GitMenu.qml:102/103 | icon x9宽14、文字left31 | 9+14+8=31 |
| GitWidget.tsx:364/432 | 图标14 | GitMenu.qml:103 | 14 | 保持 |
| redesign.css:452/469 | 外radius-lg12、项radius8 | GitMenu.qml:32/106；Theme.qml:88/89 | 12/8 | 保持 |
| redesign.css:492 | 线1、margin4px 6px | GitMenu.qml:96/97 | 总9、线1、x6 y4 | 保持 |
| redesign.css:497 | section padding6px 9px 3px、字11 | GitMenu.qml:96/98 | 高26、x9 y6、字11 | 原版文字行盒未做DOM量取，不能声称26已相等 |
| redesign.css:483 | max-height viewport-16、overflow auto | GitMenu.qml:29/84 | parent.height-16、Flickable | 既有40分支验证保留；本轮截图geometry再次读回 |
| redesign.css:456；tokens.css:82/149 | shadow浅0 6 24 /.12、暗0 8 30 /.5 | GitMenu.qml:31；SoftShadow.qml:24–26 | 相同参数，Qt Canvas | 参数一致，模糊引擎残差未归零 |
| redesign.css:504 | 筛选padding5/8、字号12、背景bg | GitMenu.qml:91 | SettingsField默认样式 | 尚非完全同形，未完成；未通过改公共组件波及其它页 |

reach-dark/light.json包含主/分支实际width/height/padding；截图1280×1060、DPR1、Linux软件渲染。不是macOS原版像素对照，无对应宿主。上轮固定点颜色采样保留docs/audit/git-upstream/branch-samples.json，本轮未改主菜单主题色。
