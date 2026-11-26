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
        notice = I18n.t("models.keySaved")
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
        Text { text: pane.mode === "custom-model" ? I18n.t("native.message7") : pane.mode === "mcp" ? I18n.t("native.message12") : I18n.t("cf.filterRoles"); color: Theme.fg; font.pixelSize: 18 }
        Text { visible: pane.mode === "custom-model"; text: I18n.t("native.message9"); color: Theme.fgMuted }
        ComboBox {
            id: chooser
            palette.text: Theme.fg
            palette.buttonText: Theme.fg
            palette.base: Theme.bg
            palette.button: Theme.bg
            palette.highlight: Theme.accent
            palette.highlightedText: Theme.accentFg
            contentItem: Text { text: chooser.displayText || I18n.t("native.message17"); color: Theme.fg; verticalAlignment: Text.AlignVCenter; leftPadding: 8 }
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
        SettingsField { id: identifier; objectName: "pluginIdentifier"; visible: pane.mode !== "custom-model"; placeholderText: I18n.t("native.message10"); Layout.fillWidth: true }
        SettingsField { id: address; objectName: "pluginBaseUrl"; visible: pane.mode !== "identities"; placeholderText: I18n.t("native.message4"); Layout.fillWidth: true }
        SettingsField { id: modelName; objectName: "pluginModelName"; visible: pane.mode === "custom-model"; placeholderText: I18n.t("models.displayName"); Layout.fillWidth: true }
        SettingsField { id: command; visible: pane.mode === "mcp"; placeholderText: I18n.t("native.message6"); Layout.fillWidth: true }
        SettingsField { id: argsInput; visible: pane.mode === "mcp"; text: "[]"; placeholderText: I18n.t("native.message3"); Layout.fillWidth: true }
        SettingsCheck { id: enabledBox; objectName: "pluginEnabled"; visible: pane.mode === "mcp"; text: I18n.t("models.enabled"); checked: true }
        SettingsCheck { objectName: "pluginApprovalEnabled"; visible: pane.mode === "mcp"; text: I18n.t("native.message25"); checked: pane.state.approvalEnabled === true; onClicked: pane.invoke("saveApproval", {enabled: checked}) }
        Text { id: keyStatus; visible: pane.mode !== "identities"; text: (pane.mode === "mcp" ? pane.state.servers.some(function(row) { return row.id === identifier.text && row.hasKey }) : pane.state.model.hasKey) ? I18n.t("native.message23") : I18n.t("native.message28"); color: Theme.fgMuted }
        SettingsField { id: secret; objectName: "pluginSecret"; visible: pane.mode !== "identities"; placeholderText: I18n.t("native.message14"); echoMode: TextInput.Password; Layout.fillWidth: true }
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
                placeholderText: I18n.t("native.message16")
                background: Rectangle { color: Theme.bgElevated; border.color: Theme.borderStrong; radius: Theme.radiusSm }
            }
        }
        RowLayout {
            SettingsButton {
                primary: true
                objectName: "pluginSave"
                text: I18n.t("cf.save")
                onClicked: {
                    var value = {key: secret.text.length ? secret.text : undefined}
                    var op
                    if (pane.mode === "custom-model") { op = "saveModel"; value.baseUrl = address.text; value.model = modelName.text }
                    else if (pane.mode === "mcp") {
                        op = "saveServer"; value.id = identifier.text
                        try { value.config = {url: address.text, command: command.text, args: JSON.parse(argsInput.text), enabled: enabledBox.checked} }
                        catch (e) { pane.notice = I18n.t("native.message11"); return }
                    } else { op = "saveIdentity"; value = {id: identifier.text, text: body.text} }
                    if (pane.invoke(op, value)) secret.text = ""
                }
            }
            SettingsButton { visible: pane.mode === "mcp"; destructive: true; text: I18n.t("common.delete"); onClicked: pane.invoke("deleteServer", {id: identifier.text}) }
            SettingsButton {
                visible: pane.mode !== "identities"
                text: I18n.t("native.message5")
                onClicked: {
                    if (pane.mode === "custom-model") pane.invoke("saveModel", {baseUrl: address.text, model: modelName.text, key: ""})
                    else {
                        try { pane.invoke("saveServer", {id: identifier.text, config: {url: address.text, command: command.text, args: JSON.parse(argsInput.text), enabled: enabledBox.checked}, key: ""}) }
                        catch(e) { pane.notice = I18n.t("native.message11") }
                    }
                    secret.text = ""
                }
            }
        }
        Text { text: pane.notice; color: Theme.fgMuted; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Item { Layout.fillHeight: true; visible: pane.mode !== "identities" }
    }
}
