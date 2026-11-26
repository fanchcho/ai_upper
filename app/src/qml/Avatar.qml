// Avatar images take priority; otherwise render the original Humation seed/spec in Qt.
import QtQuick
import "."

Item {
    id: ava
    // 文件名（不含 .svg）：user / general / xiaomajiang
    property string persona: "general"
    property string imageSource: ""
    // 框内构图（原版 `shell-common.tsx:313` 的 `compact`）。原版是 `compact ?? size <= 20`：
    // 不传时按尺寸自动判定，所以 34/38/48 的头像默认都是「探出」构图
    // （`humation.tsx:817` `pop = !compact && !!parts.head`，box 换成 `POP_BOX`），
    // 只有 ≤20 的小头像才用框内构图。对应 `avatars/<id>.svg` 与 `<id>-pop.svg` 两套。
    property bool compact: size <= 20
    readonly property bool pop: !compact
    property real size: 38
    implicitWidth: size
    implicitHeight: size

    Rectangle {
        anchors.fill: parent; radius: width / 2
        visible: avatarImage.status === Image.Error || avatarImage.source.toString().length === 0
        color: Theme.accent
        Text { anchors.centerIn: parent; text: ava.persona.slice(0, 1).toUpperCase(); color: Theme.accentFg; font.pixelSize: ava.size * 0.5 }
    }
    Image {
        id: avatarImage
        anchors.fill: parent
        source: {
            if (ava.imageSource) return ava.imageSource
            if (ava.persona === "user") return "avatars/user" + (ava.pop ? "-pop" : "") + ".svg"
            if (typeof shellBridge !== "undefined" && shellBridge)
                return shellBridge.personaAvatar(ava.persona, ava.pop)
            // The context is gone during teardown: never start a disk read.
            return ""
        }
        sourceSize: Qt.size(ava.size, ava.size)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
