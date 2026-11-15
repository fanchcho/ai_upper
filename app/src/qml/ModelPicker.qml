// 模型/强度下拉：几何取自原版实测（out/qml-shell/pages/deva/model-picker-deva.png
// 的测量结果：面板 (700,542)–(1129,759)，即 429×217；分组标题 "THINKING LEVEL"
// 为 11px 字距加宽的小标题，选项为 4 行（Default/Low/High/Max））。
import QtQuick
import "."

Rectangle {
    id: picker
    signal close()

    width: 429
    height: 217
    radius: Theme.radiusLg
    color: Theme.bg
    border.width: 1
    border.color: Theme.border

    Rectangle {
        z: -1
        anchors.fill: parent
        anchors.margins: -6
        radius: Theme.radiusLg + 4
        color: Theme.shadow
        opacity: 0.5
    }

    Column {
        x: 12
        y: 10
        spacing: 2

        Text {
            x: 4
            text: "THINKING LEVEL"
            color: Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 11
            font.weight: 600
            font.letterSpacing: 0.6
            height: 24
            verticalAlignment: Text.AlignVCenter
        }

        Repeater {
            model: ["Default", "Low", "High", "Max"]
            delegate: Rectangle {
                required property int index
                required property string modelData
                width: 397
                height: 34
                radius: Theme.radius
                color: optHover.hovered ? Theme.bgHover : "transparent"
                Text {
                    x: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData
                    color: index === 0 ? Theme.fg : Theme.fgMuted
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: index === 0 ? 600 : 400
                }
                HoverHandler { id: optHover }
                MouseArea {
                    anchors.fill: parent
                    onClicked: picker.close()
                }
            }
        }
    }
}
