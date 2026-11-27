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
    color: Theme.bg
    onVisibleChanged: if (visible) { api = shellBridge.botsService(); refresh() }
    function refresh() { if (api) rows = api.list() }
    function act(id,action,value) { error = api.action(id,action,value || ""); refresh() }
    Connections {
        target: root.api
        function onChanged() { root.refresh() }
        function onStatus(error,link) { root.error = error; root.link = link }
    }
    SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: root.shell.page = "chat" }
    Text { x: 120; y: 26; text: "机器人"; font.pixelSize: 20; color: Theme.fg }
    Column { id: setup; x: 20; y: 75; width: parent.width-40; spacing: 10
        Text { text: "Telegram · 从 @BotFather 复制 Token，然后打开配对链接认领机器人"; color: Theme.fgMuted }
        Row { spacing: 8
            SettingsField { id: token; objectName: "botToken"; width: 470; placeholderText: "Bot Token"; echoMode: TextInput.Password }
            SettingsButton { objectName: "botLink"; text: "添加 Telegram"; onClicked: root.error = root.api.linkTelegram(token.text) }
            SettingsButton { text: "取消配对"; onClicked: { root.api.cancelLink(); root.link = "" } }
        }
        Row { spacing:8
            SettingsField { id:feishuId; objectName:"feishuId"; width:200; placeholderText:"飞书 App ID" }
            SettingsField { id:feishuSecret; objectName:"feishuSecret"; width:200; placeholderText:"App Secret"; echoMode:TextInput.Password }
            ComboBox { id:feishuDomain; objectName:"feishuDomain"; width:110; model:["feishu","lark"] }
            SettingsButton { objectName:"feishuConnect"; text:"连接飞书"; onClicked:root.error=root.api.linkFeishu(feishuId.text,feishuSecret.text,feishuDomain.currentText) }
        }
        SettingsButton { visible: root.link.length > 0; text: "打开 Telegram 认领链接"; onClicked: shellBridge.openExternal(root.link) }
        SettingsButton { objectName:"webPairTicket"; text:"生成浏览器配对票据"; onClicked:root.webLink=root.api.webPairTicket() }
        SettingsButton { objectName:"openWebPair"; visible:root.webLink.length>0; text:"打开浏览器完成安全配对"; onClicked:shellBridge.openExternal(root.webLink) }
        Text { text: root.error; visible: text.length > 0; color: Theme.danger; wrapMode: Text.Wrap; width: parent.width }
    }
    ListView {
        id: list; x: 20; y: setup.y+setup.height+20; width: parent.width-40; height: Math.max(0,parent.height-y-20)
        model: root.rows; spacing: 8; clip: true; ScrollBar.vertical: SettingsScrollBar {}
        delegate: Rectangle {
            required property var modelData
            width: list.width; height: 178; color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
            Text { x: 12; y: 12; text: modelData.name + " · " + modelData.platform; color: Theme.fg; font.pixelSize: 16 }
            Text { x: 12; y: 40; text: modelData.state + " · " + (modelData.users || []).length + " 位已配对用户"; color: Theme.fgMuted }
            Row { x: 12; y: 68; spacing: 8
                SettingsButton { visible:modelData.platform==="feishu"; objectName:"feishuPair_"+modelData.id; text:"生成配对码"; onClicked:root.error=root.api.feishuPairCode(modelData.id) }
                SettingsButton { objectName: "botToggle_"+modelData.id; text: modelData.enabled ? "停用" : "启用"; onClicked: root.act(modelData.id,modelData.enabled ? "disable":"enable") }
                SettingsButton { objectName: "botReply_"+modelData.id; text: "回复："+(modelData.replyMode === "final" ? "仅最终":"流式"); onClicked: root.act(modelData.id,"reply",modelData.replyMode === "final" ? "stream":"final") }
                SettingsButton { objectName: "botScope_"+modelData.id; text: "范围："+(modelData.scope.mode === "all" ? "全部":"指定对话"); onClicked: root.act(modelData.id,"scope",JSON.stringify({mode:modelData.scope.mode === "all" ? "sessions":"all",personas:modelData.scope.personas || [],sessions:[root.shell.activeId]})) }
                SettingsButton { objectName: "botDelete_"+modelData.id; text: "删除"; onClicked: root.act(modelData.id,"delete") }
            }
            Row { x: 12; y: 118; spacing: 8
                Repeater { model: modelData.users || []
                    SettingsButton { required property var modelData; objectName: "botUser_"+modelData.id; text: "移除用户 " + (modelData.name || modelData.id); onClicked: root.act(parent.parent.modelData.id,"remove-user",modelData.id) }
                }
            }
        }
    }
}
