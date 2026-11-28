import QtQuick
import QtQuick.Controls.Basic
import "."
Rectangle {
 id:root
 required property var shell
 property var api:null
 property var state:({devices:[],links:{lan:"off",relay:"off"}})
 property var ticket:({})
 property string via:"lan"
 property string error:""
 color:Theme.bg
 function refresh(){if(api){var next=api.phoneState();if(next.devices.length>state.devices.length){ticket={paired:true};error=""}state=next}}
 function issue(kind){ticket=api.phoneTicket(via,kind);error=ticket.error || "";refresh()}
 function revoke(id){error=api.action(state.id,"remove-user",id);refresh()}
 onVisibleChanged: if(visible){api=shellBridge.botsService();refresh()}else if(api){api.cancelPhoneQr();ticket={}}
 Connections { target:root.api;function onChanged(){root.refresh()} }
 Timer { interval:1000;repeat:true;running:root.visible && !!root.ticket.expiresAt
  onTriggered:if(Date.now()>root.ticket.expiresAt)root.issue("pair")
 }
 Column { anchors.fill:parent;anchors.margins:24;spacing:14
  Row { spacing:18
   SettingsButton { objectName:"phoneBack";text:"返回";onClicked:root.shell.page="bots" }
   Text { text:"手机联动";font.pixelSize:22;color:Theme.fg }
  }
  Row { spacing:10
   SettingsButton { objectName:"phoneLan";text:"局域网";onClicked:{root.via="lan";root.issue("pair")} }
   SettingsButton { objectName:"phoneRelay";text:"中转";onClicked:{root.via="relay";root.issue("pair")} }
   SettingsButton { objectName:"phoneLink";text:"复制一次性链接（10 分钟）";onClicked:{root.issue("link");if(root.ticket.url)root.api.copyLink(root.ticket.url)} }
   SettingsButton { objectName:"phoneCancel";text:"取消二维码";onClicked:{root.api.cancelPhoneQr();root.ticket={}} }
   SettingsButton { objectName:"phoneDisable";visible:!!root.state.added;text:root.state.enabled?"停用":"启用";onClicked:{root.error=root.api.action(root.state.id,root.state.enabled?"disable":"enable","");root.ticket={};root.refresh()} }
   SettingsButton { objectName:"phoneRemove";visible:!!root.state.added;text:"移除手机联动";onClicked:{root.error=root.api.action(root.state.id,"delete","");root.ticket={};root.refresh()} }
  }
  Text { text:"LAN："+root.state.links.lan+"   Relay："+root.state.links.relay;color:Theme.fg;wrapMode:Text.Wrap;width:parent.width }
  Text { visible:!!root.error;text:root.error;color:Theme.danger;wrapMode:Text.Wrap;width:parent.width }
  Row { spacing:20
   Image { objectName:"phoneQr";source:root.ticket.qr || "";width:280;height:280;smooth:false }
   Column { width:450;spacing:12
    Text { text:root.ticket.paired?"设备已配对":root.ticket.url?"用手机扫描二维码（2 分钟、一次有效）":"选择连接方式生成二维码";color:Theme.fg }
    Text { text:"局域网需要同一网络。中转传输端到端加密。浏览器订阅与外部推送送达分别验证。";color:Theme.fgMuted;wrapMode:Text.Wrap;width:parent.width }
    SettingsButton { objectName:"phoneOpen";visible:!!root.ticket.url;text:"在本机浏览器打开";onClicked:shellBridge.openExternal(root.ticket.url) }
   }
  }
  Text { text:"已配对设备";color:Theme.fg;font.pixelSize:18 }
  ListView { width:parent.width;height:230;clip:true;model:root.state.devices;spacing:8;ScrollBar.vertical:SettingsScrollBar{}
   delegate:Row { required property var modelData;spacing:12
    Text { width:600;anchors.verticalCenter:parent.verticalCenter;color:Theme.fg;text:modelData.name+" · "+(modelData.via || "lan")+" · "+(modelData.online?"在线":"离线")+" · 最后活动 "+(modelData.lastSeen?new Date(modelData.lastSeen).toLocaleString():"未知") }
    SettingsButton { objectName:"phoneRevoke_"+modelData.id;text:"撤销设备";onClicked:root.revoke(modelData.id) }
   }
  }
 }
}
