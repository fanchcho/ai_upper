import QtQuick
import QtQuick.Controls.Basic
import "."
Rectangle {
    id: root
    visible: false
    color: Theme.bg
    property var turns: []
    property var preview: ({files:[],commands:[]})
    property int selected: -1
    property string error: ""
    function openPanel() {
        var data = shellBridge.rewind("list",0,"both")
        turns = data.turns || []; selected = -1; error = data.error || ""; visible = true
    }
    Column {
        x: 30; y: 30; width: parent.width-60; spacing: 12
        Text { font.family: Theme.sansFamily; text: "回滚 / rewind"; color: Theme.fg; font.pixelSize: 22 }
        SettingsButton { objectName: "rewindClose"; text: "返回"; onClicked: root.visible = false }
        Repeater {
            model: root.turns
            SettingsButton {
                required property var modelData
                objectName: "rewindTurn_" + modelData.turn
                text: "第 " + (modelData.turn+1) + " 轮：" + modelData.text
                onClicked: {
                    root.selected = modelData.turn
                    root.preview = shellBridge.rewind("preview",root.selected,"both")
                    root.error = root.preview.error || ""
                }
            }
        }
        Text { font.family: Theme.sansFamily; width: parent.width; wrapMode: Text.Wrap; color: Theme.fg; text: (root.preview.files || []).map(function(row) { return row.path + "\n" + row.status }).join("\n\n") + ((root.preview.commands || []).length ? "\n命令影响无法撤销：\n" + root.preview.commands.join("\n") : "") }
        ComboBox { id: mode; font.family: Theme.sansFamily; model: ["对话和文件", "仅文件", "仅对话"] }
        Row { spacing: 12
            SettingsButton {
                objectName: "rewindApply"; text: "应用回滚"; enabled: root.selected >= 0
                onClicked: { var data = shellBridge.rewind("apply",root.selected,["both","code","conversation"][mode.currentIndex]); root.error = data.error || "已回滚" }
            }
            SettingsButton {
                objectName: "rewindUndo"; text: "撤销回滚"
                onClicked: { var data = shellBridge.rewind("undo",0,"both"); root.error = data.error || "已撤销" }
            }
        }
        Text { font.family: Theme.sansFamily; objectName: "rewindResult"; width: parent.width; wrapMode: Text.Wrap; text: root.error; color: Theme.fg }
    }
}
