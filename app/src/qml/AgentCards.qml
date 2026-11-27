// F81：propose_agent 角色名片与 create_task 定时任务确认名片。
import QtQuick
import QtQuick.Controls
import "."

Column {
    id: root
    objectName: "agentCards"
    property var proposals: []
    property var autotasks: []
    width: parent ? parent.width : 0
    spacing: 8
    Repeater {
        model: root.proposals || []
        delegate: Rectangle {
            required property var modelData
            width: parent.width; height: 92; radius: Theme.radius; color: Theme.bgPanel; border.color: Theme.border
            Column {
                x: 10; y: 8; width: parent.width - 20; spacing: 4
                Text { text: "角色名片 · " + (modelData.draft.name || ""); color: Theme.fg; font.pixelSize: 13; font.weight: 600 }
                Text { width: parent.width; text: modelData.draft.description || ""; color: Theme.fgMuted; font.pixelSize: 11; elide: Text.ElideRight }
                Row {
                    visible: modelData.status === "pending"
                    spacing: 6
                    SettingsButton { objectName: "proposalAccept_" + modelData.id; text: "接受"; onClicked: shellBridge.resolveProposal(modelData.id, "accepted") }
                    SettingsButton { objectName: "proposalReject_" + modelData.id; text: "拒绝"; onClicked: shellBridge.resolveProposal(modelData.id, "rejected") }
                }
                Text { visible: modelData.status !== "pending"; text: modelData.status === "accepted" ? "已接受" : "已拒绝"; color: Theme.fgMuted; font.pixelSize: 11 }
            }
        }
    }
    Repeater {
        model: root.autotasks || []
        delegate: Rectangle {
            required property var modelData
            width: parent.width; height: 100; radius: Theme.radius; color: Theme.bgPanel; border.color: Theme.border
            Column {
                x: 10; y: 8; width: parent.width - 20; spacing: 4
                Text { text: "定时任务名片 · " + (modelData.draft.title || ""); color: Theme.fg; font.pixelSize: 13; font.weight: 600 }
                Text { width: parent.width; text: (modelData.draft.schedule && modelData.draft.schedule.kind) + " " + ((modelData.draft.schedule && (modelData.draft.schedule.at || modelData.draft.schedule.cron)) || ""); color: Theme.fgMuted; font.pixelSize: 11 }
                Row {
                    visible: modelData.status === "pending"
                    spacing: 6
                    SettingsButton { objectName: "autotaskCreate_" + modelData.id; text: "创建"; onClicked: shellBridge.resolveAutotask(modelData.id, "create", JSON.stringify(modelData.draft)) }
                    SettingsButton { objectName: "autotaskDismiss_" + modelData.id; text: "忽略"; onClicked: shellBridge.resolveAutotask(modelData.id, "dismiss", "{}") }
                }
                Text { visible: modelData.status !== "pending"; text: modelData.status === "created" ? "已创建 " + (modelData.taskId || "") : "已忽略"; color: Theme.fgMuted; font.pixelSize: 11 }
            }
        }
    }
}
