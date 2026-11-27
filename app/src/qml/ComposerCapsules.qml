// 输入框上方的对话内胶囊：Todo / 待插入 / 后台任务 / 浏览器操作。
// 原版 Composer.tsx:864-866；本移植版只对真实存在的服务显示，空状态不占高。
import QtQuick
import QtQuick.Controls
import "."

Item {
    id: root
    objectName: "composerCapsules"
    property var todo: ({})
    property var pending: []
    property var background: []
    property var browser: null
    property bool todoOpen: false
    property bool backgroundOpen: false
    signal withdrawRequested()
    readonly property bool hasTodo: todo && (todo.items || []).length > 0
    readonly property bool hasPending: (pending || []).length > 0
    readonly property bool hasBackground: (background || []).length > 0
    readonly property bool hasBrowser: browser && browser.open === true
    visible: hasTodo || hasPending || hasBackground || hasBrowser
    height: visible ? 30 : 0
    width: parent ? parent.width : 0

    Row {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        Rectangle {
            objectName: "todoCapsule"
            visible: root.hasTodo
            height: 26; radius: 13; width: todoText.implicitWidth + 22
            color: Theme.bgHover
            Text {
                id: todoText
                anchors.centerIn: parent
                text: (root.todo.title || "待办") + "  " + (root.todo.done || 0) + "/" + (root.todo.total || 0)
                color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 12
            }
            MouseArea { anchors.fill: parent; onClicked: root.todoOpen = !root.todoOpen }
        }
        Rectangle {
            objectName: "pendingInsertsCapsule"
            visible: root.hasPending
            height: 26; radius: 13; width: pendingText.implicitWidth + 22
            color: Theme.bgActive
            Text {
                id: pendingText
                anchors.centerIn: parent
                text: "待插入 " + (root.pending || []).length + " 条（点击撤回）"
                color: Theme.accent; font.family: Theme.sansFamily; font.pixelSize: 12
            }
            MouseArea { anchors.fill: parent; onClicked: root.withdrawRequested() }
        }
        Rectangle {
            objectName: "backgroundCapsule"
            visible: root.hasBackground
            height: 26; radius: 13; width: bgText.implicitWidth + 22
            color: Theme.bgHover
            Text { id: bgText; anchors.centerIn: parent; text: "后台任务 " + (root.background || []).length; color: Theme.fgMuted; font.family: Theme.sansFamily; font.pixelSize: 12 }
            MouseArea { anchors.fill: parent; onClicked: root.backgroundOpen = !root.backgroundOpen }
        }
        Rectangle {
            objectName: "browserCapsule"
            visible: root.hasBrowser
            height: 26; radius: 13; width: 88
            color: Theme.bgHover
            Text { anchors.centerIn: parent; text: "浏览器操作"; color: Theme.fgMuted; font.family: Theme.sansFamily; font.pixelSize: 12 }
        }
    }
    Rectangle {
        objectName: "backgroundCapsuleList"
        visible: root.backgroundOpen && root.hasBackground
        x: 0; y: -height - 4; width: 390; height: visible ? Math.min(260, 14 + (root.background || []).length * 44) : 0
        radius: Theme.radius; color: Theme.bgElevated; border.width: 1; border.color: Theme.border
        z: 20
        Column {
            x: 8; y: 6; width: parent.width - 16; spacing: 2
            Repeater {
                model: root.background || []
                delegate: Row {
                    required property var modelData
                    width: parent.width; height: 40
                    Text { width: 150; text: modelData.name + " · " + modelData.status; color: Theme.fg; font.pixelSize: 12; elide: Text.ElideRight }
                    SettingsButton { objectName: "bgOpen_" + modelData.id; text: "打开"; height: 24; onClicked: shellBridge.openBackground(modelData.id) }
                    SettingsButton { objectName: "bgCancel_" + modelData.id; text: "取消"; height: 24; onClicked: { shellBridge.cancelBackground(modelData.id); root.backgroundOpen = false } }
                    SettingsButton { objectName: "bgRemove_" + modelData.id; text: "移除"; height: 24; onClicked: { root.backgroundOpen = false; shellBridge.removeMember(modelData.id) } }
                }
            }
        }
    }
    Rectangle {
        objectName: "todoCapsuleList"
        visible: root.todoOpen && root.hasTodo
        x: 0; y: 30; width: 300; height: visible ? Math.min(220, 12 + (root.todo.items || []).length * 26) : 0
        radius: Theme.radius; color: Theme.bgElevated; border.width: 1; border.color: Theme.border
        z: 20
        Column {
            x: 10; y: 6; spacing: 2
            Repeater {
                model: root.todo.items || []
                delegate: Text {
                    required property var modelData
                    width: 280; height: 24
                    text: (modelData.status === "completed" ? "✓ " : modelData.status === "in_progress" ? "◐ " : "○ ") + modelData.content
                    color: modelData.status === "completed" ? Theme.fgMuted : Theme.fg
                    font.family: Theme.sansFamily; font.pixelSize: 12; elide: Text.ElideRight
                }
            }
        }
    }
}
