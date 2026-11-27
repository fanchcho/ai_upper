import QtQuick
import "."

Row {
    id: stack
    property var roles: []
    property var images: ({})
    property real size: 20
    readonly property int more: roles.length > 3 ? roles.length - 2 : 0
    spacing: -6
    Repeater {
        model: stack.more ? stack.roles.slice(0, 3) : stack.roles
        Item {
            required property string modelData
            required property int index
            width: stack.size; height: stack.size
            Avatar { anchors.fill: parent; size: stack.size; compact: true; persona: modelData; imageSource: stack.images[modelData] || "" }
            Image {
                anchors.fill: parent
                visible: stack.more > 0 && index === 2
                source: visible && typeof shellBridge !== "undefined" && shellBridge ? shellBridge.personaVeil(modelData) : ""
                sourceSize: Qt.size(stack.size, stack.size)
            }
            Text {
                objectName: "avatarStackRemainder"
                anchors.centerIn: parent; visible: stack.more > 0 && index === 2
                text: "+" + stack.more; color: "white"
                font.pointSize: (stack.more >= 10 ? 8 : 9.5) * 72 / 96
                font.weight: Font.DemiBold; font.letterSpacing: -0.19
            }
        }
    }
}
