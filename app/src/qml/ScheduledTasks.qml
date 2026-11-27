import QtQuick
import QtQuick.Controls.Basic
import "."
Rectangle {
    id: root
    required property var shell
    property var api: null
    property var rows: []
    property string error: ""
    color: Theme.bg
    onVisibleChanged: if (visible) { api = shellBridge.tasksService(); refresh() }
    function refresh() { if (api) rows = api.list() }
    function act(id,action) { error = api.action(id,action); refresh() }
    Connections { target: root.api; function onChanged() { root.refresh() } }
    SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: root.shell.page = "chat" }
    Text { x: 120; y: 26; text: "定时任务"; font.pixelSize: 20; color: Theme.fg }
    Column {
        x: 20; y: 75; width: parent.width-40; spacing: 8
        SettingsField { id: title; objectName: "taskTitle"; width: parent.width; placeholderText: "任务名称" }
        SettingsField { id: prompt; objectName: "taskPrompt"; width: parent.width; placeholderText: "交给角色执行的任务内容" }
        Row { spacing: 8
            ComboBox { id: kind; objectName: "taskKind"; model: ["单次", "重复（cron）"]; width: 160 }
            SettingsField { id: when; objectName: "taskWhen"; width: 270; placeholderText: kind.currentIndex === 0 ? "YYYY-MM-DDTHH:mm" : "分 时 日 月 周" }
            SettingsField { id: tz; objectName: "taskTimezone"; width: 160; text: "UTC"; placeholderText: "IANA 时区" }
            ComboBox { id: persona; width: 180; textRole: "name"; model: root.shell.quickStartPersonas }
        }
        SettingsButton {
            objectName: "taskCreate"; text: "创建任务"
            onClicked: {
                root.error = root.api.create(title.text,prompt.text,kind.currentIndex ? "recurring":"once",when.text,tz.text,
                    persona.currentIndex >= 0 ? persona.model[persona.currentIndex].id : "general")
                if (!root.error) { title.text = ""; prompt.text = ""; root.refresh() }
            }
        }
        Text { text: root.error; color: Theme.danger; visible: text.length > 0 }
    }
    ListView {
        id: list; x: 20; y: 300; width: parent.width-40; height: parent.height-y-20
        clip: true; spacing: 8; model: root.rows; ScrollBar.vertical: SettingsScrollBar {}
        delegate: Rectangle {
            required property var modelData
            width: list.width; height: 130; color: Theme.bgPanel; radius: Theme.radiusSm; border.color: Theme.border
            Text { x: 12; y: 10; text: modelData.title; color: Theme.fg; font.pixelSize: 16 }
            Text { x: 12; y: 35; text: modelData.status + " · " + (modelData.schedule.at || modelData.schedule.cron) + " · " + modelData.schedule.tz; color: Theme.fgMuted }
            Text { x: 12; y: 55; text: "运行记录：" + modelData.runs.length + (modelData.runs.length ? " · " + modelData.runs[modelData.runs.length-1].status : "") + (modelData.lastError || ""); color: Theme.fgMuted }
            Row { x: 12; y: 85; spacing: 8
                SettingsButton { objectName: "taskOpen_"+modelData.id; text: "打开任务对话"; onClicked: root.act(modelData.id,"open") }
                SettingsButton { objectName: "taskRun_"+modelData.id; text: "立即运行"; onClicked: root.act(modelData.id,"run") }
                SettingsButton { objectName: "taskPause_"+modelData.id; text: modelData.status === "active" ? "暂停" : "启用"; onClicked: root.act(modelData.id,modelData.status === "active" ? "pause":"resume") }
                SettingsButton { objectName: "taskDelete_"+modelData.id; text: "删除"; onClicked: root.act(modelData.id,"delete") }
            }
        }
    }
}
