// 会话行的几何与配色逐项取自原版（CDP 实测 out/qml-shell/dom/chat.json）：
//   行 275×54，padding 8/12，grid 38px + 12px gap，头像 38，标题 13/600，
//   时间 11/#8a8a94，选中底色 rgba(91,91,214,0.12)，圆角 8。
// 三态优先级严格照 apps/desktop/src/renderer/src/redesign/redesign.css：
//   hover  = --bg-hover（styles/tokens.css:45 rgba(0,0,0,0.045)；深色 :113 rgba(255,255,255,0.06)），
//            见 redesign.css:762-764；叠在 #f7f7f8 上为 (236,236,237)。
//   active = --bg-selected（styles/tokens.css:47 rgba(91,91,214,0.12)；深色 :115 rgba(124,124,240,0.2)），
//            见 redesign.css:765-767；叠在 #f7f7f8 上为 (228,228,244)。
//   picked = 多选勾选态，同样用 --bg-selected（redesign.css:788-793），勾选框见 :795-813。
// active / picked 的规则在 hover 之后，故二者优先于 hover，与下列绑定顺序一致。
import QtQuick
import "."

Rectangle {
    id: row
    property string title: ""
    property string time: ""
    property string persona: "general"
    property string ownerName: ""
    property bool active: false
    // 交互态：逐页对比里需要固定某一行显示 hover 时使用（原版是真实鼠标悬停）。
    property bool forceHover: false
    // 多选态：右键「Select」进入后显示左侧勾选框，点击整行即切换选中。
    property bool selectionMode: false
    property bool selected: false
    // 未读红点：原版 Rail.tsx:1124-1156 + redesign.css:1041-1051
    // （头像右上角 10px、--danger、外圈 2px --bg-panel）。
    property bool unread: false
    property bool attention: false

    height: 54
    radius: Theme.radius
    color: selected ? Theme.bgSelected
                    : active ? Theme.bgSelected
                             : (hover.hovered || forceHover) ? Theme.bgHover
                                                             : "transparent"

    HoverHandler { id: hover }

    // 多选勾选框：原版 `ThreadSelect` 行首的 checkbox；只在 selectionMode 下出现。
    Rectangle {
        objectName: "threadCheck"
        visible: row.selectionMode
        x: 8
        y: 19
        width: 16
        height: 16
        radius: 4
        color: row.selected ? Theme.accent : "transparent"
        border.width: 1
        border.color: row.selected ? Theme.accent : Theme.borderStrong
        Text {
            anchors.centerIn: parent
            visible: row.selected
            text: "✓"
            color: Theme.accentFg
            font.family: Theme.sansFamily
            font.pixelSize: 11
            font.weight: 700
        }
    }

    // 头像：原版 `.cf-ava` 是 38×38 的 humation SVG（DOM 实测 x=12/y=8，相对行）。
    Avatar {
        id: face
        objectName: "threadFace"
        persona: row.persona
        size: 38
        x: row.selectionMode ? 30 : 12
        y: 8
    }
    Rectangle {
        objectName: "threadUnread"
        visible: (row.unread || row.attention) && !row.active
        x: face.x + face.width - 9
        y: face.y - 1
        width: 10
        height: 10
        radius: 5
        color: Theme.danger
        border.width: 2
        border.color: Theme.bgPanel
    }

    // 主列：标题行 17px（13/600）+ 角色名 13px（11px）
    Text {
        id: titleText
        x: row.selectionMode ? 80 : 62
        y: 8
        width: row.width - x - 12 - timeText.width - 8
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
        x: row.selectionMode ? 80 : 62
        y: 29
        width: row.width - x - 12
        text: row.ownerName
        color: Theme.fgSubtle
        font.family: Theme.sansFamily
        font.pixelSize: 11
        height: 13
        elide: Text.ElideRight
    }
}
