import QtQuick

// 软件光栅下的投影：`QT_QUICK_BACKEND=software` 时 QtQuick.Effects 的 MultiEffect 与
// Qt5Compat 的 DropShadow 都**不出影**（实测灰底像素不变），只有 Canvas 的
// ctx.shadowColor / shadowBlur / shadowOffsetY 生效。
//
// 画法：把卡片自身的圆角矩形从画布里挖掉（evenodd 裁剪），只画「卡片外」那一圈，
// 否则半透明阴影会叠在卡面上把它压暗。
//
// 默认参数取自原版 tokens.css 的 `--shadow`：浅色 `0 6px 24px rgba(0,0,0,.12)`（:82）、
// 深色 `0 8px 30px rgba(0,0,0,.5)`（:149）。颜色用 Theme.shadow（Theme.qml:67 已按深浅
// 取 0.12 / 0.50），blur / offsetY 在这里按深浅分别取。
Item {
    id: root

    // 被投影的卡片：位置、尺寸、圆角全部跟着它走（同一父级坐标系）。
    property Item target: null
    property real radius: target && target.radius !== undefined ? target.radius : Theme.radiusLg
    property color color: Theme.shadow
    property real blur: Theme.dark ? 30 : 24
    property real offsetY: Theme.dark ? 8 : 6
    // 外扩量：blur 30 的外沿 + 8px 偏移 + 余量 = 38（与输入卡片实测取值一致，
    // 再小会让高斯尾部被画布边缘截断）。
    property real pad: 38

    x: target ? target.x - pad : 0
    y: target ? target.y - pad : 0
    width: target ? target.width + 2 * pad : 0
    height: target ? target.height + 2 * pad : 0

    onWidthChanged: canvas.requestPaint()
    onHeightChanged: canvas.requestPaint()
    Connections {
        target: Theme
        function onDarkChanged() { canvas.requestPaint() }
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var pad = root.pad
            var box = { x: pad, y: pad, w: width - 2 * pad, h: height - 2 * pad, r: root.radius }
            function ringPath(c) {
                // 圆角矩形（arcTo 顺序：右上 → 右下 → 左下 → 左上）
                c.moveTo(box.x + box.r, box.y)
                c.arcTo(box.x + box.w, box.y, box.x + box.w, box.y + box.h, box.r)
                c.arcTo(box.x + box.w, box.y + box.h, box.x, box.y + box.h, box.r)
                c.arcTo(box.x, box.y + box.h, box.x, box.y, box.r)
                c.arcTo(box.x, box.y, box.x + box.w, box.y, box.r)
                c.closePath()
            }
            // 只保留画布内、卡片外的那一圈
            ctx.beginPath()
            ctx.rect(0, 0, width, height)
            ringPath(ctx)
            ctx.clip("evenodd")
            ctx.shadowColor = root.color
            ctx.shadowBlur = root.blur
            ctx.shadowOffsetY = root.offsetY
            ctx.fillStyle = "rgba(0,0,0,1)"
            ctx.beginPath()
            ringPath(ctx)
            ctx.fill()
        }
    }
}
