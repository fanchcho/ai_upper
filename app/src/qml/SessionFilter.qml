import QtQuick
import QtQuick.Controls
import "."

Popup {
    id: menu
    objectName: "sessionFilter"
    required property var shell
    width: 285
    height: Math.min(500, options.height + 16)
    padding: 8
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; radius: Theme.radiusSm; border.color: Theme.border }
    contentItem: Flickable {
        clip: true
        contentHeight: options.height
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: options
            width: parent.width
            Text { text: I18n.t("cf.filterRoles"); color: Theme.fgMuted; height: 26 }
            Repeater {
                model: menu.shell.filterRolesAvailable
                delegate: SettingsButton {
                    required property var modelData
                    objectName: "filterRole_" + modelData.id
                    width: options.width
                    text: modelData.name + " (" + menu.shell.filterCount("role", modelData.id) + ")"
                    primary: menu.shell.filterRoles.indexOf(modelData.id) >= 0
                    onClicked: menu.shell.toggleFilter("role", modelData.id)
                }
            }
            Text { text: I18n.t("cf.filterFolders"); color: Theme.fgMuted; height: 26 }
            Repeater {
                model: menu.shell.filterFoldersAvailable
                delegate: SettingsButton {
                    required property var modelData
                    required property int index
                    objectName: "filterFolder_" + index
                    width: options.width
                    text: (modelData.name || I18n.t("cf.filterNoFolder")) + " (" + menu.shell.filterCount("folder", modelData.path) + ")"
                    primary: menu.shell.filterFolders.indexOf(modelData.path) >= 0
                    onClicked: menu.shell.toggleFilter("folder", modelData.path)
                }
            }
        }
    }
}
