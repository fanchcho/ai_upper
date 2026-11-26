# 设置组件审计

以下行号指修复前快照（同原始源文件行号）。透明色是有意透出父背景。所有设置页共用 SettingsModal 背景/侧栏/遮罩；正文 QTextDocument 不在本次改动范围。

## SettingsModal

```text
app/src/qml/SettingsModal.qml:32: color: Theme.backdrop
app/src/qml/SettingsModal.qml:49: color: Theme.bgPanel
app/src/qml/SettingsModal.qml:51: border.color: Theme.border
app/src/qml/SettingsModal.qml:64: color: Theme.border
app/src/qml/SettingsModal.qml:70: color: Theme.fg
app/src/qml/SettingsModal.qml:83: color: closeHover.hovered ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:88: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:111: color: Theme.bgInset
app/src/qml/SettingsModal.qml:116: color: Theme.border
app/src/qml/SettingsModal.qml:142: color: modelData.key === root.pane ? Theme.bgActive
app/src/qml/SettingsModal.qml:154: color: modelData.key === root.pane ? Theme.fg : Theme.fgSubtle
app/src/qml/SettingsModal.qml:159: color: modelData.key === root.pane ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:216: color: Theme.border
app/src/qml/SettingsModal.qml:222: color: Theme.fg
app/src/qml/SettingsModal.qml:236: color: Theme.bgInset
app/src/qml/SettingsModal.qml:238: border.color: Theme.border
app/src/qml/SettingsModal.qml:252: color: index === row.current ? Theme.bg : "transparent"
app/src/qml/SettingsModal.qml:265: color: index === row.current ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:290: color: "transparent"
app/src/qml/SettingsModal.qml:292: border.color: Theme.border
app/src/qml/SettingsModal.qml:298: color: Theme.fg
app/src/qml/SettingsModal.qml:495: color: Theme.fg
app/src/qml/SettingsModal.qml:508: color: addHover.hovered ? Theme.bgHover : Theme.bgElevated
app/src/qml/SettingsModal.qml:510: border.color: Theme.border
app/src/qml/SettingsModal.qml:515: color: addHover.hovered ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:532: Button {
app/src/qml/SettingsModal.qml:553: color: "transparent"
app/src/qml/SettingsModal.qml:555: border.color: Theme.border
app/src/qml/SettingsModal.qml:566: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:587: color: providerMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:595: color: Theme.border
app/src/qml/SettingsModal.qml:605: color: providerRow.modelData.enabled === true ? Theme.success : Theme.fgSubtle
app/src/qml/SettingsModal.qml:620: color: Theme.fg
app/src/qml/SettingsModal.qml:629: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:655: color: Theme.warning
app/src/qml/SettingsModal.qml:660: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:699: color: detailBackMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:709: color: detailBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:713: color: detailBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:742: color: deleteMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:747: color: deleteMouse.containsMouse ? Theme.danger : Theme.fgSubtle
app/src/qml/SettingsModal.qml:765: color: wrenchMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:770: color: wrenchMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:785: color: Theme.fgMuted
app/src/qml/SettingsModal.qml:799: color: modPane.detail.enabled === true ? Theme.accent : Theme.bgActive
app/src/qml/SettingsModal.qml:807: color: "#ffffff"
app/src/qml/SettingsModal.qml:834: color: Theme.fg
app/src/qml/SettingsModal.qml:844: color: Theme.border
app/src/qml/SettingsModal.qml:855: color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.08)
app/src/qml/SettingsModal.qml:857: border.color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.4)
app/src/qml/SettingsModal.qml:867: color: Theme.warning
app/src/qml/SettingsModal.qml:871: color: Theme.warning
app/src/qml/SettingsModal.qml:888: color: Theme.fg
app/src/qml/SettingsModal.qml:904: color: "transparent"
app/src/qml/SettingsModal.qml:906: border.color: Theme.border
app/src/qml/SettingsModal.qml:916: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:933: color: "transparent"
app/src/qml/SettingsModal.qml:940: color: Theme.border
app/src/qml/SettingsModal.qml:949: color: Theme.fg
app/src/qml/SettingsModal.qml:957: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:992: color: advancedBackMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:1002: color: advancedBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:1006: color: advancedBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:1036: color: Theme.fg
app/src/qml/SettingsModal.qml:1049: color: addHeaderMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:1058: color: addHeaderMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:1062: color: addHeaderMouse.containsMouse ? Theme.fg : Theme.fgMuted
app/src/qml/SettingsModal.qml:1093: color: "transparent"
app/src/qml/SettingsModal.qml:1095: border.color: Theme.border
app/src/qml/SettingsModal.qml:1105: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1129: color: Theme.border
app/src/qml/SettingsModal.qml:1139: color: Theme.bgElevated
app/src/qml/SettingsModal.qml:1141: border.color: headerNameInput.activeFocus ? Theme.accent : Theme.borderStrong
app/src/qml/SettingsModal.qml:1148: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1160: color: Theme.fg
app/src/qml/SettingsModal.qml:1176: color: Theme.bgElevated
app/src/qml/SettingsModal.qml:1178: border.color: headerValueInput.activeFocus ? Theme.accent : Theme.borderStrong
app/src/qml/SettingsModal.qml:1185: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1197: color: Theme.fg
app/src/qml/SettingsModal.qml:1214: color: headerDeleteMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:1220: color: headerDeleteMouse.containsMouse ? Theme.fg : Theme.fgSubtle
app/src/qml/SettingsModal.qml:1237: color: Theme.warning
app/src/qml/SettingsModal.qml:1251: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1284: color: Theme.fg
app/src/qml/SettingsModal.qml:1298: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1311: color: "transparent"
app/src/qml/SettingsModal.qml:1313: border.color: Theme.border
app/src/qml/SettingsModal.qml:1341: color: Theme.border
app/src/qml/SettingsModal.qml:1352: color: Theme.fg
app/src/qml/SettingsModal.qml:1363: color: Theme.bgInset
app/src/qml/SettingsModal.qml:1365: border.color: Theme.border
app/src/qml/SettingsModal.qml:1370: color: Theme.fgMuted
app/src/qml/SettingsModal.qml:1381: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1400: opacity: extRow.modelData.builtin ? 0.55 : 1.0
app/src/qml/SettingsModal.qml:1406: color: extRow.modelData.enabled ? Theme.accent : Theme.bgActive
app/src/qml/SettingsModal.qml:1414: color: "#ffffff"
app/src/qml/SettingsModal.qml:1477: color: Theme.fg
app/src/qml/SettingsModal.qml:1501: color: Theme.fg
app/src/qml/SettingsModal.qml:1511: color: Theme.fgSubtle
app/src/qml/SettingsModal.qml:1529: color: updateMouse.containsMouse && !aboutPaneRoot.checking
app/src/qml/SettingsModal.qml:1532: border.color: Theme.borderStrong
app/src/qml/SettingsModal.qml:1533: opacity: aboutPaneRoot.checking ? 0.45 : 1
app/src/qml/SettingsModal.qml:1543: color: Theme.fg
app/src/qml/SettingsModal.qml:1550: color: Theme.fg
app/src/qml/SettingsModal.qml:1565: color: Theme.fg
app/src/qml/SettingsModal.qml:1589: color: Theme.success
app/src/qml/SettingsModal.qml:1594: color: Theme.success
app/src/qml/SettingsModal.qml:1607: color: Theme.danger
app/src/qml/SettingsModal.qml:1612: color: Theme.danger
app/src/qml/SettingsModal.qml:1633: color: Theme.backdrop
app/src/qml/SettingsModal.qml:1647: color: Theme.bgElevated
app/src/qml/SettingsModal.qml:1649: border.color: Theme.border
app/src/qml/SettingsModal.qml:1660: color: Theme.fg
app/src/qml/SettingsModal.qml:1673: color: Theme.fgMuted
app/src/qml/SettingsModal.qml:1686: color: providerCancelMouse.containsMouse ? Theme.bgHover : "transparent"
app/src/qml/SettingsModal.qml:1690: color: Theme.fg
app/src/qml/SettingsModal.qml:1712: color: providerConfirmMouse.containsMouse ? Qt.lighter(Theme.danger, 1.07) : Theme.danger
app/src/qml/SettingsModal.qml:1716: color: "#ffffff"
```

