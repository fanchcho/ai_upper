import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs as Dialogs
import "."

Rectangle {
    id: prompt
    property var request: null
    objectName: "interactionPrompt"
    visible: request !== null
    width: Math.min(520, parent.width - 40)
    height: content.implicitHeight + 40
    color: Theme.bg
    border.color: Theme.fgMuted
    radius: 12
    z: 2000
    anchors.centerIn: parent
    Dialogs.FolderDialog {
        id: memberFolder
        objectName: "memberFolderDialog"
        onAccepted: {
            if (prompt.request && shellBridge.acceptMemberFolder(prompt.request.id,selectedFolder)) prompt.request=null
        }
        onRejected: prompt.respond("dismissed", "")
    }
    function respond(outcome, text) {
        if (request && shellBridge.answerInteraction(request.id, outcome, text)) {
            request = null
            answer.text = ""
        }
    }
    Connections {
        target: shellBridge
        function onInteractionsChanged(rows) {
            var next = rows.length ? rows[0] : null
            if (!next || !prompt.request || next.id !== prompt.request.id) {
                prompt.request = next
                answer.text = ""
            }
        }
    }
    MouseArea { anchors.fill: parent }
    ColumnLayout {
        id: content
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
        spacing: 12
        Text { text: prompt.request ? prompt.request.question : ""; color: Theme.fg; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Repeater {
            model: prompt.request ? prompt.request.choices : []
            Button { required property string modelData; text: modelData; Layout.fillWidth: true; onClicked: prompt.respond("answered", modelData) }
        }
        TextField { id: answer; objectName: "interactionAnswer"; visible: prompt.request && prompt.request.kind === "question"; placeholderText: I18n.t("native.message22"); Layout.fillWidth: true }
        RowLayout {
            Button { objectName: "interactionAccept"; text: prompt.request && prompt.request.kind === "mount" ? "选择文件夹" : prompt.request && prompt.request.kind === "approval" ? I18n.t("native.message18") : I18n.t("native.submit"); onClicked: { if(prompt.request.kind==="mount")memberFolder.open();else prompt.respond(prompt.request.kind === "approval" ? "approved" : "answered", answer.text) } }
            Button { objectName: "interactionReject"; text: prompt.request && prompt.request.kind === "approval" ? I18n.t("cf.reject") : I18n.t("cf.close"); onClicked: prompt.respond(prompt.request.kind === "approval" ? "denied" : "dismissed", "") }
        }
    }
}
