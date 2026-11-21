// 头像：直接显示预生成的原版 humation SVG（见 scripts/parity/gen_avatars.mjs）。
//
// 原版头像不是图片而是渲染期生成的 SVG，形状/配色由 persona 的 seed 或显式 spec 决定。
// 这里用的是同一个引擎、同一份 spec 预生成的产物，运行时只做缩放，不再二次创作。
import QtQuick
import "."

Item {
    id: ava
    // 文件名（不含 .svg）：user / general / xiaomajiang
    property string persona: "general"
    // 框内构图（原版 `shell-common.tsx:313` 的 `compact`）。原版是 `compact ?? size <= 20`：
    // 不传时按尺寸自动判定，所以 34/38/48 的头像默认都是「探出」构图
    // （`humation.tsx:817` `pop = !compact && !!parts.head`，box 换成 `POP_BOX`），
    // 只有 ≤20 的小头像才用框内构图。对应 `avatars/<id>.svg` 与 `<id>-pop.svg` 两套。
    property bool compact: size <= 20
    readonly property bool pop: !compact
    property real size: 38
    implicitWidth: size
    implicitHeight: size

    Image {
        anchors.fill: parent
        source: "avatars/" + ava.persona + (ava.pop ? "-pop" : "") + ".svg"
        sourceSize: Qt.size(ava.size, ava.size)
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
