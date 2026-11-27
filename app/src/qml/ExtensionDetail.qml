import QtQuick
import QtQuick.Controls.Basic
import "."

Item {
    id: root
    property var item: ({})
    property string error: ""
    signal back()
    component FieldLabel: Text {
        color: Theme.fgSubtle; font.pixelSize: 11; font.bold: true
        font.capitalization: Font.AllUppercase; topPadding: 4
    }
    // app.css .ext-field: label line box 16.5 + margin 6, field margin 16.
    component McpField: Item {
        property string label
        property real afterControl: 0
        default property alias controls: body.data
        width: parent.width; height: 22.5 + body.height + afterControl + 16
        FieldLabel { text: parent.label; width: parent.width; height: 16.5; topPadding: 0; verticalAlignment: Text.AlignVCenter }
        Column { id: body; y: 22.5; width: parent.width }
    }
    component ExtensionScrollBar: ScrollBar {
        id: bar
        padding: 0; implicitWidth: 8
        visible: size < 1
        contentItem: Item {
            implicitWidth: 8; implicitHeight: 8
            Rectangle { anchors.fill: parent; anchors.margins: 2; radius: 6; color: bar.hovered || bar.pressed ? Theme.scrollbarHover : Theme.scrollbar }
        }
        background: Item {}
    }
    function call(action, payload) {
        var result = JSON.parse(shellBridge.extensionAction(action, item.kind, item.id, JSON.stringify(payload || {})))
        error = result.ok ? "" : result.error
        if (result.item) item = result.item
        return result.ok
    }
    function personaRecord(id) { return (root.item.personas || []).find(function(p) { return p.id === id }) || {id:id, name:id, avatarImage:""} }
    function rolesSummary() {
        var names = (root.item.roles || []).map(function(id) { return root.personaRecord(id).name })
        if (!names.length) return I18n.t("extensions.rolesGeneral")
        if (names.length <= 2) return names.join(I18n.locale === "en" ? ", " : "、")
        return I18n.t("extensions.rolesSummary").replace("{names}", names.slice(0,2).join(", ")).replace("{rest}",names.length-2).replace("{n}",names.length)
    }
    function save(field, value) { var patch = {}; patch[field] = value; call("update", patch) }
    Connections {
        target: shellBridge
        function onExtensionsChanged() {
            if (root.item.kind === "mcp") {
                var result = JSON.parse(shellBridge.extensionAction("detail", "mcp", root.item.id, "{}"))
                if (result.ok) { var copy = Object.assign({}, root.item); copy.status = result.item.status; copy.tools = result.item.tools; copy.lastError = result.item.lastError; root.item = copy }
            }
        }
    }
    Item {
        id: toolbar; parent: root.item.kind === "mcp" ? scroll.contentItem.contentItem : root
        x: root.item.kind === "mcp" ? 0 : 20; y: 11; width: root.width - (root.item.kind === "mcp" ? 48 : 40); height: 40
        Icon { x: 6; anchors.verticalCenter: parent.verticalCenter; name: IconData.chevronLeft; size: 16; color: Theme.fgMuted }
        Text { x: 26; anchors.verticalCenter: parent.verticalCenter; text: I18n.t("common.back"); color: Theme.fgMuted; font.pixelSize: 13 }
        MouseArea { width: 80; height: parent.height; onClicked: root.back() }
        Icon { anchors.right: parent.right; anchors.rightMargin: 118; anchors.verticalCenter: parent.verticalCenter; name: IconData.trash2; size: 15; color: Theme.fgSubtle }
        MouseArea { anchors.right: parent.right; anchors.rightMargin: 110; width: 30; height: parent.height; onClicked: confirm.open() }
        Text { anchors.right: parent.right; anchors.rightMargin: 50; anchors.verticalCenter: parent.verticalCenter; text: I18n.t("extensions.enable"); color: Theme.fgMuted; font.pixelSize: 12 }
        Rectangle {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: 38; height: 22; radius: 11; color: root.item.enabled ? Theme.accent : Theme.bgActive
            Rectangle { x: root.item.enabled ? 18 : 2; y: 2; width: 18; height: 18; radius: 9; color: Theme.switchThumb }
            MouseArea { anchors.fill: parent; onClicked: root.save("enabled", !root.item.enabled) }
        }
    }
    Dialog {
        id: confirm
        title: I18n.t("common.delete") + " " + (root.item.name || "")
        modal: true; width: 360; anchors.centerIn: parent
        palette.window: Theme.bgPanel; palette.windowText: Theme.fg
        palette.button: Theme.bgElevated; palette.buttonText: Theme.fg
        palette.text: Theme.fg; palette.base: Theme.bgPanel
        background: Rectangle { color: Theme.bgPanel; radius: Theme.radiusLg; border.color: Theme.border }
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { color: Theme.fg; text: I18n.t(root.item.kind === "skill" ? "cf.skillDeleteConfirm" : "cf.mcpDeleteConfirm"); wrapMode: Text.Wrap; width: 320 }
        onAccepted: if (root.call("remove", {})) root.back()
    }
    ScrollView {
        id: scroll; objectName: "extensionDetailScroll"
        contentWidth: availableWidth
        x: 20; y: root.item.kind === "mcp" ? 0 : 60; width: parent.width - (root.item.kind === "mcp" ? 48 : 40); height: parent.height - y
        contentHeight: fields.height + fields.y
        ScrollBar.vertical: ExtensionScrollBar {}
        bottomPadding: 16
        clip: true
        Binding { target: scroll.contentItem; property: "boundsBehavior"; value: Flickable.StopAtBounds }
        Column {
            id: fields; y: root.item.kind === "mcp" ? 60 : 0
            width: scroll.availableWidth; spacing: root.item.kind === "mcp" ? 0 : 12
            Item { width: parent.width; height: root.item.kind === "mcp" ? 61 : 42
                Icon { y: 6; name: root.item.kind === "mcp" ? "M12 22v-5M9 8V2M15 8V2M7 8h10v4a5 5 0 0 1-10 0V8Z" : IconData.puzzle; size: 18; color: Theme.accent }
                Text { x: 34; y: 6; text: root.item.name || ""; color: Theme.fg; font.pixelSize: 14; font.family: Theme.monoFamily; font.bold: true }
                Row { visible: root.item.kind === "mcp"; anchors.right: parent.right; y: 6; spacing: 8
                    Text {
                        font.family: Theme.monoFamily; font.pixelSize: 12
                        text: (root.item.enabled ? (root.item.status === "connected" || root.item.status === "connecting" ? "● " : root.item.status === "disconnected" ? "○ " : "! ") : "○ ") + I18n.t("extensions.status." + (root.item.enabled ? root.item.status || "disconnected" : "off")) + (root.item.enabled && root.item.status === "connected" ? " · " + (root.item.tools || []).length + " " + I18n.t("extensions.tools") : "")
                        color: !root.item.enabled ? Theme.fgSubtle : root.item.status === "connected" ? Theme.success : root.item.status === "error" ? Theme.danger : Theme.fgMuted
                    }
                    Text { visible: root.item.enabled && root.item.status === "error"; text: I18n.t("extensions.retry"); color: Theme.accent; font.pixelSize: 12
                        MouseArea { anchors.fill: parent; onClicked: root.call("retry", {}) }
                    }
                }
                Rectangle { y: 40; width: parent.width; height: 1; color: Theme.border }
            }
            Text { visible: root.item.enabled && !!root.item.lastError; text: root.item.lastError || ""; width: parent.width; wrapMode: Text.Wrap; color: Theme.warning }
            Text { visible: root.error.length > 0; text: root.error; color: Theme.danger; width: parent.width; wrapMode: Text.Wrap }
            Item {
                width: parent.width; height: root.item.kind === "mcp" ? 70.5 : 61
                FieldLabel { text: I18n.t("extensions.roles"); height: root.item.kind === "mcp" ? 16.5 : 17; topPadding: root.item.kind === "mcp" ? 0 : 4; verticalAlignment: Text.AlignVCenter }
            SettingsButton {
                y: root.item.kind === "mcp" ? 22.5 : 29.5
                id: rolesTrigger; objectName: "extensionRolesTrigger"
                width: parent.width; height: 32; leftPadding: 9
                background: Item {
                    Rectangle { visible: rolesPopup.opened; anchors.fill: parent; anchors.margins: -3; radius: 9; color: Theme.dark ? Qt.rgba(124/255,124/255,240/255,0.16) : Qt.rgba(91/255,91/255,214/255,0.1) }
                    Rectangle { anchors.fill: parent; radius: 6; color: Theme.bgElevated; border.color: rolesPopup.opened ? Theme.accent : Theme.borderStrong }
                }
                contentItem: Row { spacing: 8
                    Rectangle {
                        visible: !root.item.roles || !root.item.roles.length
                        width: 20; height: 20; radius: 10; color: Theme.bgSelected
                        Icon { anchors.centerIn: parent; name: IconData.users; size: 12; color: Theme.accent }
                    }
                    AvatarStack { roles: root.item.roles || []; images: {
                        var result = {}; (root.item.personas || []).forEach(function(p) { result[p.id] = p.avatarImage || "" }); return result
                    } }
                    Text { text: root.rolesSummary(); color: Theme.fg; font.pixelSize: 13 }
                }
                Icon { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; name: IconData.chevronDown; rotation: rolesPopup.opened ? 180 : 0; size: 15; color: Theme.fgSubtle }
                onClicked: rolesPopup.open()
                Keys.onPressed: function(event) {
                    if ([Qt.Key_Down, Qt.Key_Up, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].indexOf(event.key) >= 0) { rolesPopup.open(); event.accepted = true }
                }
                Popup {
                    id: rolesPopup; objectName: "extensionRolesPopup"; focus: true; y: parent.height + 6; width: parent.width
                    padding: 7
                    property int activeRow: 0
                    property string typedText: ""
                    property double typedAt: 0
                    function typeAhead(text) {
                        var now = Date.now()
                        typedText = (now - typedAt < 600 ? typedText : "") + text.toLowerCase()
                        typedAt = now
                        var labels = [I18n.t("extensions.rolesGeneral")].concat((root.item.personas || []).map(function(p) { return p.name }))
                        var hit = labels.findIndex(function(label) { return label.toLowerCase().indexOf(typedText) === 0 })
                        if (hit >= 0) activeRow = hit
                    }
                    function pick(index) {
                        if (index === 0) { root.save("roles", null); close(); rolesTrigger.forceActiveFocus(); return }
                        var id = root.item.personas[index - 1].id
                        var roles = (root.item.roles || []).slice(); var i = roles.indexOf(id)
                        if (i >= 0) roles.splice(i, 1); else roles.push(id)
                        root.save("roles", roles.length ? roles : null)
                    }
                    onOpened: {
                        rolesContent.forceActiveFocus()
                        var picked = root.item.roles || []
                        activeRow = picked.length ? 1 + (root.item.personas || []).findIndex(function(p) { return picked.indexOf(p.id) >= 0 }) : 0
                    }
                    background: Item {
                        SoftShadow { target: rolesBackground }
                        Rectangle { id: rolesBackground; anchors.fill: parent; color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
                    }
                    contentItem: Column {
                        id: rolesContent; focus: true
                        Keys.onPressed: function(event) {
                            var last = (root.item.personas || []).length
                            if (event.key === Qt.Key_Down) rolesPopup.activeRow = Math.min(last, rolesPopup.activeRow + 1)
                            else if (event.key === Qt.Key_Up) rolesPopup.activeRow = Math.max(0, rolesPopup.activeRow - 1)
                            else if (event.key === Qt.Key_Home) rolesPopup.activeRow = 0
                            else if (event.key === Qt.Key_End) rolesPopup.activeRow = last
                            else if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].indexOf(event.key) >= 0) rolesPopup.pick(rolesPopup.activeRow)
                            else if (event.key === Qt.Key_Tab) { rolesPopup.close(); return }
                            else if (event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127 && !(event.modifiers & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier))) rolesPopup.typeAhead(event.text)
                            else return
                            event.accepted = true
                        }
                        Item { width: parent.width; height: 48.75
                            Rectangle { anchors.fill: parent; radius: 8; color: rolesPopup.activeRow === 0 ? Theme.bgHover : "transparent" }
                            Icon { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; size: 15; name: "M20 6 9 17l-5-5"; color: Theme.accent; visible: !root.item.roles || !root.item.roles.length }
                            Rectangle { x: 8; y: 11.375; width: 26; height: 26; radius: 13; color: Theme.bgSelected
                                Icon { anchors.centerIn: parent; name: IconData.users; size: 14; color: Theme.accent }
                            }
                            Text { x: 44; y: 6; text: I18n.t("extensions.rolesGeneral"); color: Theme.fg; font.pixelSize: 13 }
                            Text { x: 44; y: 25.5; text: I18n.t("extensions.rolesGeneralHint"); color: Theme.fgSubtle; font.pointSize: 8.625 }
                            MouseArea { anchors.fill: parent; hoverEnabled: true; onPositionChanged: rolesPopup.activeRow = 0; onClicked: { root.save("roles", null); rolesPopup.close() } }
                        }
                        Item { width: parent.width; height: 13
                            Rectangle { x: 4; y: 6; width: parent.width - 8; height: 1; color: Theme.border }
                        }
                        Text { text: I18n.t("extensions.rolesOnly"); color: Theme.fgSubtle; font.pixelSize: 11; height: 26.5; leftPadding: 8; topPadding: 6 }
                        Repeater {
                            model: root.item.personas || []
                            Item {
                                required property var modelData
                                required property int index
                                Rectangle { anchors.fill: parent; radius: 8; color: rolesPopup.activeRow === index + 1 ? Theme.bgHover : "transparent" }
                                width: parent.width; height: modelData.desc ? 48.75 : 38
                                Avatar { x: 8; anchors.verticalCenter: parent.verticalCenter; persona: modelData.id; imageSource: modelData.avatarImage || ""; size: 26 }
                                Text { x: 44; y: modelData.desc ? 6 : 9.25; text: modelData.name; color: Theme.fg; font.pixelSize: 13 }
                                Text { x: 44; y: 25.5; width: parent.width - 70; text: modelData.desc || ""; elide: Text.ElideRight; color: Theme.fgSubtle; font.pointSize: 8.625 }
                                Icon { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; size: 15; name: "M20 6 9 17l-5-5"; visible: (root.item.roles || []).indexOf(modelData.id) >= 0; color: Theme.accent }
                                MouseArea { anchors.fill: parent; hoverEnabled: true; onPositionChanged: rolesPopup.activeRow = index + 1; onClicked: {
                                    var roles = (root.item.roles || []).slice(); var i = roles.indexOf(modelData.id)
                                    if (i >= 0) roles.splice(i,1); else roles.push(modelData.id)
                                    root.save("roles", roles.length ? roles : null)
                                } }
                            }
                        }
                    }
                }
            }
            }
            FieldLabel { visible: root.item.kind === "skill"; text: I18n.t("extensions.instructions") }
            Column {
                visible: root.item.kind === "mcp"; width: parent.width; spacing: 0
                McpField { label: I18n.t("extensions.transport")
                ComboBox {
                    id: transportChoice
                    width: parent.width; height: 32; leftPadding: 12; rightPadding: 28
                    font.family: Theme.monoFamily; font.pixelSize: 12
                    contentItem: Text { text: transportChoice.displayText; font: transportChoice.font; color: Theme.fg; verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { radius: Theme.radiusSm; color: Theme.bgElevated; border.color: Theme.borderStrong }
                    indicator: Icon { x: transportChoice.width - 24; y: 10; name: IconData.chevronDown; size: 12; color: Theme.fgSubtle }
                    palette.button: Theme.bgElevated
                    palette.buttonText: Theme.fg
                    palette.base: Theme.bgPanel
                    palette.text: Theme.fg
                    model: ["stdio", "sse", "http"]
                    currentIndex: Math.max(0, model.indexOf(root.item.transport || "stdio"))
                    onActivated: root.save("transport", currentText)
                }
                }
                McpField { label: I18n.t(root.item.transport === "stdio" ? "extensions.command" : "extensions.url")
                SettingsField {
                    width: parent.width; height: 32; font.family: Theme.monoFamily; font.pixelSize: 12
                    text: root.item.transport === "stdio" ? (root.item.command || "") : (root.item.url || "")
                    onEditingFinished: root.save(root.item.transport === "stdio" ? "command" : "url", text)
                }
                }
                // The inline HTML textarea reserves 5.5px below its baseline.
                McpField { visible: root.item.transport === "stdio"; label: I18n.t("extensions.args"); afterControl: 5.5
                TextArea {
                    visible: root.item.transport === "stdio"; width: parent.width; height: Math.max(72, contentHeight + 16)
                    font.family: Theme.monoFamily; font.pixelSize: 12; padding: 10; wrapMode: TextEdit.Wrap
                    text: (root.item.args || []).join("\n"); color: Theme.fg
                    background: Rectangle { radius: Theme.radiusSm; color: Theme.bgElevated; border.color: Theme.borderStrong }
                    onActiveFocusChanged: if (!activeFocus && root.item.kind === "mcp") root.save("args", text.split("\n").filter(function(v) { return v.trim().length > 0 }))
                }
                }
                McpField { label: I18n.t(root.item.transport === "stdio" ? "extensions.env" : "extensions.headers")
                Column { width: parent.width; spacing: 8
                Repeater {
                    model: root.item[root.item.transport === "stdio" ? "env" : "headers"] || []
                    Row {
                        id: kv
                        required property var modelData
                        required property int index
                        spacing: 8; width: parent.width
                        property string secretDraft: ""
                        property string saveState: ""
                        function saveSecret() {
                            if (!modelData.key || !secretDraft) return
                            secretTimer.stop(); saveState = "saving"
                            var result = JSON.parse(shellBridge.extensionAction("secret", "mcp", root.item.id, JSON.stringify({field:modelData.key,value:secretDraft})))
                            root.error = result.ok ? "" : result.error
                            saveState = result.ok ? "saved" : ""
                        }
                        Timer { id: secretTimer; interval: 600; onTriggered: kv.saveSecret() }
                        function patch(field, value) {
                            var group = root.item.transport === "stdio" ? "env" : "headers"
                            var rows = JSON.parse(JSON.stringify(root.item[group] || []))
                            rows[index][field] = value; root.save(group, rows)
                        }
                        SettingsField { width: parent.width * 0.34; height: 32; font.family: Theme.monoFamily; font.pixelSize: 12; text: kv.modelData.key; placeholderText: I18n.t("extensions.kvKey"); onEditingFinished: kv.patch("key", text) }
                        SettingsField {
                            width: parent.width * 0.66 - 72; height: 32; font.family: Theme.monoFamily; font.pixelSize: 12
                            text: kv.modelData.secret ? kv.secretDraft : kv.modelData.value
                            echoMode: kv.modelData.secret ? TextInput.Password : TextInput.Normal
                            placeholderText: kv.modelData.secret ? I18n.t(kv.modelData.configured ? "extensions.secretPlaceholder" : "extensions.secretValuePlaceholder") : I18n.t("extensions.kvValue")
                            onTextEdited: if (kv.modelData.secret) { kv.secretDraft = text; kv.saveState = ""; secretTimer.restart() }
                            onEditingFinished: {
                                if (kv.modelData.secret) kv.saveSecret()
                                else kv.patch("value", text)
                            }
                            Row { y: parent.height + 3; spacing: 4; visible: kv.modelData.secret && (!!kv.saveState || kv.modelData.configured)
                                Icon { anchors.verticalCenter: parent.verticalCenter; visible: kv.saveState !== "saving"; size: 12; color: Theme.success
                                    name: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z|m9 12 2 2 4-4" }
                                Text {
                                    text: I18n.t(kv.saveState === "saved" ? "extensions.secretSaved" : kv.saveState === "saving" ? "extensions.secretSaving" : "extensions.secretConfigured")
                                    color: Theme.success; font.pixelSize: 11; font.weight: Font.DemiBold
                                }
                            }
                        }
                        Item { width: 24; height: kv.modelData.secret && (!!kv.saveState || kv.modelData.configured) ? 51.5 : 32
                            Icon { anchors.horizontalCenter: parent.horizontalCenter; y: 9.5; size: 13; color: kv.modelData.secret ? Theme.accent : Theme.fgMuted
                                name: "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z|" + (kv.modelData.secret ? "M7 11V7a5 5 0 0 1 10 0v4" : "M7 11V7a5 5 0 0 1 9.9-1") }
                            MouseArea { anchors.fill: parent; onClicked: {
                                var wasSecret = kv.modelData.secret; var key = kv.modelData.key
                                kv.patch("secret", !wasSecret)
                                if (wasSecret) shellBridge.extensionAction("secret", "mcp", root.item.id, JSON.stringify({field:key,value:""}))
                            } }
                        }
                        SettingsButton {
                            text: "×"; width: 24; height: 32
                            background: Rectangle { color: parent.hovered ? Theme.bgHover : "transparent" }
                            onClicked: { var group = root.item.transport === "stdio" ? "env" : "headers"; var rows = root.item[group].slice(); rows.splice(kv.index,1); root.save(group,rows) }
                        }
                    }
                }
                SettingsButton {
                    text: "+  " + I18n.t("extensions.addRow"); height: 26
                    background: Rectangle { color: parent.hovered ? Theme.bgHover : "transparent"; radius: Theme.radiusSm }
                    onClicked: {
                        var group = root.item.transport === "stdio" ? "env" : "headers"
                        var copy = JSON.parse(JSON.stringify(root.item)); copy[group].push({key:"",value:"",secret:false,configured:false}); root.item = copy
                    }
                }
                }
                }
                McpField { label: I18n.t("extensions.discoveredTools")
                Text { visible: !(root.item.tools || []).length; text: I18n.t("extensions.noToolsYet"); color: Theme.fgSubtle; font.pixelSize: 13; lineHeightMode: Text.FixedHeight; lineHeight: 19.5 }
                Repeater { model: root.item.tools || []; Item {
                    required property var modelData; required property int index
                    width: parent.width; height: Math.max(toolName.height, toolDesc.height) + 16 + (index < root.item.tools.length - 1 ? 1 : 0)
                    Text { id: toolName; y: 8; width: parent.width * 0.34; text: modelData.name; wrapMode: Text.Wrap; color: Theme.accent; font.family: Theme.monoFamily; font.pixelSize: 12; lineHeightMode: Text.FixedHeight; lineHeight: 18 }
                    Text { id: toolDesc; x: toolName.width + 12; y: 8; text: modelData.description; width: parent.width - x; wrapMode: Text.Wrap; color: Theme.fgSubtle; font.pixelSize: 12; lineHeightMode: Text.FixedHeight; lineHeight: 18 }
                    Rectangle { visible: index < root.item.tools.length - 1; anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Theme.border }
                } }
                }
            }
        }
    }
    Rectangle {
        visible: root.item.kind === "skill"
        x: 20; y: 214; width: parent.width - 40; height: parent.height - y - 18
        radius: 6; color: Theme.bgElevated; border.color: Theme.border
        Flickable {
            id: instructionsScroll; objectName: "extensionInstructionsScroll"
            anchors.fill: parent; anchors.leftMargin: 17; anchors.rightMargin: 3; anchors.topMargin: 13; anchors.bottomMargin: 13; clip: true; contentWidth: width
            contentHeight: instructionsText.height; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ExtensionScrollBar { x: instructionsScroll.width - width + 2 }
            TextEdit {
                id: instructionsText
                width: instructionsScroll.width - 14; height: contentHeight
                text: shellBridge ? shellBridge.extensionInstructions(root.item.instructions || I18n.t("extensions.instructionsEmpty"), width, Theme.dark) : ""
                textFormat: TextEdit.RichText; readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: Theme.fg; font.pixelSize: 13
            }
        }
    }

}
