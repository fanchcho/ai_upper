import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."

Item {
    id: pane
    property string mode: "custom-model"
    property var state: ({model: {}, servers: [], identities: []})
    property string notice: ""
    function invoke(op, payload) {
        var result = JSON.parse(shellBridge.pluginSettings(op, JSON.stringify(payload || {})))
        if (!result.ok) { notice = result.error; return false }
        state = result
        notice = "Saved"
        return true
    }
    function refresh() {
        invoke(mode === "identities" ? "identities" : "read", {})
        notice = ""
        if (mode === "custom-model") {
            address.text = state.model.baseUrl || ""
            modelName.text = state.model.model || ""
        }
    }
    Component.onCompleted: refresh()
    onModeChanged: refresh()
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 10
        Text { text: pane.mode === "custom-model" ? "Custom model" : pane.mode === "mcp" ? "MCP servers" : "Personas"; color: Theme.fg; font.pixelSize: 18 }
        Text { visible: pane.mode === "custom-model"; text: "Empty address follows the current session model."; color: Theme.fgMuted }
        ComboBox {
            id: chooser
            palette.text: Theme.fg
            palette.buttonText: Theme.fg
            palette.base: Theme.bg
            palette.button: Theme.bg
            palette.highlight: Theme.accent
            palette.highlightedText: Theme.accentFg
            contentItem: Text { text: chooser.displayText || "Select an entry"; color: Theme.fg; verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
            background: Rectangle { implicitHeight: 34; color: Theme.bgElevated; radius: Theme.radiusSm; border.color: Theme.borderStrong }

            visible: pane.mode !== "custom-model"
            Layout.fillWidth: true
            model: pane.mode === "mcp" ? pane.state.servers : pane.state.identities
            textRole: "id"
            indicator: Text { x: chooser.width - width - 10; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: Theme.fgMuted }
            delegate: ItemDelegate {
                width: chooser.width
                text: modelData.id
                contentItem: Text { text: modelData.id; color: Theme.fg; font.pixelSize: 13 }
                background: Rectangle { color: highlighted ? Theme.bgActive : Theme.bg }
                highlighted: chooser.highlightedIndex === index
            }
            popup: Popup {
                y: chooser.height
                width: chooser.width
                implicitHeight: Math.min(contentItem.implicitHeight + 8, 240)
                padding: 4
                background: Rectangle { color: Theme.bgElevated; border.color: Theme.borderStrong; radius: Theme.radiusSm }
                contentItem: ListView {
                    clip: true
                    implicitHeight: contentHeight
                    model: chooser.popup.visible ? chooser.delegateModel : null
                    currentIndex: chooser.highlightedIndex
                    ScrollBar.vertical: SettingsScrollBar {}
                }
            }
            onActivated: {
                var row = model[currentIndex]
                identifier.text = row.id
                if (pane.mode === "mcp") {
                    address.text = row.url || ""
                    command.text = row.command || ""
                    argsInput.text = JSON.stringify(row.args || [])
                    enabledBox.checked = row.enabled
                } else body.text = row.text
                secret.text = ""
            }
        }
        SettingsField { id: identifier; objectName: "pluginIdentifier"; visible: pane.mode !== "custom-model"; placeholderText: "ID (new ID creates an entry)"; Layout.fillWidth: true }
        SettingsField { id: address; objectName: "pluginBaseUrl"; visible: pane.mode !== "identities"; placeholderText: "Base URL"; Layout.fillWidth: true }
        SettingsField { id: modelName; objectName: "pluginModelName"; visible: pane.mode === "custom-model"; placeholderText: "Model name"; Layout.fillWidth: true }
        SettingsField { id: command; visible: pane.mode === "mcp"; placeholderText: "Command (stdio)"; Layout.fillWidth: true }
        SettingsField { id: argsInput; visible: pane.mode === "mcp"; text: "[]"; placeholderText: "Arguments (JSON array)"; Layout.fillWidth: true }
        SettingsCheck { id: enabledBox; objectName: "pluginEnabled"; visible: pane.mode === "mcp"; text: "Enabled"; checked: true }
        SettingsCheck { objectName: "pluginApprovalEnabled"; visible: pane.mode === "mcp"; text: "执行命令、写文件和 MCP 调用前审批"; checked: pane.state.approvalEnabled === true; onClicked: pane.invoke("saveApproval", {enabled: checked}) }
        Text { id: keyStatus; visible: pane.mode !== "identities"; text: (pane.mode === "mcp" ? pane.state.servers.some(function(row) { return row.id === identifier.text && row.hasKey }) : pane.state.model.hasKey) ? "已设置" : "未设置"; color: Theme.fgMuted }
        SettingsField { id: secret; objectName: "pluginSecret"; visible: pane.mode !== "identities"; placeholderText: "New API key / credential (empty keeps current)"; echoMode: TextInput.Password; Layout.fillWidth: true }
        ScrollView {
            visible: pane.mode === "identities"
            Layout.fillWidth: true
            Layout.fillHeight: true
            ScrollBar.vertical: SettingsScrollBar {}
            TextArea {
                id: body
                objectName: "pluginPersonaBody"
                color: Theme.fg
                placeholderTextColor: Theme.fgMuted
                selectionColor: Theme.accent
                selectedTextColor: Theme.accentFg
                wrapMode: TextEdit.Wrap
                placeholderText: "Persona Markdown"
                background: Rectangle { color: Theme.bgElevated; border.color: Theme.borderStrong; radius: Theme.radiusSm }
            }
        }
        RowLayout {
            SettingsButton {
                primary: true
                objectName: "pluginSave"
                text: "Save"
                onClicked: {
                    var value = {key: secret.text.length ? secret.text : undefined}
                    var op
                    if (pane.mode === "custom-model") { op = "saveModel"; value.baseUrl = address.text; value.model = modelName.text }
                    else if (pane.mode === "mcp") {
                        op = "saveServer"; value.id = identifier.text
                        try { value.config = {url: address.text, command: command.text, args: JSON.parse(argsInput.text), enabled: enabledBox.checked} }
                        catch (e) { pane.notice = "Invalid JSON arguments"; return }
                    } else { op = "saveIdentity"; value = {id: identifier.text, text: body.text} }
                    if (pane.invoke(op, value)) secret.text = ""
                }
            }
            SettingsButton { visible: pane.mode === "mcp"; destructive: true; text: "Delete"; onClicked: pane.invoke("deleteServer", {id: identifier.text}) }
            SettingsButton {
                visible: pane.mode !== "identities"
                text: "Clear credential"
                onClicked: {
                    if (pane.mode === "custom-model") pane.invoke("saveModel", {baseUrl: address.text, model: modelName.text, key: ""})
                    else {
                        try { pane.invoke("saveServer", {id: identifier.text, config: {url: address.text, command: command.text, args: JSON.parse(argsInput.text), enabled: enabledBox.checked}, key: ""}) }
                        catch(e) { pane.notice = "Invalid JSON arguments" }
                    }
                    secret.text = ""
                }
            }
        }
        Text { text: pane.notice; color: Theme.fgMuted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Item { Layout.fillHeight: true; visible: pane.mode !== "identities" }
    }
}
