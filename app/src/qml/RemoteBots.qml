import QtQuick
import QtQuick.Controls.Basic
import "."
Rectangle {
    id: root
    required property var shell
    property var api: null
    property var rows: []
    property string error: ""
    property string link: ""
    property string webLink: ""
    property string query: ""
    property string selectedId: ""
    property var selected: null
    property var scan: ({status:"idle"})
    function select(id) { selectedId=id; selected=rows.find(function(r){return r.id===id}) || null }

    color: Theme.bg
    onVisibleChanged: if (visible) { api = shellBridge.botsService(); refresh() }
    function refresh() { if (api) { rows = api.list(); select(selectedId) } }
    function act(id,action,value) { error = api.action(id,action,value || ""); refresh() }
    Connections {
        target: root.api
        function onChanged() { root.refresh() }
        function onStatus(error,link) { root.error = error; root.link = link }
        function onScanChanged(state) { root.scan=state; if(state.status==="done")root.select(state.botId) }
    }
    SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: root.shell.page = "chat" }
    Text { x: 120; y: 26; text: "机器人"; font.pixelSize: 20; color: Theme.fg }
    Column { visible: !root.selected; id: setup; x: 20; y: 75; width: parent.width-40; spacing: 10
        Text { text: "Telegram · 从 @BotFather 复制 Token，然后打开配对链接认领机器人"; color: Theme.fgMuted }
        Row { spacing: 8
            SettingsField { id: token; objectName: "botToken"; width: 470; placeholderText: "Bot Token"; echoMode: TextInput.Password }
            SettingsButton { objectName: "botLink"; text: "添加 Telegram"; onClicked: root.error = root.api.linkTelegram(token.text) }
            SettingsButton { text: "取消配对"; onClicked: { root.api.cancelLink(); root.link = "" } }
        }
        Row { spacing:8
            SettingsButton { objectName:"feishuScan"; text:"扫码创建飞书应用"; onClicked:root.api.startFeishuScan() }
            SettingsField { id:feishuId; objectName:"feishuId"; width:200; placeholderText:"飞书 App ID" }
            SettingsField { id:feishuSecret; objectName:"feishuSecret"; width:200; placeholderText:"App Secret"; echoMode:TextInput.Password }
            ComboBox { id:feishuDomain; objectName:"feishuDomain"; width:110; model:["feishu","lark"] }
            SettingsButton { objectName:"feishuConnect"; text:"连接飞书"; onClicked:root.error=root.api.linkFeishu(feishuId.text,feishuSecret.text,feishuDomain.currentText) }
        }
        SettingsButton { visible: root.link.length > 0; text: "打开 Telegram 认领链接"; onClicked: shellBridge.openExternal(root.link) }
        SettingsButton { objectName:"phoneEntry"; text:"手机联动：扫码 / 设备"; onClicked:root.shell.page="phone" }
        SettingsButton { objectName:"webPairTicket"; text:"生成浏览器配对票据"; onClicked:root.webLink=root.api.webPairTicket() }
        SettingsButton { objectName:"openWebPair"; visible:root.webLink.length>0; text:"打开浏览器完成安全配对"; onClicked:shellBridge.openExternal(root.webLink) }
        Text { text: root.error; visible: text.length > 0; color: Theme.danger; wrapMode: Text.Wrap; width: parent.width }
        SettingsField { objectName: "botSearch"; width: parent.width; placeholderText: "搜索机器人"; onTextChanged: root.query = text }

    }
    ListView {
        id: list; visible: !root.selected; x: 20; y: setup.y+setup.height+20; width: parent.width-40; height: Math.max(0,parent.height-y-20)
        model: root.rows.filter(function(row) { return !root.query || String(row.name || "").toLowerCase().indexOf(root.query.toLowerCase()) >= 0 || String(row.platform || "").toLowerCase().indexOf(root.query.toLowerCase()) >= 0 }); spacing: 8; clip: true; ScrollBar.vertical: SettingsScrollBar {}
        delegate: Rectangle {
            required property var modelData
            width: list.width; height: 208; color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
            SettingsButton { x:parent.width-100; y:10; objectName:"botDetail_"+modelData.id; text:"详情"; onClicked:root.select(modelData.id) }
            Text { x: 12; y: 12; text: modelData.name + " · " + modelData.platform; color: Theme.fg; font.pixelSize: 16 }
            Text { x: 12; y: 40; text: modelData.state + " · " + (modelData.users || []).length + " 位已配对用户"; color: Theme.fgMuted }
            Text { x: 12; y: 59; text: "回复：" + (modelData.replyMode === "final" ? "仅最终" : "流式") + " · 范围：" + (modelData.scope && modelData.scope.mode || "all"); color: Theme.fgMuted; elide: Text.ElideRight; width: parent.width-24 }
            Text { x: 12; y: 77; visible: modelData.platform === "feishu"; text: "App ID：" + (modelData.settings && modelData.settings.appId || "未配置") + " · 域：" + (modelData.settings && modelData.settings.domain || "feishu"); color: Theme.fgMuted; elide: Text.ElideRight; width: parent.width-24 }
            Row { x: 12; y: 98; spacing: 8
                SettingsButton { visible:modelData.platform==="feishu"; objectName:"feishuPair_"+modelData.id; text:"生成配对码"; onClicked:root.error=root.api.feishuPairCode(modelData.id) }
                SettingsButton { objectName: "botToggle_"+modelData.id; text: modelData.enabled ? "停用" : "启用"; onClicked: root.act(modelData.id,modelData.enabled ? "disable":"enable") }
                SettingsButton { objectName: "botReply_"+modelData.id; text: "回复："+(modelData.replyMode === "final" ? "仅最终":"流式"); onClicked: root.act(modelData.id,"reply",modelData.replyMode === "final" ? "stream":"final") }
                SettingsButton { objectName: "botScope_"+modelData.id; text: "范围："+(modelData.scope.mode === "all" ? "全部":"指定对话"); onClicked: root.act(modelData.id,"scope",JSON.stringify({mode:modelData.scope.mode === "all" ? "sessions":"all",personas:modelData.scope.personas || [],sessions:[root.shell.activeId]})) }
                SettingsButton { objectName: "botDelete_"+modelData.id; text: "删除"; onClicked: root.act(modelData.id,"delete") }
            }
            Row { x: 12; y: 148; spacing: 8
                Repeater { model: modelData.users || []
                    SettingsButton { required property var modelData; objectName: "botUser_"+modelData.id; text: "移除用户 " + (modelData.name || modelData.id); onClicked: root.act(parent.parent.modelData.id,"remove-user",modelData.id) }
                }
            }
        }
    }

    BotDetail {
        anchors { top:parent.top; topMargin:75; left:parent.left; leftMargin:20; right:parent.right; rightMargin:20; bottom:parent.bottom; bottomMargin:20 }
        visible: root.selected !== null
        bot: root.selected
        api: root.api
        onBack: root.select("")
        onAction: function(action,value) { root.act(root.selectedId,action,value) }
    }
    Rectangle {
        anchors.centerIn:parent; width:480; height:520; z:10
        visible:["loading","waiting","error","denied","expired"].indexOf(root.scan.status)>=0
        color:Theme.bgPanel; border.color:Theme.border; radius:Theme.radiusSm
        Column { anchors.fill:parent; anchors.margins:20; spacing:12
            Text { text:"扫码创建 / 认领机器人"; color:Theme.fg; font.pixelSize:20 }
            Image { objectName:"botScanQr"; width:320; height:320; anchors.horizontalCenter:parent.horizontalCenter; source:root.scan.qr || ""; smooth:false }
            Text { objectName:"botScanStatus"; width:parent.width; wrapMode:Text.Wrap; color:Theme.fg
                text:root.scan.error || (root.scan.status==="waiting" ? "请在应用中扫码并确认；二维码仅本次有效" : "正在获取二维码…") }
            SettingsButton { objectName:"botScanCancel"; text:"关闭 / 取消扫码"; onClicked:{root.api.cancelScan();root.api.cancelLink();root.scan={status:"cancelled"}} }
        }
    }
}
