import QtQuick
import QtQuick.Controls.Basic
import "."

Item {
    id: root
    property var item: ({})
    property string error: ""
    signal back()
    function call(action, payload) {
        var result = JSON.parse(shellBridge.extensionAction(action, item.kind, item.id, JSON.stringify(payload || {})))
        error = result.ok ? "" : result.error
        if (result.item) item = result.item
        return result.ok
    }
    function save(field, value) { var patch = {}; patch[field] = value; call("update", patch) }
    Row {
        id: toolbar
        x: 20; y: 12; spacing: 12
        SettingsButton { text: I18n.t("common.back"); onClicked: root.back() }
        SettingsButton { text: I18n.t("common.delete"); onClicked: confirm.open() }
        SettingsCheck {
            text: I18n.t("extensions.enable"); checked: root.item.enabled || false
            palette.windowText: Theme.fg
            onClicked: {
                root.save("enabled", checked)
            }
        }
    }
    Dialog {
        id: confirm
        title: I18n.t("common.delete") + " " + (root.item.name || "")
        modal: true; width: 360; anchors.centerIn: parent
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: I18n.t(root.item.kind === "skill" ? "cf.skillDeleteConfirm" : "cf.mcpDeleteConfirm"); wrapMode: Text.Wrap; width: 320 }
        onAccepted: if (root.call("remove", {})) root.back()
    }
    ScrollView {
        id: scroll
        contentWidth: availableWidth
        anchors { top: toolbar.bottom; topMargin: 12; left: parent.left; right: parent.right; bottom: parent.bottom; margins: 20 }
        clip: true
        Column {
            width: scroll.availableWidth; spacing: 12
            Text { text: root.item.name || ""; color: Theme.fg; font.pixelSize: 17; font.bold: true }
            Text { visible: root.error.length > 0; text: root.error; color: Theme.danger; width: parent.width; wrapMode: Text.Wrap }
            Text { text: I18n.t("extensions.roles"); color: Theme.fgMuted; font.pixelSize: 12 }
            Flow {
                width: parent.width; spacing: 6
                SettingsCheck {
                    text: I18n.t("extensions.rolesGeneral"); checked: !root.item.roles || root.item.roles.length === 0
                    palette.windowText: Theme.fg
                    onClicked: root.save("roles", null)
                }
                Repeater {
                    model: root.item.personas || []
                    SettingsCheck {
                        required property var modelData
                        text: modelData.name; palette.windowText: Theme.fg
                        checked: (root.item.roles || []).indexOf(modelData.id) >= 0
                        onClicked: {
                            var roles = (root.item.roles || []).slice()
                            var index = roles.indexOf(modelData.id)
                            if (index >= 0) roles.splice(index, 1); else roles.push(modelData.id)
                            root.save("roles", roles.length ? roles : null)
                        }
                    }
                }
            }
            Text { visible: root.item.kind === "skill"; text: I18n.t("extensions.instructions"); color: Theme.fgMuted }
            TextEdit {
                visible: root.item.kind === "skill"; width: parent.width
                text: root.item.instructions || I18n.t("extensions.instructionsEmpty")
                textFormat: TextEdit.MarkdownText; readOnly: true; selectByMouse: true
                wrapMode: TextEdit.Wrap; color: Theme.fg; font.pixelSize: 13
            }
            Column {
                visible: root.item.kind === "mcp"; width: parent.width; spacing: 12
                Text { text: I18n.t("extensions.transport"); color: Theme.fgMuted }
                ComboBox {
                    id: transportChoice
                    palette.button: Theme.bgElevated
                    palette.buttonText: Theme.fg
                    palette.base: Theme.bgPanel
                    palette.text: Theme.fg
                    model: ["stdio", "sse", "http"]
                    currentIndex: Math.max(0, model.indexOf(root.item.transport || "stdio"))
                    onActivated: root.save("transport", currentText)
                }
                Text { text: I18n.t(root.item.transport === "stdio" ? "extensions.command" : "extensions.url"); color: Theme.fgMuted }
                SettingsField {
                    width: parent.width
                    text: root.item.transport === "stdio" ? (root.item.command || "") : (root.item.url || "")
                    onEditingFinished: root.save(root.item.transport === "stdio" ? "command" : "url", text)
                }
                Text { visible: root.item.transport === "stdio"; text: I18n.t("extensions.args"); color: Theme.fgMuted }
                TextArea {
                    visible: root.item.transport === "stdio"; width: parent.width
                    text: (root.item.args || []).join("\n"); color: Theme.fg
                    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border }
                    onActiveFocusChanged: if (!activeFocus && root.item.kind === "mcp") root.save("args", text.split("\n").filter(function(v) { return v.trim().length > 0 }))
                }
                Text { text: I18n.t(root.item.transport === "stdio" ? "extensions.env" : "extensions.headers"); color: Theme.fgMuted }
                Repeater {
                    model: root.item[root.item.transport === "stdio" ? "env" : "headers"] || []
                    Row {
                        id: kv
                        required property var modelData
                        required property int index
                        spacing: 4
                        function patch(field, value) {
                            var group = root.item.transport === "stdio" ? "env" : "headers"
                            var rows = JSON.parse(JSON.stringify(root.item[group] || []))
                            rows[index][field] = value; root.save(group, rows)
                        }
                        SettingsField { width: 115; text: kv.modelData.key; placeholderText: I18n.t("extensions.kvKey"); onEditingFinished: kv.patch("key", text) }
                        SettingsField {
                            width: 160; text: kv.modelData.value
                            echoMode: kv.modelData.secret ? TextInput.Password : TextInput.Normal
                            placeholderText: kv.modelData.configured ? I18n.t("extensions.secretConfigured") : I18n.t("extensions.kvValue")
                            onEditingFinished: {
                                if (kv.modelData.secret) { if (text.length) root.call("secret", {field: kv.modelData.key, value: text}) }
                                else kv.patch("value", text)
                            }
                        }
                        SettingsCheck { text: I18n.t("extensions.markSecret"); checked: kv.modelData.secret; onClicked: kv.patch("secret", checked) }
                        SettingsButton {
                            text: "×"
                            onClicked: { var group = root.item.transport === "stdio" ? "env" : "headers"; var rows = root.item[group].slice(); rows.splice(kv.index,1); root.save(group,rows) }
                        }
                    }
                }
                SettingsButton {
                    text: I18n.t("extensions.addRow")
                    onClicked: {
                        var group = root.item.transport === "stdio" ? "env" : "headers"
                        var copy = JSON.parse(JSON.stringify(root.item)); copy[group].push({key:"",value:"",secret:false,configured:false}); root.item = copy
                    }
                }
                Text { text: I18n.t("extensions.discoveredTools"); color: Theme.fgMuted }
                Text { text: I18n.t("extensions.noToolsYet"); color: Theme.fgSubtle }
            }
        }
    }
}