## PluginSettingsPane

```text
app/src/qml/PluginSettingsPane.qml:32: Text { text: pane.mode === "custom-model" ? "Custom model" : pane.mode === "mcp" ? "MCP servers" : "Personas"; color: Theme.fg; font.pixelSize: 18 }
app/src/qml/PluginSettingsPane.qml:33: Text { visible: pane.mode === "custom-model"; text: "Empty address follows the current session model."; color: Theme.fgMuted }
app/src/qml/PluginSettingsPane.qml:34: ComboBox {
app/src/qml/PluginSettingsPane.qml:51: TextField { id: identifier; objectName: "pluginIdentifier"; visible: pane.mode !== "custom-model"; placeholderText: "ID (new ID creates an entry)"; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:52: TextField { id: address; objectName: "pluginBaseUrl"; visible: pane.mode !== "identities"; placeholderText: "Base URL"; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:53: TextField { id: modelName; objectName: "pluginModelName"; visible: pane.mode === "custom-model"; placeholderText: "Model name"; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:54: TextField { id: command; visible: pane.mode === "mcp"; placeholderText: "Command (stdio)"; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:55: TextField { id: argsInput; visible: pane.mode === "mcp"; text: "[]"; placeholderText: "Arguments (JSON array)"; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:56: CheckBox { id: enabledBox; objectName: "pluginEnabled"; visible: pane.mode === "mcp"; text: "Enabled"; checked: true }
app/src/qml/PluginSettingsPane.qml:57: CheckBox { objectName: "pluginApprovalEnabled"; visible: pane.mode === "mcp"; text: "执行命令、写文件和 MCP 调用前审批"; checked: pane.state.approvalEnabled === true; onClicked: pane.invoke("saveApproval", {enabled: checked}) }
app/src/qml/PluginSettingsPane.qml:58: Text { id: keyStatus; visible: pane.mode !== "identities"; text: (pane.mode === "mcp" ? pane.state.servers.some(function(row) { return row.id === identifier.text && row.hasKey }) : pane.state.model.hasKey) ? "已设置" : "未设置"; color: Theme.fgMuted }
app/src/qml/PluginSettingsPane.qml:59: TextField { id: secret; objectName: "pluginSecret"; visible: pane.mode !== "identities"; placeholderText: "New API key / credential (empty keeps current)"; echoMode: TextInput.Password; Layout.fillWidth: true }
app/src/qml/PluginSettingsPane.qml:60: ScrollView { visible: pane.mode === "identities"; Layout.fillWidth: true; Layout.fillHeight: true; TextArea { id: body; objectName: "pluginPersonaBody"; wrapMode: TextEdit.Wrap; placeholderText: "Persona Markdown" } }
app/src/qml/PluginSettingsPane.qml:62: Button {
app/src/qml/PluginSettingsPane.qml:77: Button { visible: pane.mode === "mcp"; text: "Delete"; onClicked: pane.invoke("deleteServer", {id: identifier.text}) }
app/src/qml/PluginSettingsPane.qml:78: Button {
app/src/qml/PluginSettingsPane.qml:91: Text { text: pane.notice; color: Theme.fgMuted; wrapMode: Text.Wrap; Layout.fillWidth: true }
```

