import QtQuick
import QtQuick.Controls
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
            visible: pane.mode !== "custom-model"
            Layout.fillWidth: true
            model: pane.mode === "mcp" ? pane.state.servers : pane.state.identities
            textRole: "id"
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
        TextField { id: identifier; objectName: "pluginIdentifier"; visible: pane.mode !== "custom-model"; placeholderText: "ID (new ID creates an entry)"; Layout.fillWidth: true }
        TextField { id: address; objectName: "pluginBaseUrl"; visible: pane.mode !== "identities"; placeholderText: "Base URL"; Layout.fillWidth: true }
        TextField { id: modelName; objectName: "pluginModelName"; visible: pane.mode === "custom-model"; placeholderText: "Model name"; Layout.fillWidth: true }
        TextField { id: command; visible: pane.mode === "mcp"; placeholderText: "Command (stdio)"; Layout.fillWidth: true }
        TextField { id: argsInput; visible: pane.mode === "mcp"; text: "[]"; placeholderText: "Arguments (JSON array)"; Layout.fillWidth: true }
        CheckBox { id: enabledBox; objectName: "pluginEnabled"; visible: pane.mode === "mcp"; text: "Enabled"; checked: true }
        CheckBox { objectName: "pluginApprovalEnabled"; visible: pane.mode === "mcp"; text: "执行命令、写文件和 MCP 调用前审批"; checked: pane.state.approvalEnabled === true; onClicked: pane.invoke("saveApproval", {enabled: checked}) }
        Text { id: keyStatus; visible: pane.mode !== "identities"; text: (pane.mode === "mcp" ? pane.state.servers.some(function(row) { return row.id === identifier.text && row.hasKey }) : pane.state.model.hasKey) ? "已设置" : "未设置"; color: Theme.fgMuted }
        TextField { id: secret; objectName: "pluginSecret"; visible: pane.mode !== "identities"; placeholderText: "New API key / credential (empty keeps current)"; echoMode: TextInput.Password; Layout.fillWidth: true }
        ScrollView { visible: pane.mode === "identities"; Layout.fillWidth: true; Layout.fillHeight: true; TextArea { id: body; objectName: "pluginPersonaBody"; wrapMode: TextEdit.Wrap; placeholderText: "Persona Markdown" } }
        RowLayout {
            Button {
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
            Button { visible: pane.mode === "mcp"; text: "Delete"; onClicked: pane.invoke("deleteServer", {id: identifier.text}) }
            Button {
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
