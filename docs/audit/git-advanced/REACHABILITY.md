# 旧表单不可达
基线dc5f42b。rg -n 'gitPanel|GitPanel' app/src --glob '*.qml' 仅返回Main.qml:1675/1676实例声明和GitPanel.qml:9 objectName。没有open调用、快捷键或菜单接线。Main.qml:1896仅调用gitMenu.open。GitPanel是默认visible=false的Popup，不设置visible=true；保留用于内部旧测试，不是用户路由。
旧常驻身份、remote/URL、diff、最近提交、全部丢弃在GitPanel内部；上游GitWidget.tsx:425–440默认主菜单没有这些块。条件身份恢复不是旧常驻表单，属于本地原版定制GitIdentityForm。
reach-dark/light.json读回legacy_visible=false；同名main/branches.png为真实键鼠路径截图。脚本advanced_interaction.py reach dark|light。没有把内部测试主动调用Popup.open当作用户入口。