|页|背景/文字|输入|按钮/开关|分隔/空状态/滚动|
|---|---|---|---|---|
|General|bgPanel/fg/fgMuted|无|Theme 分段选项|border；无滚动|
|Models（含 provider/advanced）|bgPanel/fg；小字 fgSubtle 不达标|高级头输入已有 Theme；占位符 fgSubtle|自定义网络 Button 漏绑；开关白色硬编码；确认危险白字|border；空状态 fgSubtle；无滚动条|
|Extensions|bgPanel/fg；注释 fgSubtle|无|开关白色硬编码，内置禁用 opacity .55|border；空状态 fgSubtle；无滚动条|
|About|bgPanel/fg；版本 fgSubtle|无|检查更新 Theme；checking opacity .45；状态字 success/danger|无输入/分隔/滚动条|
|Custom model|标题 fg、说明 fgMuted|所有 TextField 漏绑|Save/Clear Button 漏绑|无分隔/滚动；状态 fgMuted|
|MCP|标题 fg、状态 fgMuted|ComboBox/TextField 漏绑|CheckBox/三个 Button 全漏绑|无分隔/滚动；空 ComboBox 无提示|
|Personas|标题 fg|ComboBox/TextField/TextArea 漏绑|Save Button 漏绑|ScrollView 滚动条为平台默认|

修复：新增设置专用 Basic 控件；原版 token 绑定背景、文字、边框、焦点、选区、按钮态、复选框、下拉弹层与滚动条。小字改 fgMuted；危险按钮用 danger 边框和 fg 正文。详见 git diff。
