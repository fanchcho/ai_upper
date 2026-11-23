// 输入区上下文圆环（模型贴片左侧）：28×28 方形贴片 + 16×16 灰色圆环。
//
// 逐项取自只读原版：
//   redesign/ContextRing.tsx:58-68  button.cf-mp__ringbtn（28×28，见 model-panel.css:20-23）；
//   redesign/ContextRing.tsx:98-120 16×16 SVG、r=6、stroke=2、track/arc 均灰、
//                                   12 点起顺时针、无数字；
//   redesign/ContextRing.tsx:69-91  卡片 260 宽、10/12/12 padding、bottom 8、居圆环，
//                                   进度条 6px、tick 2px；
//   redesign/ContextRing.tsx:42-55  卡片越窗左右各留 8px 的 clamp。
//   redesign/model-panel.css:20-33  ringbtn 28px、padding 0、justify-content center；
//                                   track=var(--border-strong)、arc=var(--fg-muted)。
//   redesign/model-panel.css:37-74  card/borders/shadow、title 12/600 --fg-muted、
//                                   value 11.5px --fg-subtle、bar 6px margin-top 9、
//                                   fill --fg-muted、tick --fg-subtle 上下各 3px。
//   redesign/context-usage.ts:62-81 approxTokens / usageRatio / usagePercent 的精确口径。
//   shared/context.ts:163-175      formatTokens 的十进制优先规则。
//
// 读数缺失（used=None，新对话/无模型）时整个贴片不占宽；有读数才显示 28px。
import QtQuick
import "."

Item {
    id: root

    // Python `contextUsage()` 投影：{used, estimated, window, trigger}。
    property var usage: ({})
    // 由 Python chatLabels() 投影：context / approx / usage / autoCompact。
    property var labels: ({})
    // 打开/收起由 Main.qml 统一管理，点模型或思考贴片时一并收起。
    property bool open: false
    // 窗口宽（用于卡片越界内移；deva 固定左右各留 8px）。
    property real viewportWidth: 1280

    signal toggleRequested()

    readonly property var u: usage || ({})
    readonly property bool available: u.used !== undefined && u.used !== null
    readonly property real ratio: {
        if (u.used === undefined || u.used === null || !u.window || u.window <= 0)
            return 0
        return Math.min(1, Math.max(0, u.used / u.window))
    }

    function approxTokens(n) {
        n = Number(n) || 0
        if (n < 1000)
            return String(Math.max(0, Math.round(n)))
        if (n < 999500)
            return String(Math.round(n / 1000)) + "K"
        return String(Number((n / 1000000).toFixed(2))) + "M"
    }

    function formatTokens(n) {
        n = Number(n) || 0
        if (n >= 1000000) {
            if (n % 1000000 === 0)
                return String(n / 1000000) + "M"
            if (n % 1048576 === 0)
                return String(n / 1048576) + "M"
            return String(Number((n / 1000000).toFixed(2))) + "M"
        }
        if (n >= 1000) {
            if (n % 1000 === 0)
                return String(n / 1000) + "K"
            if (n % 1024 === 0)
                return String(n / 1024) + "K"
            return String(Number((n / 1000).toFixed(1))) + "K"
        }
        return String(n)
    }

    function usagePercent() {
        if (u.used === undefined || u.used === null || !u.window || u.window <= 0)
            return ""
        var p = (u.used / u.window) * 100
        if (p > 0 && p < 0.1)
            return "<0.1%"
        return String(Number(Math.min(100, p).toFixed(1))) + "%"
    }

    function label(key, fallback) {
        return root.labels && root.labels[key] ? root.labels[key] : fallback
    }

    readonly property string usageText: {
        if (!available)
            return ""
        var text = label("usage", "{used}/{window} ({pct})")
            .replace("{used}", approxTokens(u.used || 0))
            .replace("{window}", formatTokens(u.window || 0))
            .replace("{pct}", usagePercent())
        return u.estimated ? label("approx", "~{n}").replace("{n}", text) : text
    }
    readonly property string titleText: label("context", "Context") + " " + usageText
    readonly property real tickRatio: (u.trigger !== undefined && u.trigger !== null && u.window > 0)
                                      ? Math.min(1, u.trigger / u.window) : -1

    // 卡片以圆环为中心；超出窗口时按 deva ContextRing.tsx:42-55 的 8px 边距往里挪。
    readonly property real cardShift: {
        if (!open)
            return 0
        var p = root.mapToItem(null, 0, 0)
        var left = p.x + root.width / 2 - 130
        var right = left + 260
        var over = right - (root.viewportWidth - 8)
        var under = 8 - left
        return over > 0 ? -over : (under > 0 ? under : 0)
    }

    implicitWidth: available ? 28 : 0
    implicitHeight: available ? 28 : 0
    width: implicitWidth
    height: implicitHeight
    visible: available

    Rectangle {
        id: ringButton
        anchors.fill: parent
        radius: Theme.radius
        color: root.open ? Theme.bgActive : (ringHover.hovered ? Theme.bgHover : "transparent")
        HoverHandler { id: ringHover }
        MouseArea {
            anchors.fill: parent
            onClicked: root.toggleRequested()
        }
    }

    Canvas {
        id: ring
        width: 16
        height: 16
        anchors.centerIn: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            ctx.lineWidth = 2
            ctx.strokeStyle = Theme.borderStrong
            ctx.beginPath()
            ctx.arc(8, 8, 6, 0, Math.PI * 2)
            ctx.stroke()
            if (root.ratio > 0) {
                ctx.strokeStyle = Theme.fgMuted
                ctx.lineCap = "round"
                ctx.beginPath()
                ctx.arc(8, 8, 6, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * root.ratio)
                ctx.stroke()
            }
        }
    }
    onRatioChanged: ring.requestPaint()

    SoftShadow {
        target: card
        visible: root.open
        blur: Theme.dark ? 26 : 20
    }

    Rectangle {
        id: card
        objectName: "contextCard"
        visible: root.open
        z: 50
        width: 260
        height: 53
        x: root.width / 2 - width / 2 + root.cardShift
        y: -height - 8
        radius: Theme.radiusLg
        color: Theme.bgElevated
        border.width: 1
        border.color: Theme.border

        Text {
            id: cardTitle
            x: 13
            y: 11
            text: root.label("context", "Context")
            color: Theme.fgMuted
            font.family: Theme.sansFamily
            font.pixelSize: 12
            font.weight: 600
        }
        Text {
            id: cardValue
            anchors.right: parent.right
            anchors.rightMargin: 13
            y: 11
            text: root.usageText
            color: Theme.fgSubtle
            font.family: Theme.sansFamily
            // 原版 11.5px；Qt pixelSize 只收整数，96dpi 下 11.5px = 8.625pt（同 SettingsModal:603）。
            font.pointSize: 8.625
        }
        Rectangle {
            id: bar
            x: 13
            y: 34
            width: parent.width - 26
            height: 6
            radius: 3
            color: Theme.bgInset
            border.width: 1
            border.color: Theme.border
            Rectangle {
                width: Math.round(parent.width * root.ratio * 10) / 10
                height: parent.height
                radius: 3
                color: Theme.fgMuted
            }
            Rectangle {
                visible: root.tickRatio >= 0
                x: Math.round(parent.width * root.tickRatio) - 1
                y: -3
                width: 2
                height: parent.height + 6
                radius: 1
                color: Theme.fgSubtle
            }
        }
    }
}
