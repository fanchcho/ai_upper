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
    property string ownerName: ""
    property bool active: false
    // 交互态：逐页对比里 hover-thread 需要指定某一行处于 hover（原版是真实鼠标悬停）。
    property bool forceHover: false

    height: 54
    radius: Theme.radius
    color: active ? Theme.bgSelected
                  : (hover.hovered || forceHover) ? Theme.bgHover
                                                  : "transparent"

    HoverHandler { id: hover }

    // 头像：原版 `.cf-ava` 是 38×38 的 humation SVG（DOM 实测 x=12/y=8，相对行）。
    Avatar {
        id: face
        objectName: "threadFace"
        persona: row.persona
        size: 38
        x: 12
        y: 8
    }

    // 主列：标题行 17px（13/600）+ 角色名 13px（11px）
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
        height: 17
        verticalAlignment: Text.AlignVCenter
    }

    Text {
        id: timeText
        anchors.right: parent.right
        anchors.rightMargin: 12
        y: 12
        text: row.time
        color: Theme.fgSubtle
        font.family: Theme.sansFamily
        font.pixelSize: 11
        height: 13
        verticalAlignment: Text.AlignVCenter
    }

    // 角色名：原版 `.cf-thread__owner`，11px、次要色，紧贴标题行下方。
    Text {
        id: ownerText
        x: 62
        y: 27
        width: row.width - 62 - 12
        text: row.ownerName
        color: Theme.fgSubtle
        font.family: Theme.sansFamily
        font.pixelSize: 11
        height: 13
        elide: Text.ElideRight
    }
}
