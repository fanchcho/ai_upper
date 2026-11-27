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
    property var remotes: []
    property string remoteName: ""
    property string remoteUrl: ""
    readonly property string branchesText: (branches || []).map(function (b) { return b.name + (b.current ? "*" : "") }).join("  ")
    property string message: ""
    property string diffText: ""
    property string branchName: ""
    property string notice: ""
    width: 480; height: 650; padding: 12
    modal: false
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: reload()

    function reload() {
        if (!repoRoot) return
        status = shellBridge.gitStatus(repoRoot)
        branches = shellBridge.gitBranches(repoRoot).branches || []
        commits = shellBridge.gitLog(repoRoot, 8).commits || []
        remotes = shellBridge.gitRemotes(repoRoot).remotes || []
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
    function showDiff(entry) {
        var result = shellBridge.gitDiffEx(repoRoot, entry.path, entry.staged === true, entry.untracked === true)
        diffText = result.text || result.error || ""
    }
    function discardAll() {
        var entries = status.entries || []
        var tracked = [], untracked = []
        for (var i = 0; i < entries.length; i++) (entries[i].untracked ? untracked : tracked).push(entries[i].path)
        var result = shellBridge.gitDiscard(repoRoot, tracked, untracked)
        if (result.ok) reload(); else notice = result.error || "丢弃失败"
    }
    function runRemote(action) {
        var result = action === "fetch" ? shellBridge.gitFetch(repoRoot)
                   : action === "pull" ? shellBridge.gitPull(repoRoot)
                   : shellBridge.gitPush(repoRoot, status.upstream ? "" : status.branch)
        if (result.ok) reload(); else notice = result.error || "远程操作失败"
    }

    Column {
        width: parent.width
        spacing: 8
        Row {
            width: parent.width
            Text { text: "Git · " + ((root.status.branch || "") || "detached"); color: Theme.fg; font.pixelSize: 18; font.weight: 700; width: parent.width - 60 }
            SettingsButton { objectName: "gitRefresh"; text: "刷新"; onClicked: root.reload() }
        }
        Text { text: "分支：" + root.branchesText; color: Theme.fgMuted; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
        Rectangle {
            width: parent.width; height: 180; color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
            ListView {
                anchors.fill: parent; anchors.margins: 8; clip: true
                model: root.status.entries || []
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width; height: 24; color: "transparent"
                    Text { x: 4; anchors.verticalCenter: parent.verticalCenter; text: modelData.index + modelData.worktree + "  " + modelData.path; color: Theme.fg; font.pixelSize: 12 }
                    MouseArea { anchors.fill: parent; onClicked: root.showDiff(modelData) }
                }
            }
        }
        Row {
            width: parent.width; spacing: 8
            SettingsButton { objectName: "gitStageAll"; text: "全部暂存"; onClicked: root.stageAll() }
            SettingsButton { objectName: "gitDiscardAll"; text: "丢弃全部"; destructive: true; onClicked: root.discardAll() }
            SettingsButton { objectName: "gitFetch"; text: "Fetch"; onClicked: root.runRemote("fetch") }
            SettingsButton { objectName: "gitPull"; text: "Pull"; onClicked: root.runRemote("pull") }
            SettingsButton { objectName: "gitPush"; text: "Push"; onClicked: root.runRemote("push") }
        }
        TextField {
            id: commitMessage; objectName: "gitCommitMessage"; width: parent.width
            placeholderText: "提交说明"; text: root.message
            onTextChanged: root.message = text
            color: Theme.fg; font.pixelSize: 12
            background: Rectangle { color: Theme.bgPanel; border.color: Theme.border; radius: Theme.radiusSm }
        }
        Row {
            width: parent.width; spacing: 8
            TextField { id: branchName; objectName: "gitBranchName"; width: 140; placeholderText: "分支名"; text: root.branchName; onTextChanged: root.branchName = text; color: Theme.fg; font.pixelSize: 12 }
            SettingsButton { objectName: "gitCreateBranch"; text: "新建分支"; onClicked: { var r = shellBridge.gitCreateBranch(repoRoot, root.branchName); if (r.ok) { root.branchName = ""; root.reload() } else root.notice = r.error } }
            SettingsButton { objectName: "gitMerge"; text: "合并"; onClicked: { var r = shellBridge.gitMerge(repoRoot, root.branchName); if (r.ok) root.reload(); else root.notice = r.error } }
        }
        TextArea { objectName: "gitDiffText"; width: parent.width; height: 80; readOnly: true; text: root.diffText; color: Theme.fg; font.pixelSize: 11; wrapMode: TextArea.NoWrap; background: Rectangle { color: Theme.bgPanel } }
        Text { text: "最近提交：" + ((root.commits || []).slice(0, 3).join(" · ")); color: Theme.fgMuted; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
        Text { text: "远程：" + ((root.remotes || []).join(", ") || "无"); color: Theme.fgMuted; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
        Row {
            width: parent.width; spacing: 6
            TextField { id: remoteName; objectName: "gitRemoteName"; width: 100; placeholderText: "remote 名"; text: root.remoteName; onTextChanged: root.remoteName = text; color: Theme.fg; font.pixelSize: 12 }
            TextField { id: remoteUrl; objectName: "gitRemoteUrl"; width: 180; placeholderText: "URL"; text: root.remoteUrl; onTextChanged: root.remoteUrl = text; color: Theme.fg; font.pixelSize: 12 }
            SettingsButton { objectName: "gitAddRemote"; text: "添加"; onClicked: { var r = shellBridge.gitAddRemote(repoRoot, root.remoteName, root.remoteUrl); if (r.ok) { root.remoteName = ""; root.remoteUrl = ""; root.reload() } else root.notice = r.error } }
            SettingsButton { objectName: "gitRemoveRemote"; text: "删除"; onClicked: { var r = shellBridge.gitRemoveRemote(repoRoot, root.remoteName); if (r.ok) root.reload(); else root.notice = r.error } }
        }
        Text { text: root.notice; color: Theme.danger; font.pixelSize: 12; visible: text.length > 0 }
    }
}
