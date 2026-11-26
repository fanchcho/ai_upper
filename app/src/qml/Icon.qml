// Lucide path data comes from IconData, not an icon font or external SVG file.
// Rasterize the same 24x24 SVG at screen DPR. A layered software Shape clips
// at fractional DPR and disappears at DPR=2; Image also respects Flickable
// clipping without the offscreen Shape layer (see docs/audit/icon-dpi.md).
import QtQuick
import QtQuick.Window
import "."

Item {
    id: icon
    property string name: ""
    property real size: 16
    property color color: Theme.fgSubtle
    // 原版个别图标改过线宽；默认按 lucide 规格 2。
    property real strokeWidth: 2
    property bool filled: false

    implicitWidth: size
    implicitHeight: size

    readonly property var parts: name.length ? name.split("|") : []

    Image {
        anchors.fill: parent
        sourceSize.width: icon.size * Screen.devicePixelRatio
        sourceSize.height: icon.size * Screen.devicePixelRatio
        source: {
            var paths = icon.parts.map(function(path) {
                return '<path d="' + path + '"/>'
            }).join('')
            return "data:image/svg+xml," + encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"'
                + ' fill="' + (icon.filled ? icon.color : 'none') + '"'
                + ' stroke="' + (icon.filled ? 'none' : icon.color) + '"'
                + ' stroke-width="' + icon.strokeWidth + '" stroke-linecap="round" stroke-linejoin="round">'
                + paths + '</svg>')
        }
    }
}
