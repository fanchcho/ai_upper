import QtQuick
import QtQuick.Controls.Basic
import "."
Popup {
    id: root
    required property var api
    property var rows: []
    property string selectedId: ""
    property string error: ""
    width: 560; height: 420
    modal: true; focus: true; anchors.centerIn: parent
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radius }
    function refresh() { rows = [{id:"",name:"新增决策服务商"}].concat(api.decisionProviderRows()) }
    function select(row) {
        selectedId=row.id; providerName.text=row.id?row.name:""; host.text=row.apiHost||""
        key.text=""; threshold.text=String(row.threshold===undefined?0.6:row.threshold);enabledProvider.checked=row.enabled!==false
    }
    onOpened: { refresh(); providers.currentIndex=0; select(rows[0]) }
    Column {
        anchors.fill: parent; anchors.margins: 16; spacing: 10
        Text { text: "自动决策服务商 · Jev"; color: Theme.fg; font.pixelSize: 18 }
        ComboBox { id:providers; objectName:"decisionConfigSelect"; width:parent.width; model:root.rows; textRole:"name"; onActivated:root.select(root.rows[currentIndex]) }
        SettingsField { id:providerName; objectName:"decisionConfigName"; width:parent.width; placeholderText:"服务商名称" }
        SettingsField { id:host; objectName:"decisionConfigHost"; width:parent.width; placeholderText:"API 服务地址（HTTP(S)）" }
        SettingsField { id:key; objectName:"decisionConfigKey"; width:parent.width; echoMode:TextInput.Password; placeholderText:root.selectedId?"密钥（留空保留原密钥）":"API 密钥" }
        Row { spacing:10
            Text { text:"默认触发阈值"; color:Theme.fg; height:34; verticalAlignment:Text.AlignVCenter }
            SettingsField { id:threshold; objectName:"decisionConfigThreshold"; width:100; text:"0.6" }
            CheckBox { id:enabledProvider; objectName:"decisionConfigEnabled"; text:"启用"; checked:true }
        }
        Text { text:root.error; color:Theme.danger; visible:text.length>0; width:parent.width; wrapMode:Text.Wrap }
        Row { spacing:8
            SettingsButton { objectName:"decisionConfigSave"; text:"保存"; onClicked: {
                root.error=root.api.saveDecisionProvider(root.selectedId,providerName.text,host.text,key.text,Number(threshold.text),enabledProvider.checked)
                if(!root.error)root.close()
            } }
            SettingsButton { objectName:"decisionConfigDelete"; visible:root.selectedId.length>0; text:"删除"; onClicked: {
                if(shellBridge.deleteProvider(root.selectedId)){root.refresh();providers.currentIndex=0;root.select(root.rows[0])}
            } }
            SettingsButton { text:"关闭"; onClicked:root.close() }
        }
    }
}
