// Git 面板最小子集：状态/暂存/提交/分支/日志（原版 GitWidget.tsx 的常用操作）。
import QtQuick
import QtQuick.Controls
import "."

Popup {
    id: root
    objectName: "gitPanel"
    property string repoRoot: ""
    property var status: ({})
    property var branches: []
    property var commits: []
    property string message: ""
    width: 440; height: 420; padding: 12
    modal: false
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: reload()

    function reload() {
        if (!repoRoot) return
        status = shellBridge.gitStatus(repoRoot)
        branches = shellBridge.gitBranches(repoRoot).branches || []
        commits = shellBridge.gitLog(repoRoot, 8).commits || []
    }
    function stageAll() {
        var entries = status.entries || []
        var paths = entries.map(function (e) { return e.path })
        if (paths.length) { shellBridge.gitStage(repoRoot, paths); reload() }
    }
    function commit() {
        var result = shellBridge.gitCommit(repoRoot, message)
        if (result.ok) { message = ""; reload() }
        else root.notice = result.error || "提交失败"
    }
    property string notice: ""

    Column {
        width: parent.width
        spacing: 8
        Row {
            width: parent.width
            Text { text: "Git · " + ((root.status.branch || "") || "detached"); color: Theme.fg; font.pixelSize: 18; font.weight: 700; width: parent.width - 60 }
            SettingsButton { objectName: "gitRefresh"; text: "刷新"; onClicked: root.reload() }
        }
        Text { text: "分支：" + ((root.branches || []).join("  ")); color: Theme.fgMuted; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
        Rectangle {
            width: parent.width; height: 180; color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
            ListView {
                anchors.fill: parent; anchors.margins: 8; clip: true
                model: root.status.entries || []
                delegate: Text {
                    required property var modelData
                    text: modelData.index + modelData.worktree + "  " + modelData.path
                    color: Theme.fg; font.pixelSize: 12; height: 22
                }
            }
        }
        Row {
            width: parent.width; spacing: 8
            SettingsButton { objectName: "gitStageAll"; text: "全部暂存"; onClicked: root.stageAll() }
            SettingsButton { objectName: "gitCommit"; text: "提交"; onClicked: root.commit() }
        }
        TextField {
            id: commitMessage; objectName: "gitCommitMessage"; width: parent.width
            placeholderText: "提交说明"; text: root.message
            onTextChanged: root.message = text
            color: Theme.fg; font.pixelSize: 12
            background: Rectangle { color: Theme.bgPanel; border.color: Theme.border; radius: Theme.radiusSm }
        }
        Text { text: "最近提交：" + ((root.commits || []).slice(0, 3).join(" · ")); color: Theme.fgMuted; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
        Text { text: root.notice; color: Theme.danger; font.pixelSize: 12; visible: text.length > 0 }
    }
}
