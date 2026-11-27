import QtQuick
import QtQuick.Controls
import "."

Rectangle {
    id: roster
    objectName: "personaRoster"
    required property var shell
    color: Theme.bg
    property string query: ""
    readonly property var rows: shell.quickStartPersonas.filter(function(row) {
        return (row.name + " " + row.desc).toLowerCase().indexOf(query.trim().toLowerCase()) >= 0
    })
    SettingsButton {
        x: 20; y: 20
        text: I18n.t("common.back")
        onClicked: roster.shell.page = "chat"
    }
    SettingsButton {
        objectName: "rosterManage"
        anchors.right: parent.right; anchors.rightMargin: 116; y: 20
        text: I18n.t("cf.addPersona")
        onClicked: roster.shell.page = "personas-editor"
    }
    SettingsField {
        objectName: "rosterSearch"
        x: 20; y: 70; width: parent.width - 40
        placeholderText: I18n.t("cf.searchRoster")
        onTextChanged: roster.query = text
    }
    ListView {
        id: list
        objectName: "rosterList"
        x: 20; y: 120; width: parent.width - 40; height: parent.height - y - 20
        clip: true; spacing: 8; model: roster.rows
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: SettingsScrollBar {}
        delegate: Rectangle {
            required property var modelData
            width: list.width; height: 84
            color: Theme.bgPanel; radius: Theme.radiusSm
            border.color: Theme.border
            Text { x: 16; y: 12; width: parent.width - 150; text: modelData.name; color: Theme.fg; font.pixelSize: 16 }
            Text { x: 16; y: 40; width: parent.width - 150; text: modelData.desc; elide: Text.ElideRight; color: Theme.fgMuted }
            SettingsButton {
                objectName: "rosterStart_" + modelData.id
                anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter
                text: I18n.t("cf.startChat")
                onClicked: {
                    var id = shellBridge.startQuickStart(modelData.id)
                    if (id) {
                        roster.shell.filterRoles = []
                        roster.shell.filterFolders = []
                        roster.shell.searchQuery = ""
                        roster.shell.page = "chat"
                    }
                }
            }
        }
    }
    Text { anchors.centerIn: list; visible: roster.rows.length === 0; text: I18n.t("cf.searchNoResults"); color: Theme.fgMuted }
}
