// 会话行的几何与配色逐项取自原版（CDP 实测 out/qml-shell/dom/chat.json）：
//   行 275×54，padding 8/12，grid 38px + 12px gap，头像 38，标题 13/600，
//   时间 11/#8a8a94，选中底色 rgba(91,91,214,0.12)，圆角 8。
import QtQuick
import "."

Rectangle {
    id: row
    property string title: ""
    property string time: ""
    property string persona: "general"
    property bool active: false

    height: 54
    radius: Theme.radius
    color: active ? Theme.bgSelected
                  : hover.hovered ? Theme.bgHover
                                  : "transparent"

    HoverHandler { id: hover }

    // 头像位（38×38，x=12/y=8）保留但不画内容：原版 `.cf-ava` 在这份数据里是空的
    // div（DOM 实测无子节点、背景透明），只有外框占位。这里如实留空，别画自造的头像。
    Item {
        id: face
        objectName: "threadFace"
        x: 12
        y: 8
        width: 38
        height: 38
    }

    Text {
        id: titleText
        x: 62
        y: 8
        width: row.width - 62 - 12 - timeText.width - 8
        text: row.title
        color: Theme.fg
        font.family: Theme.sansFamily
        font.pixelSize: 13
        font.weight: 600
        elide: Text.ElideRight
        height: 19
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        id: timeText
        anchors.right: parent.right
        anchors.rightMargin: 12
        y: 8 + (19 - height) / 2 + 2
        text: row.time
        color: Theme.fgSubtle
        font.family: Theme.sansFamily
        font.pixelSize: 11
        height: 13
        verticalAlignment: Text.AlignVCenter
    }
}
