// 角色花名册 + 资料卡 + 编辑（原版 Rail.tsx 角色 tab / ProfileView.tsx / PersonaEditor）。
// 所有写操作经 ShellBridge → PersonaStore 落盘；这里不存第二份角色数据。
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Rectangle {
    id: roster
    objectName: "personaRoster"
    required property var shell
    property string mode: "list"          // list | detail | edit
    property var rows: []
    property var selected: ({})
    property string selectedId: ""
    property string editId: ""
    property string query: ""
    property string notice: ""
    property var memoryRows: []
    property string memoryTitle: ""
    property string memoryBody: ""

    color: Theme.bg

    function reload() {
        rows = shellBridge ? shellBridge.personaRecords() : []
    }
    function visibleRows() {
        var q = query.trim().toLowerCase()
        if (!q) return rows
        return rows.filter(function (row) {
            return ((row.name || "") + " " + (row.description || "")).toLowerCase().indexOf(q) >= 0
        })
    }
    function openDetail(id) {
        selectedId = String(id)
        selected = shellBridge.personaDetail(selectedId)
        memoryRows = shellBridge.roleMemories(selectedId)
        mode = "detail"
    }
    function addMemory() {
        var result = shellBridge.roleMemorySave(selectedId, JSON.stringify({title: memoryTitle, body: memoryBody, type: "reference"}))
        if (result.ok) { memoryTitle = ""; memoryBody = ""; memoryRows = shellBridge.roleMemories(selectedId) }
        else notice = result.error || "保存失败"
    }
    function removeMemory(id) {
        if (!shellBridge.roleMemoryDelete(selectedId, String(id)).ok) notice = "删除失败"
        memoryRows = shellBridge.roleMemories(selectedId)
    }
    function openEdit(row) {
        editId = row && row.id ? String(row.id) : roster.selectedId
        nameField.text = row && row.name ? row.name : ""
        descField.text = row && row.description ? row.description : ""
        promptField.text = row && row.prompt ? row.prompt : ""
        avatarPreview.source = row && row.avatarImage ? row.avatarImage : ""
        mode = "edit"
    }
    function save() {
        var payload = JSON.stringify({
            id: editId,
            name: nameField.text,
            description: descField.text,
            prompt: promptField.text
        })
        if (!shellBridge.personaSave(payload)) { notice = "保存失败"; return }
        notice = ""
        reload()
        mode = "list"
    }
    function remove(id) {
        if (!shellBridge.personaDelete(String(id))) { notice = "删除失败"; return }
        reload(); mode = "list"
    }
    function move(id, delta) {
        var ids = rows.map(function (r) { return r.id })
        var at = ids.indexOf(id)
        var to = at + delta
        if (at < 0 || to < 0 || to >= ids.length) return
        ids.splice(to, 0, ids.splice(at, 1)[0])
        if (!shellBridge.personaReorder(ids)) notice = "排序失败"
        reload()
    }

    Component.onCompleted: reload()
    onVisibleChanged: if (visible) reload()

    // ── 列表 ────────────────────────────────────────────────────────────
    Item {
        visible: roster.mode === "list"
        anchors.fill: parent
        SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: roster.shell.page = "chat" }
        Text { x: 120; y: 22; text: I18n.t("cf.tabRoster"); color: Theme.fg; font.pixelSize: 20; font.weight: 700 }
        SettingsButton {
            objectName: "rosterAdd"
            anchors.right: parent.right; anchors.rightMargin: 116; y: 20
            text: I18n.t("cf.addPersona")
            onClicked: roster.openEdit(null)
        }
        SettingsField {
            objectName: "rosterSearch"
            x: 20; y: 68; width: parent.width - 40
            placeholderText: I18n.t("cf.searchRoster")
            onTextChanged: roster.query = text
        }
        ListView {
            id: list
            objectName: "rosterList"
            x: 20; y: 116; width: parent.width - 40; height: parent.height - y - 20
            clip: true; spacing: 8; model: roster.visibleRows()
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: SettingsScrollBar {}
            delegate: Rectangle {
                required property var modelData
                objectName: "personaRow_" + modelData.id
                width: list.width; height: 84
                color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
                MouseArea { anchors.fill: parent; onClicked: roster.openDetail(modelData.id) }
                Avatar { x: 12; y: 14; width: 56; height: 56; persona: modelData.id; imageSource: modelData.avatarImage || ""; size: 56 }
                Text { x: 82; y: 12; width: parent.width - 360; text: modelData.name; color: Theme.fg; font.pixelSize: 16; font.weight: 600 }
                Text { x: 82; y: 40; width: parent.width - 360; text: modelData.description; color: Theme.fgMuted; elide: Text.ElideRight; font.pixelSize: 12 }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    SettingsButton { objectName: "personaProfile_" + modelData.id; text: "资料"; onClicked: roster.openDetail(modelData.id) }
                    SettingsButton { objectName: "personaUp_" + modelData.id; text: "↑"; onClicked: roster.move(modelData.id, -1) }
                    SettingsButton { objectName: "personaDown_" + modelData.id; text: "↓"; onClicked: roster.move(modelData.id, 1) }
                    SettingsButton {
                        objectName: "rosterStart_" + modelData.id
                        text: I18n.t("cf.startChat")
                        onClicked: {
                            var id = shellBridge.startQuickStart(modelData.id)
                            if (id) { roster.shell.page = "chat" }
                        }
                    }
                }
            }
        }
        Text { anchors.centerIn: list; visible: roster.visibleRows().length === 0; text: I18n.t("cf.searchNoResults"); color: Theme.fgMuted }
    }

    // ── 资料卡 ──────────────────────────────────────────────────────────
    Item {
        visible: roster.mode === "detail"
        anchors.fill: parent
        SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: roster.mode = "list" }
        SettingsButton { objectName: "personaEdit"; anchors.right: parent.right; anchors.rightMargin: 116; y: 20; text: I18n.t("cf.editPersona"); onClicked: roster.openEdit(roster.selected) }
        Avatar { x: 20; y: 70; width: 88; height: 88; persona: roster.selected.id || "general"; imageSource: roster.selected.avatarImage || ""; size: 88 }
        Text { x: 124; y: 74; width: parent.width - 150; text: roster.selected.name || ""; color: Theme.fg; font.pixelSize: 22; font.weight: 700 }
        Text { x: 124; y: 108; width: parent.width - 150; text: roster.selected.description || ""; color: Theme.fgMuted; font.pixelSize: 13; wrapMode: Text.Wrap }
        Text { x: 20; y: 180; width: 120; text: I18n.t("cf.personaPrompt"); color: Theme.fgMuted; font.pixelSize: 12 }
        TextArea {
            objectName: "personaPromptView"
            x: 20; y: 204; width: parent.width - 40; height: 260
            readOnly: true; text: roster.selected.prompt || ""
            color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13
            background: Rectangle { color: Theme.bgPanel; border.color: Theme.border; radius: 6 }
        }
        Text { x: 20; y: 478; text: "角色记忆"; color: Theme.fg; font.pixelSize: 13; font.weight: 600 }
        Column {
            x: 20; y: 500; width: parent.width - 40; spacing: 4
            Repeater {
                model: roster.memoryRows
                delegate: Row {
                    required property var modelData
                    width: parent.width; height: 26
                    Text { width: parent.width - 50; text: modelData.title; color: Theme.fg; font.pixelSize: 12; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter }
                    SettingsButton { objectName: "memoryDelete_" + modelData.id; text: "删除"; height: 24; onClicked: roster.removeMemory(modelData.id) }
                }
            }
            Row {
                width: parent.width; spacing: 6
                SettingsField { id: memoryTitleField; objectName: "memoryTitle"; width: 180; placeholderText: "记忆标题" }
                SettingsField { id: memoryBodyField; objectName: "memoryBody"; width: parent.width - 300; placeholderText: "记忆正文" }
                SettingsButton { objectName: "memoryAdd"; text: "添加"; onClicked: { roster.memoryTitle = memoryTitleField.text; roster.memoryBody = memoryBodyField.text; roster.addMemory(); memoryTitleField.text = ""; memoryBodyField.text = "" } }
            }
        }
        SettingsButton {
            objectName: "personaDelete"
            x: 20; y: 600; destructive: true; text: I18n.t("common.delete")
            onClicked: roster.remove(roster.selected.id)
        }
        Text { x: 20; y: 548; text: roster.notice; color: Theme.danger; visible: text.length > 0 }
    }

    // ── 编辑 ────────────────────────────────────────────────────────────
    Item {
        visible: roster.mode === "edit"
        anchors.fill: parent
        SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: roster.mode = "list" }
        Text { x: 120; y: 22; text: roster.editId ? I18n.t("cf.editPersona") : I18n.t("cf.addPersona"); color: Theme.fg; font.pixelSize: 20; font.weight: 700 }
        Row {
            x: 20; y: 70; spacing: 16
            Rectangle {
                width: 88; height: 88; radius: 44; color: Theme.bgPanel; border.color: Theme.border
                Image { id: avatarPreview; anchors.fill: parent; fillMode: Image.PreserveAspectCrop }
            }
            Column {
                spacing: 8
                SettingsButton {
                    objectName: "personaPickAvatar"; text: I18n.t("cf.changeAvatar")
                    onClicked: { var uri = shellBridge.personaPickAvatar(roster.editId); if (uri) avatarPreview.source = uri }
                }
                SettingsButton {
                    objectName: "personaClearAvatar"; text: I18n.t("cf.removeAvatar")
                    onClicked: { if (shellBridge.personaClearAvatar(roster.editId)) avatarPreview.source = "" }
                }
            }
        }
        SettingsField { id: nameField; objectName: "personaName"; x: 20; y: 180; width: parent.width - 40; placeholderText: I18n.t("cf.personaName") }
        SettingsField { id: descField; objectName: "personaDescription"; x: 20; y: 226; width: parent.width - 40; placeholderText: I18n.t("cf.personaDescription") }
        TextArea {
            id: promptField; objectName: "personaPromptEdit"
            x: 20; y: 272; width: parent.width - 40; height: 240
            placeholderText: I18n.t("cf.personaPrompt")
            color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13
            background: Rectangle { color: Theme.bgPanel; border.color: Theme.border; radius: 6 }
        }
        Row {
            x: 20; y: 530; spacing: 8
            SettingsButton { objectName: "personaSave"; text: I18n.t("common.save"); onClicked: roster.save() }
            SettingsButton { text: I18n.t("common.cancel"); onClicked: roster.mode = "list" }
        }
        Text { x: 20; y: 566; text: roster.notice; color: Theme.danger; visible: text.length > 0 }
    }
}
