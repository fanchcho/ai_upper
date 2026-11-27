// F34/F36：正文右键后的轮次列表，用于选择删除/回滚（原版 Conversation.tsx 的消息级操作入口）。
import QtQuick
import QtQuick.Controls
import "."

Popup {
    id: root
    objectName: "turnListPopup"
    property var turns: []
    property string mode: "delete"
    signal chosen(int turn)
    width: 360; height: Math.min(420, 70 + (turns || []).length * 34); padding: 10
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: turns = shellBridge.sessionTurns()
    Column {
        width: parent.width; spacing: 6
        Text { text: root.mode === "delete" ? "选择要删除的轮次" : "选择要回滚的轮次"; color: Theme.fg; font.pixelSize: 14; font.weight: 600 }
        Repeater {
            model: root.turns
            delegate: Rectangle {
                required property var modelData
                width: parent.width; height: 32; radius: Theme.radiusSm
                color: rowMouse.containsMouse ? Theme.bgHover : Theme.bgPanel
                Text { x: 8; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 60; text: (modelData.turn + 1) + ". " + modelData.label; color: Theme.fg; font.pixelSize: 12; elide: Text.ElideRight }
                MouseArea { id: rowMouse; anchors.fill: parent; hoverEnabled: true; onClicked: { root.chosen(modelData.turn); root.close() } }
            }
        }
        SettingsButton { text: "关闭"; onClicked: root.close() }
    }
}
