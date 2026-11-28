import QtQuick
import QtQuick.Controls.Basic
import "."
Rectangle {
 id: root
 property var bot: null
 property var api: null
 property string mode: "all"
 property var picked: []
 property var choices: []
 property string error: ""
 signal back()
 signal action(string action,string value)
 color: Theme.bg
 onBotChanged: if (bot) load(bot.scope.mode)
 function load(kind) { mode=kind; picked=bot && bot.scope[kind] ? bot.scope[kind].slice() : []; choices=api && kind!=="all" ? api.scopeChoices(kind) : [] }
 Column {
  anchors.fill: parent; spacing: 12
  Row { spacing:12
   SettingsButton { objectName:"detailBack"; text:"返回机器人列表"; onClicked:root.back() }
   Text { text:root.bot ? root.bot.name+" · "+root.bot.platform : ""; color:Theme.fg; font.pixelSize:22 }
  }
  Text { text:root.bot ? root.bot.state : ""; color:Theme.fgMuted }
  Row { spacing:10
   SettingsButton { objectName:"detailToggle"; text:root.bot && root.bot.enabled ? "停用":"启用"; onClicked:root.action(root.bot.enabled?"disable":"enable","") }
   SettingsButton { objectName:"detailReply"; text:root.bot && root.bot.replyMode==="final"?"仅最终回复":"流式回复"; onClicked:root.action("reply",root.bot.replyMode==="final"?"stream":"final") }
   SettingsButton { objectName:"detailDelete"; text:"删除机器人"; onClicked:root.action("delete","") }
  }
  Text { text:"接收范围（选择后保存）"; color:Theme.fg }
  Row { spacing:8
   Repeater { model:[{id:"all",label:"全部"},{id:"personas",label:"角色"},{id:"sessions",label:"会话"}]
    SettingsButton { required property var modelData; objectName:"scopeMode_"+modelData.id; text:modelData.label; onClicked:root.load(modelData.id) }
   }
  }
  ListView {
   width:parent.width; height:200; clip:true; model:root.choices
   ScrollBar.vertical:SettingsScrollBar {}
   delegate:CheckBox { palette.windowText: Theme.fg; required property var modelData; objectName:"scopeChoice_"+modelData.id; text:modelData.title; checked:root.picked.indexOf(modelData.id)>=0
    onClicked: { var next=root.picked.slice();var at=next.indexOf(modelData.id);if(at>=0)next.splice(at,1);else next.push(modelData.id);root.picked=next }
   }
  }
  SettingsButton { objectName:"scopeSave"; text:"保存范围"; onClicked:{var s=JSON.parse(JSON.stringify(root.bot.scope));s.mode=root.mode;if(root.mode!=="all")s[root.mode]=root.picked;root.action("scope",JSON.stringify(s))} }
  Row { spacing:8; visible:root.bot && root.bot.platform==="feishu"
   SettingsButton { objectName:"detailInvite"; text:"生成/刷新邀请"; onClicked:root.error=root.api.feishuPairCode(root.bot.id) }
   SettingsButton { objectName:"detailCancelInvite"; text:"取消邀请"; onClicked:{root.api.cancelPair(root.bot.id);root.error="邀请已取消"} }
  }
  Text { text:root.error; color:Theme.fg; wrapMode:Text.Wrap; width:parent.width }
  Repeater { model:root.bot ? root.bot.users : []
   SettingsButton { required property var modelData; text:"移除用户 "+(modelData.name || modelData.id); onClicked:root.action("remove-user",modelData.id) }
  }
 }
}
