// Deva 0.1.17 GitWidget.tsx:377-440, 490-510: menu drill-down and commit modal.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "."
Popup {
 id: root
 component GitActionButton: SettingsButton {
  implicitHeight:30
  implicitWidth:contentItem.implicitWidth+26
  leftPadding:12;rightPadding:12;topPadding:0;bottomPadding:0
  font.weight:Font.Medium
 }
 objectName: "gitMenu"
 property string repoRoot: ""
 property var status: ({})
 property var branches: []
 property string view: "main"
 property var selected: ({})
 property string notice: ""
 property string requestId: ""
 property bool generating: false
 property bool identityNeeded: false
 property string promptAction: ""
 property string filter: ""
 property int unmergedCount: 0
 property var conflictFiles: []
 width: view === "main" ? 148 : 300; padding: 6
 height: Math.min(menuColumn.implicitHeight + 12, parent.height - 16)
 background: Item {
  SoftShadow { target: menuSurface }
  Rectangle { id:menuSurface; anchors.fill:parent; color:Theme.bgElevated; border.color:Theme.border; radius:Theme.radiusLg }
 }
 onRepoRootChanged: if (repoRoot) reload()
 onOpened: { view = "main"; filter = ""; reload() }
 function reload() { status = shellBridge.gitStatus(repoRoot); branches = shellBridge.gitBranches(repoRoot).branches || [] }
 function result(r, success) { notice = r.ok ? success : (r.error || r.message || r.reason || "操作失败"); reload(); return r.ok }
 function remote(action) { result(action === "fetch" ? shellBridge.gitFetch(repoRoot) : action === "pull" ? shellBridge.gitPull(repoRoot) : shellBridge.gitPush(repoRoot, status.upstream ? "" : status.branch), action === "fetch" ? "已获取远端更新" : action === "pull" ? "已拉取" : "已推送") }
 function prompt(action) { root.close(); notice = ""; promptAction = action; nameField.text = action === "rename" ? selected.name : ""; promptDialog.open() }
 function submit() {
  reload()
  var entries = status.entries || []
  if (entries.some(function(e) { return e.index === "U" || e.worktree === "U" || e.index + e.worktree === "AA" || e.index + e.worktree === "DD" })) { notice = "存在未解决的冲突，请先解决后再提交"; return }
  var paths = entries.map(function(e) { return e.path })
  if (paths.length && !result(shellBridge.gitStage(repoRoot, paths), "已暂存")) return
  var r = shellBridge.gitCommit(repoRoot, commitText.text.trim())
  if (result(r, "已提交")) commitDialog.close()
  else identityNeeded = /identity|user.email|user.name|who you are|auto-detect/i.test(notice)
 }
 function glyph(action) {
  if(action === "pull")return "M12 3v12|M7 10l5 5 5-5|M5 17v4h14v-4"
  if(action === "push")return "M12 17V5|M7 10l5-5 5 5|M5 17v4h14v-4"
  if(action === "fetch")return "M12 3v12|M7 10l5 5 5-5|M5 21h14"
  if(action === "commit")return "M3 12h5|M16 12h5|M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0"
  if(action === "branches")return "M6 3v12|M18 6v3a6 6 0 0 1-6 6H6|M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0|M21 3a3 3 0 1 1-6 0 3 3 0 0 1 6 0"
  if(action === "refresh")return IconData.refreshCw
  return ""
 }
 function rows() {
  if(view === "main") return (status.mergeInProgress ? [{label:"中止合并",action:"abort",danger:true},{sep:true}] : []).concat([{label:"拉取",action:"pull"},{label:"推送",action:"push"},{label:"获取远端更新",action:"fetch"},{label:"提交",action:"commit"},{sep:true},{label:"分支",action:"branches"},{label:"刷新",action:"refresh"}])
  if(view === "branch") return [{label:selected.name,section:true},{label:"切换分支",action:"checkout",disabled:selected.current},{label:"重命名分支…",action:"rename",hidden:!!selected.remote},{sep:true},{label:selected.remote ? "删除远程分支…" : "删除分支…",action:"delete",danger:true,disabled:selected.current}].filter(function(r){return !r.hidden})
  var list = view === "branches" ? [{label:"新建分支…",action:"create"},{label:"合并分支…",action:"merge"}] : []
  for(var group=0;group<2;group++) {
   var subset=branches.filter(function(b){return !!b.remote === !!group && (view !== "merge" || !b.current) && (!filter || b.name.toLowerCase().indexOf(filter.toLowerCase())>=0)})
   if(subset.length)list.push({label:group?"远程分支":"本地分支",section:true})
   subset.forEach(function(b){
    var tracking = b.upstream ? "  → " + b.upstream + (b.ahead !== null && b.ahead !== undefined ? "  ↑" + b.ahead + " ↓" + b.behind : "  状态未知") : ""
    list.push({label:(b.current?"✓  ":"")+b.name+tracking,action:"branch",branch:b})
   })
  }
  if(!list.some(function(r){return r.branch}))list.push({label:branches.length?"无匹配分支":"暂无分支",section:true,empty:true})
  return list
 }
 function act(row) {
  var a=row.action
  if(a==="fetch"||a==="pull"||a==="push")remote(a)
  else if(a==="refresh") {reload();notice="已刷新"}
  else if(a==="commit") {root.close();notice="";identityNeeded=false;commitDialog.open()}
  else if(a==="branches"||a==="merge") {view=a;filter=""}
  else if(a==="branch") {selected=row.branch;if(view==="merge")prompt("merge");else view="branch"}
  else if(a==="checkout") {result(selected.remote?shellBridge.gitCheckoutRemote(repoRoot,selected.name):shellBridge.gitCheckout(repoRoot,selected.name),"已切换分支")}
  else prompt(a)
 }
 contentItem: Flickable {
  objectName: "gitBranchScroll"
  clip:true; contentWidth:width;contentHeight:menuColumn.implicitHeight
  boundsBehavior:Flickable.StopAtBounds
  ScrollBar.vertical: ScrollBar {}
  Column {
   id:menuColumn; width:root.availableWidth; spacing:0
   SettingsField { objectName:"gitBranchFilter"; width:parent.width; visible:root.view!=="main" && root.branches.length>8; placeholderText:"筛选分支"; onTextChanged:root.filter=text }
   Repeater {
    model:root.rows()
    delegate: Item {
     required property var modelData
     width:menuColumn.width; height:modelData.sep?9:modelData.section?26:33
     Rectangle { visible:!!modelData.sep; x:6;y:4;width:parent.width-12;height:1;color:Theme.border }
     Text { objectName:modelData.empty?"gitBranchEmpty":"gitBranchSection"; visible:!!modelData.section; x:9;y:6;text:modelData.label||"";color:Theme.fgSubtle;font.pixelSize:11 }
     Button {
      objectName:"gitMenu_"+(modelData.action||"section")+(modelData.branch?"_"+modelData.branch.name:"")
      anchors.fill:parent; visible:!modelData.sep&&!modelData.section;enabled:!modelData.disabled;opacity:enabled?1:.4
      contentItem:Text { text:modelData.label||"";color:modelData.danger?Theme.danger:Theme.fg;font.family:Theme.sansFamily;font.pixelSize:13;leftPadding:modelData.branch?9:31;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight }
      Icon { x:9;anchors.verticalCenter:parent.verticalCenter;size:14;name:root.glyph(modelData.action);color:modelData.danger?Theme.danger:Theme.fg;visible:name.length>0 }
      ToolTip.visible:hovered
      ToolTip.text:modelData.label||""
      background:Rectangle {radius:Theme.radius;color:parent.hovered?(modelData.danger?Qt.rgba(Theme.danger.r,Theme.danger.g,Theme.danger.b,0.14):Theme.bgHover):"transparent"}
      onClicked:root.act(modelData)
     }
    }
   }
   Text { objectName:"gitMenuNotice";width:parent.width;visible:text.length>0;text:root.notice;color:Theme.fgMuted;font.pixelSize:12;wrapMode:Text.Wrap }
  }
 }
 Popup {
  id:commitDialog;objectName:"gitCommitDialog";parent:Overlay.overlay
  x:(parent.width-width)/2;y:(parent.height-height)/2;width:460;padding:21;height:commitColumn.implicitHeight+42;modal:true
  Overlay.modal:Rectangle { color:Qt.rgba(0,0,0,0.42) }
  onClosed:if(root.generating){shellBridge.cancelCommitMessage(root.requestId);root.generating=false}
  background:Item {
   SoftShadow { target: commitSurface }
   Rectangle { id:commitSurface;anchors.fill:parent;color:Theme.bgElevated;border.color:Theme.border;radius:Theme.radiusLg }
  }
  ColumnLayout {
   id:commitColumn;width:parent.width;spacing:12
   Text {objectName:"gitCommitTitle";text:"提交更改";font.family:Theme.sansFamily;font.pixelSize:15;font.weight:Font.DemiBold;color:Theme.fg}
   Text {Layout.topMargin:4;Layout.bottomMargin:10;text:(root.status.entries||[]).length?"将暂存并提交 "+root.status.entries.length+" 项更改":"没有可提交的更改";font.pixelSize:12;color:Theme.fgMuted}
   TextArea {id:commitText;objectName:"gitNewCommitMessage";Layout.fillWidth:true;Layout.preferredHeight:120;readOnly:root.generating;placeholderText:"填写提交信息…";placeholderTextColor:Theme.fgMuted;color:Theme.fg;font.family:Theme.sansFamily;font.pixelSize:13;wrapMode:TextEdit.Wrap;leftPadding:12;rightPadding:12;topPadding:0;bottomPadding:0;background:Rectangle{color:Theme.bgElevated;border.color:commitText.activeFocus?Theme.accent:Theme.borderStrong;radius:Theme.radiusSm}}
   ColumnLayout {
    visible:root.identityNeeded;Layout.fillWidth:true
    Text {text:"配置 Git 提交身份";color:Theme.fg}
    SettingsField {id:name;objectName:"gitNewIdentityName";placeholderText:"user.name";Layout.fillWidth:true}
    SettingsField {id:email;objectName:"gitNewIdentityEmail";placeholderText:"user.email";Layout.fillWidth:true}
    Text {text:"作用范围";color:Theme.fg}
    ComboBox {id:globalScope;objectName:"gitIdentityScope";Layout.fillWidth:true;implicitHeight:32;model:["当前仓库","全局（所有仓库）"];font.pixelSize:13;palette.text:Theme.fg;palette.buttonText:Theme.fg;palette.base:Theme.bgElevated;palette.button:Theme.bgElevated;background:Rectangle{color:Theme.bgElevated;border.color:Theme.borderStrong;radius:Theme.radiusSm}}
    SettingsButton {objectName:"gitIdentitySave";text:"保存并验证";primary:true;enabled:name.text.trim().length>0&&email.text.trim().length>0;onClicked:if(root.result(shellBridge.gitSetConfig(root.repoRoot,name.text,email.text,globalScope.currentIndex===1),"身份已保存并验证，请重试提交"))root.identityNeeded=false}
   }
   Text {Layout.fillWidth:true;text:root.notice;color:Theme.fgMuted;wrapMode:Text.Wrap;visible:text.length>0}
   RowLayout {
    Layout.fillWidth:true;Layout.topMargin:12;spacing:8
    GitActionButton {objectName:"gitNewGenerate";text:root.generating?"停止生成":"AI 生成";ghost:true;onClicked:{if(root.generating){shellBridge.cancelCommitMessage(root.requestId);root.generating=false}else{root.requestId="git-menu-"+Date.now();root.generating=shellBridge.generateCommitMessage(root.repoRoot,root.requestId)}}}
    Item {Layout.fillWidth:true}
    GitActionButton {text:"取消";ghost:true;onClicked:commitDialog.close()}
    GitActionButton {objectName:"gitNewSubmit";text:"提交";primary:true;enabled:!root.generating&&commitText.text.trim().length>0&&(root.status.entries||[]).length>0;onClicked:root.submit()}
   }
  }
 }
 Connections {target:shellBridge;function onCommitMessageGenerated(id,result){if(id!==root.requestId)return;root.generating=false;if(result.ok)commitText.text=result.text;else root.notice=(result.reason||"")+": "+(result.message||"")}}
 Popup {
  id:conflictToast;objectName:"gitConflictToast";parent:Overlay.overlay
  width:Math.min(360,parent.width-32);x:parent.width-width-16;y:40;padding:14;height:conflictColumn.implicitHeight+28
  closePolicy:Popup.NoAutoClose
  background:Rectangle {color:Theme.bgElevated;border.color:Theme.warning;radius:Theme.radiusLg}
  ColumnLayout {id:conflictColumn;width:parent.width;spacing:8
   Text {text:"合并产生冲突";color:Theme.fg;font.bold:true}
   Text {objectName:"gitConflictFiles";text:"解决冲突文件后提交，或中止合并。\n"+root.conflictFiles.join("\n");Layout.fillWidth:true;wrapMode:Text.Wrap;color:Theme.fgMuted}
   SettingsButton {objectName:"gitConflictAbort";text:"中止合并";onClicked:if(root.result(shellBridge.gitMergeAbort(root.repoRoot),"已中止合并"))conflictToast.close()}
  }
 }
 Popup {
  id:promptDialog;objectName:"gitBranchPrompt";parent:Overlay.overlay;modal:true;width:420;padding:20;height:promptColumn.implicitHeight+40;x:(parent.width-width)/2;y:(parent.height-height)/2
  background:Rectangle{color:Theme.bgElevated;border.color:Theme.border;radius:Theme.radiusLg}
  ColumnLayout {
   id:promptColumn;width:parent.width;spacing:12
   Text {text:root.promptAction==="forceDelete"?"分支尚未合并":root.promptAction==="abort"?"中止合并？":root.promptAction==="create"?"新建分支":root.promptAction==="rename"?"重命名分支":root.promptAction==="merge"?"合并分支 "+root.selected.name:"删除分支 "+root.selected.name+"？";color:Theme.fg;font.pixelSize:16}
   SettingsField{id:nameField;objectName:"gitNewBranchName";Layout.fillWidth:true;visible:root.promptAction==="create"||root.promptAction==="rename";placeholderText:"分支名称"}
   Text {objectName:"gitDeleteWarning";visible:root.promptAction==="delete"||root.promptAction==="forceDelete";text:root.promptAction==="forceDelete"?"分支 "+root.selected.name+" 有 "+root.unmergedCount+" 个提交未合并到当前分支，强制删除后这些提交将难以找回。":root.selected.remote?"将从远程仓库删除该分支，会影响所有协作者。":"只删除本地分支，不影响远程。";color:Theme.fgMuted;Layout.fillWidth:true;wrapMode:Text.Wrap}
   Text {objectName:"gitPromptError";Layout.fillWidth:true;visible:root.notice.length>0;text:root.notice;color:Theme.danger;wrapMode:Text.Wrap}
   RowLayout {
    SettingsButton{objectName:"gitBranchCancel";text:"取消";ghost:true;onClicked:promptDialog.close()}
    SettingsButton{objectName:"gitBranchConfirm";text:root.promptAction==="forceDelete"?"强制删除":root.promptAction==="delete"?"删除":"确认";primary:root.promptAction!=="delete"&&root.promptAction!=="forceDelete";destructive:root.promptAction==="delete"||root.promptAction==="forceDelete";onClicked:{var r;var a=root.promptAction;if(a==="abort")r=shellBridge.gitMergeAbort(root.repoRoot);else if(a==="create")r=shellBridge.gitCreateBranch(root.repoRoot,nameField.text);else if(a==="rename")r=shellBridge.gitRenameBranch(root.repoRoot,root.selected.name,nameField.text);else if(a==="merge")r=shellBridge.gitMerge(root.repoRoot,root.selected.name);else r=root.selected.remote?shellBridge.gitDeleteRemoteBranch(root.repoRoot,root.selected.remote,root.selected.name.slice(root.selected.remote.length+1)):shellBridge.gitDeleteBranch(root.repoRoot,root.selected.name,a==="forceDelete");if(!r.ok&&r.reason==="conflict"&&a==="merge"){root.conflictFiles=r.conflicts||[];promptDialog.close();conflictToast.open();root.reload();return}if(!r.ok&&r.reason==="unmerged"&&a==="delete"){root.unmergedCount=r.count;root.promptAction="forceDelete";return}if(root.result(r,"操作完成")){promptDialog.close();root.view="branches"}}}
   }
  }
 }
}
