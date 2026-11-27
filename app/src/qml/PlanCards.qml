// F32：exit_plan 计划审阅卡（原版 PlanReviewCard）；正文 + 批准/继续完善/忽略。
import QtQuick
import QtQuick.Controls
import "."

Column {
    id: root
    objectName: "planCards"
    property var plans: []
    width: parent ? parent.width : 0
    spacing: 8
    Repeater {
        model: root.plans || []
        delegate: Rectangle {
            required property var modelData
            width: parent.width
            height: cardCol.implicitHeight + 20
            radius: Theme.radius
            color: Theme.bgPanel
            border.color: modelData.pending ? Theme.accent : Theme.border
            border.width: 1
            Column {
                id: cardCol
                x: 10; y: 10; width: parent.width - 20; spacing: 6
                Row {
                    width: parent.width
                    Text { text: "计划审阅"; color: Theme.fg; font.pixelSize: 13; font.weight: 700; width: parent.width - 80 }
                    Text { text: modelData.decision || (modelData.pending ? "待决定" : "已取消"); color: Theme.fgMuted; font.pixelSize: 11 }
                }
                Text { width: parent.width; text: modelData.plan; color: Theme.fg; font.pixelSize: 12; wrapMode: Text.Wrap; textFormat: Text.MarkdownText }
                Text { visible: (modelData.feedback || "").length > 0; width: parent.width; text: "回复：" + modelData.feedback; color: Theme.fgMuted; font.pixelSize: 11; wrapMode: Text.Wrap }
                Row {
                    visible: modelData.pending === true
                    spacing: 6
                    SettingsButton { objectName: "planApprove_" + modelData.id; text: "批准并执行"; onClicked: shellBridge.answerPlan(modelData.id, "approve", "") }
                    SettingsButton { objectName: "planKeep_" + modelData.id; text: "继续完善"; onClicked: shellBridge.answerPlan(modelData.id, "keep", "请继续完善") }
                    SettingsButton { objectName: "planIgnore_" + modelData.id; text: "忽略"; onClicked: shellBridge.answerPlan(modelData.id, "ignore", "") }
                }
            }
        }
    }
}
