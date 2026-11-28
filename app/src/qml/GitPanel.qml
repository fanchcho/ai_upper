// Git 面板最小子集：状态/暂存/提交/分支/日志（原版 GitWidget.tsx 的常用操作）。
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
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
    property bool remoteSucceeded: false
    onNoticeChanged: remoteSucceeded = false
    property string genReq: ""
    property bool generating: false
    width: 480; height: 760; padding: 12
    modal: false
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: reload()
    Connections {
        target: shellBridge
        function onCommitMessageGenerated(requestId, result) {
            if (requestId !== root.genReq) return
            root.generating = false
            if (result.ok) root.message = result.text
            else root.notice = (result.reason || "unverified") + ": " + (result.message || "")
        }
    }

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
        notice = result.ok ? action.charAt(0).toUpperCase() + action.slice(1) + " 完成" : result.error || "远程操作失败"
        remoteSucceeded = result.ok === true
        if (result.ok) reload()
    }

    Column {
        width: parent.width
        spacing: 8
        RowLayout {
            width: parent.width
            Text { text: "Git · " + ((root.status.branch || "") || "detached"); color: Theme.fg; font.pixelSize: 18; font.weight: 700; Layout.fillWidth: true }
            SettingsButton { implicitHeight: 34; objectName: "gitRefresh"; text: "刷新"; onClicked: root.reload() }
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
            SettingsButton { implicitHeight: 34; objectName: "gitStageAll"; text: "全部暂存"; onClicked: root.stageAll() }
            SettingsButton { implicitHeight: 34; objectName: "gitDiscardAll"; text: "丢弃全部"; destructive: true; onClicked: root.discardAll() }
            SettingsButton { implicitHeight: 34; objectName: "gitFetch"; text: "Fetch"; onClicked: root.runRemote("fetch") }
            SettingsButton { implicitHeight: 34; objectName: "gitPull"; text: "Pull"; onClicked: root.runRemote("pull") }
            SettingsButton { implicitHeight: 34; objectName: "gitPush"; text: "Push"; onClicked: root.runRemote("push") }
        }
        RowLayout {
            width: parent.width; spacing: 6
            SettingsField { id: gitName; objectName: "gitIdentityName"; Layout.fillWidth: true; Layout.preferredWidth: 120; Layout.minimumWidth: 48; Layout.preferredHeight: 34; placeholderText: "user.name"; color: Theme.fg; font.pixelSize: 12 }
            SettingsField { id: gitEmail; objectName: "gitIdentityEmail"; Layout.fillWidth: true; Layout.preferredWidth: 180; Layout.minimumWidth: 48; Layout.preferredHeight: 34; placeholderText: "user.email"; color: Theme.fg; font.pixelSize: 12 }
            SettingsButton { implicitHeight: 34; objectName: "gitSetConfig"; primary: true; text: "保存身份"; onClicked: { var r = shellBridge.gitSetConfig(repoRoot, gitName.text, gitEmail.text, false); if (!r.ok) root.notice = r.message || r.reason } }
        }
        Row {
            width: parent.width; spacing: 6
            SettingsButton { implicitHeight: 34; objectName: "gitGenerateMessage"; ghost: true; text: root.generating ? "生成中…" : "AI 提交信息"; enabled: !root.generating; onClicked: { root.genReq = "git-" + Date.now(); root.generating = true; root.notice = ""; if (!shellBridge.generateCommitMessage(repoRoot, root.genReq)) { root.generating = false; root.notice = "无法启动生成" } } }
            SettingsButton { implicitHeight: 34; objectName: "gitCancelMessage"; ghost: true; text: "取消生成"; enabled: root.generating; onClicked: shellBridge.cancelCommitMessage(root.genReq) }
        }
        SettingsField {
            id: commitMessage; objectName: "gitCommitMessage"; width: parent.width; height: 34
            placeholderText: "提交说明"; text: root.message
            onTextChanged: root.message = text
            color: Theme.fg; font.pixelSize: 12
        }
        RowLayout {
            width: parent.width; spacing: 8
            SettingsField { id: branchName; objectName: "gitBranchName"; Layout.fillWidth: true; Layout.preferredWidth: 140; Layout.minimumWidth: 48; Layout.preferredHeight: 34; placeholderText: "分支名"; text: root.branchName; onTextChanged: root.branchName = text; color: Theme.fg; font.pixelSize: 12 }
            SettingsButton { implicitHeight: 34; objectName: "gitCheckoutBranch"; text: "切换分支"; onClicked: { var r = shellBridge.gitCheckout(repoRoot, root.branchName); if (r.ok) root.reload(); else root.notice = r.error || r.reason } }
            SettingsButton { implicitHeight: 34; objectName: "gitCreateBranch"; primary: true; text: "新建分支"; onClicked: { var r = shellBridge.gitCreateBranch(repoRoot, root.branchName); if (r.ok) { root.branchName = ""; root.reload() } else root.notice = r.error } }
            SettingsButton { implicitHeight: 34; objectName: "gitMerge"; text: "合并"; onClicked: { var r = shellBridge.gitMerge(repoRoot, root.branchName); if (r.ok) root.reload(); else root.notice = r.error } }
        }
        TextArea { objectName: "gitDiffText"; width: parent.width; height: 80; readOnly: true; text: root.diffText; color: Theme.fg; font.pixelSize: 11; wrapMode: TextArea.NoWrap; background: Rectangle { color: Theme.bgPanel } }
        Text {
            objectName: "gitRecentCommits"
            text: "最近提交：" + (root.commits.length ? root.commits.slice(0, 3).map(function (entry) {
                return entry.short + " · " + entry.subject
            }).join("\n") : "暂无提交")
            color: Theme.fgMuted; font.pixelSize: 12; width: parent.width; wrapMode: Text.Wrap
        }
        Text { text: "远程：" + ((root.remotes || []).join(", ") || "无"); color: Theme.fgMuted; font.pixelSize: 12; width: parent.width; elide: Text.ElideRight }
        RowLayout {
            width: parent.width; spacing: 6
            SettingsField { id: remoteName; objectName: "gitRemoteName"; Layout.fillWidth: true; Layout.preferredWidth: 100; Layout.minimumWidth: 48; Layout.preferredHeight: 34; placeholderText: "remote 名"; text: root.remoteName; onTextChanged: root.remoteName = text; color: Theme.fg; font.pixelSize: 12 }
            SettingsField { id: remoteUrl; objectName: "gitRemoteUrl"; Layout.fillWidth: true; Layout.preferredWidth: 180; Layout.minimumWidth: 48; Layout.preferredHeight: 34; placeholderText: "URL"; text: root.remoteUrl; onTextChanged: root.remoteUrl = text; color: Theme.fg; font.pixelSize: 12 }
            SettingsButton { implicitHeight: 34; objectName: "gitAddRemote"; primary: true; text: "添加"; onClicked: { var r = shellBridge.gitAddRemote(repoRoot, root.remoteName, root.remoteUrl); if (r.ok) { root.remoteName = ""; root.remoteUrl = ""; root.reload() } else root.notice = r.error } }
            SettingsButton { implicitHeight: 34; objectName: "gitRemoveRemote"; destructive: true; text: "删除"; onClicked: { var r = shellBridge.gitRemoveRemote(repoRoot, root.remoteName); if (r.ok) root.reload(); else root.notice = r.error } }
        }
        Text { objectName: "gitNotice"; text: root.notice; color: root.remoteSucceeded ? Theme.success : Theme.danger; width: parent.width; wrapMode: Text.Wrap; font.pixelSize: 12; visible: text.length > 0 }
    }
}
