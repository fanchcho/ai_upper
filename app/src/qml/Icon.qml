// lucide 图标的 QML 画法：24×24 viewBox 的 stroke 路径，按目标尺寸整体缩放。
//
// 路径数据来自 IconData（由 scripts/parity/gen_icons.mjs 从原版的 lucide-react 里抽出，
// 与原版用的是同一份 `d`），不是另画的近似图形。原版 SVG 的默认属性是
// stroke-width=2 / linecap=round / linejoin=round，缩放时线宽随比例一起走，
// 与浏览器里 `<svg width=16 height=16 viewBox="0 0 24 24">` 的渲染同构。
//
// 一个图标常由多条子路径组成（lucide 里每条 path/circle/rect 是一个子元素），
// 生成器用 "|" 连接；这里拆开后每条子路径各自一个 ShapePath，避免跨子路径连线。
import QtQuick
import QtQuick.Shapes
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
    // 子路径条数上限：lucide 里最多的是 cog（14 条），留到 16 条足够。
    function part(i) { return i < parts.length ? parts[i] : "" }

    Shape {
        // Contain software Shape painting before ancestor Flickable clipping.
        // Keep the layer inside Icon so it cannot add siblings to a Row.
        layer.enabled: true
        width: 24
        height: 24
        scale: icon.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        // 线宽是 viewBox 单位，先按缩放倒回，使屏幕上呈现 strokeWidth * size/24 的视觉线宽
        // 与原版 `<svg stroke-width=2>` 在同样尺寸下一致。
        //
        // 注意：Repeater 的 delegate 必须是 Item，而 ShapePath 不是 Item，
        // 所以这里不用 Repeater，改用固定槽位 + 空 path 占位（空 path 不画任何东西）。
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(0) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(1) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(2) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(3) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(4) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(5) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(6) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(7) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(8) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(9) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(10) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(11) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(12) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(13) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(14) } }
        ShapePath { strokeColor: icon.filled ? "transparent" : icon.color; fillColor: icon.filled ? icon.color : "transparent"; strokeWidth: icon.strokeWidth; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin; PathSvg { path: icon.part(15) } }
    }
}
