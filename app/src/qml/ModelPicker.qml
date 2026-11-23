// 输入区两个贴片的下拉：模型列表（mode="model"）与思考等级（mode="thinking"）。
//
// 外壳与内容逐值取自原版只读源码（/tmp/deva-merged/apps/desktop/src/renderer/src）：
//   styles/app.css:3367-3376        .model-pick__menu -> padding 5、1px var(--border)、
//                                   var(--radius-lg)=12、background var(--bg-elevated)、
//                                   box-shadow var(--shadow)、bottom: calc(100% + 8px)
//   styles/app.css:3387-3395        right: 0、min-width 248、max-width 360、width max-content、
//                                   max-height 340
//   redesign/model-panel.css:105-110 .cf-mp__list -> 列表自己滚动
//   redesign/model-panel.css:111-125 .cf-mp__ghead -> padding 9px 8px 3px（首组 padding-top 4px）、
//                                   字号 11.5px、color var(--fg-subtle)
//                                   注：Qt 的 font.pixelSize 只收整数，11.5px 无法表达。实测
//                                   8.625pt 落 11px（墨迹 y12..21 共 10 行、宽 52），8.75pt 落 12px
//                                   但整体上移 1px；取 12px + y6 后墨迹 y12..24（13 行）与 deva
//                                   同带，宽 57 比 deva 的 55 多 2px（字形度量残余，见报告 §4.9）。
//   styles/app.css:3418-3438        .model-pick__item -> gap 8、padding 7px 8px、13px、var(--fg)；
//                                   :hover 用 var(--bg-hover)；.is-active 转 var(--accent) + 600
//   redesign/model-panel.css:127-131 .cf-mp__check -> 固定占位宽 14px（选中与否行宽一致）
//   styles/app.css:3452-3455        .model-pick__check -> 14px、color var(--accent)
//   styles/app.css:3456-3461        .model-pick__empty -> padding 10px 8px、12px、--fg-subtle、居中
//   redesign/model-panel.css:133-143 .cf-mp__eftext / .cf-mp__efhint -> 思考等级每项两行
//                                   （名字 13px + 说明 11.5px var(--fg-subtle)）
//
// 实测核对（out/latest-parity/deva/model-picker-deva.png）：面板外框 x 847..1094（248 宽）、
// y 688..752（65 高）；分组标题文字 y 700..712；模型行文字 y 727..739（accent、600）；
// ✓ 在 x 1069..1078 / y 729..736。
import QtQuick
import "."

Item {
    id: root

    // "model" = 模型列表；"thinking" = 思考等级；空串 = 不渲染。
    property string mode: "model"
    // 模型分组：[{id, name, models:[{id, name}]}]，由 Python `modelMenuGroups()` 投影。
    property var groups: []
    // 当前生效模型 "providerId:modelId"，用于画勾与 accent 色。
    property string activeRef: ""
    // 思考等级菜单：{title, options:[{level,name,hint}], current}，由 `effortMenu()` 投影。
    property var effortMenu: ({})
    // 没有可选模型时的文案（原版 `chat.noModel`，由 Python 投影）。
    property string emptyText: ""

    signal picked(string providerId, string modelId)
    signal effortPicked(string level)

    // 量宽用隐藏文本：面板宽度取「最长一行 + 内边距」，再夹到原版的 248..360。
    Text {
        id: measure
        visible: false
        text: {
            var widest = ""
            if (root.mode === "thinking") {
                var opts = (root.effortMenu && root.effortMenu.options) || []
                for (var i = 0; i < opts.length; i++) {
                    var n = String(opts[i].name || "")
                    var h = String(opts[i].hint || "")
                    if (n.length > widest.length) widest = n
                    if (h.length > widest.length) widest = h
                }
                return widest
            }
            var rows = root.groups || []
            for (var g = 0; g < rows.length; g++) {
                var label = String(rows[g].name || rows[g].id || "")
                if (label.length > widest.length) widest = label
                var ms = rows[g].models || []
                for (var k = 0; k < ms.length; k++) {
                    var name = String(ms[k].name || ms[k].id || "")
                    if (name.length > widest.length) widest = name
                }
            }
            return widest
        }
        font.family: Theme.sansFamily
        font.pixelSize: 13
        font.weight: 600
    }

    readonly property bool empty: mode === "model" && (groups || []).length === 0
    // 行内容宽 = 8 左内边距 + 文本 + 8 间距 + 14 勾选位 + 8 右内边距；
    // 面板再各加 5px padding + 1px border（styles/app.css:3367-3376）＝ +50。
    readonly property real panelWidth: Math.max(248, Math.min(360, measure.implicitWidth + 38 + 12))

    implicitWidth: panel.width
    implicitHeight: panel.height

    SoftShadow {
        id: panelShadow
        target: panel
        // 实测：Qt Canvas 的同名 blur 尾部比 Chrome 的 CSS `0 6px 24px` 更宽，
        // 面板上沿外多出约 4px 淡影（deva 首行非白 y=672，blur 24 时 y=668）。
        // 收到 20 后上沿起点与 deva 对齐。
        blur: Theme.dark ? 26 : 20
    }

    Rectangle {
        id: panel
        objectName: "pickerPanel"
        width: root.panelWidth
        // 模型态：border 2 + padding 10 + 分组标题 26 + 每行 27 + 组间分隔 9（或空态 40）。
        // 思考等级态：border 2 + padding 10 + 每行 44。
        height: root.mode === "thinking"
                ? 2 + 10 + 44 * (((root.effortMenu && root.effortMenu.options) || []).length || 1)
                : (root.empty ? 2 + 10 + 40
                              : 2 + 10 + 26 + 27 * root.visibleRowCount + 9 * root.groupGapCount)
        radius: Theme.radiusLg
        color: Theme.bgElevated
        border.width: 1
        border.color: Theme.border

        // 空态：styles/app.css:3456-3461（padding 10px 8px、12px、居中）
        Item {
            objectName: "pickerEmpty"
            visible: root.empty
            x: 5
            y: 5
            width: parent.width - 10
            height: 40
            Text {
                width: parent.width
                anchors.centerIn: parent
                text: root.emptyText
                color: Theme.fgSubtle
                font.family: Theme.sansFamily
                font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // ── 模型列表 ────────────────────────────────────────────────
        Column {
            id: modelList
            objectName: "modelList"
            visible: root.mode === "model" && !root.empty
            // 原版是 border-box：内容起点 x = 1px border + 5px padding = 6
            // （styles/app.css:3370-3371）。纵向保持 5 是因为 Qt 的文字基线另有 1px 偏移，
            // 实测 y=5 时行文字墨迹 y727..739 与 deva 逐行一致。
            x: 6
            y: 5

            Repeater {
                model: root.groups || []
                delegate: Column {
                    id: group
                    required property var modelData
                    required property int index
                    width: panel.width - 12

                    // `styles/app.css:3401-3405`：`.model-pick__group + .model-pick__group`
                    // margin-top 4 + padding-top 4 + border-top 1px = 9px；分隔线画在距组顶 4px 处。
                    Item {
                        visible: group.index > 0
                        width: parent.width
                        height: visible ? 9 : 0
                        Rectangle {
                            y: 4
                            width: parent.width
                            height: 1
                            color: Theme.border
                        }
                    }

                    // 分组标题（redesign/model-panel.css:111-125）：首组 padding-top 4、其余 9，
                    // 下 padding 3，行盒 26；实测文字墨迹 y 700..712，在盒内基本居中。
                    Item {
                        width: parent.width
                        height: 26
                        Text {
                            objectName: "groupHead" + group.index
                            x: 8
                            // CSS 的 ghead 是 `padding: 4px 8px 3px`（首组）+ 行盒，文字并非在盒内
                            // 垂直居中；这里保留 26 的盒高（总高与行起点因此和原版一致），
                            // 但文字从左上角起排：y=6 时墨迹落在 y700..712，与原版逐行相同。
                            y: 6
                            width: parent.width - 16
                            text: String(group.modelData.name || group.modelData.id || "")
                            color: Theme.fgSubtle
                            font.family: Theme.sansFamily
                            // 原版 CSS 是 11.5px（model-panel.css:116）：Qt 的 pixelSize 只收整数，
                            // 11.5px 不可表达。8.625pt 落 11px（只有 10 行墨迹、宽 52，明显偏小）；
                            // 8.75pt / 12px 落 12px，配 y=6 后墨迹 y12..24 与 deva 同带，
                            // 宽 57 比 deva 的 55 多 2px（字形度量残余）。
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }

                    Repeater {
                        model: (group.modelData.models || [])
                        delegate: Rectangle {
                            id: row
                            required property var modelData
                            required property int index
                            // 外层分组在闭包里可见为 group（id 可跨层级引用）。
                            readonly property bool on: root.activeRef ===
                                                       (String(group.modelData.id || "") + ":" +
                                                        String(row.modelData.id || ""))
                            objectName: "modelRow" + group.index + "_" + index
                            width: parent.width
                            height: 27
                            radius: Theme.radiusSm
                            color: rowHover.hovered ? Theme.bgHover : "transparent"

                            Text {
                                x: 8
                                width: parent.width - 8 - 8 - 14 - 8
                                anchors.verticalCenter: parent.verticalCenter
                                text: String(row.modelData.name || row.modelData.id || "")
                                color: row.on ? Theme.accent : Theme.fg
                                font.family: Theme.sansFamily
                                font.pixelSize: 13
                                font.weight: row.on ? 600 : 400
                                elide: Text.ElideRight
                            }
                            // 勾选位：固定 14px 宽（redesign/model-panel.css:127-131）
                            Item {
                                anchors.right: parent.right
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                width: 14
                                height: 14
                                Icon {
                                    visible: row.on
                                    anchors.fill: parent
                                    name: IconData.check
                                    size: 14
                                    color: Theme.accent
                                }
                            }
                            HoverHandler { id: rowHover }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.picked(String(group.modelData.id || ""),
                                                       String(row.modelData.id || ""))
                            }
                        }
                    }
                }
            }
        }

        // ── 思考等级列表 ────────────────────────────────────────────
        Column {
            id: thinkingList
            objectName: "thinkingList"
            visible: root.mode === "thinking"
            // 与模型列表同一套 border-box 内缩（1px border + 5px padding）。
            x: 6
            y: 5
            readonly property var options: (root.effortMenu && root.effortMenu.options) || []
            readonly property string current: (root.effortMenu && root.effortMenu.current)
                                              ? String(root.effortMenu.current) : "default"

            Repeater {
                model: thinkingList.options
                delegate: Rectangle {
                    id: efRow
                    required property var modelData
                    required property int index
                    readonly property bool on: thinkingList.current === String(efRow.modelData.level)
                    objectName: "efRow" + index
                    width: panel.width - 12
                    height: 44
                    radius: Theme.radiusSm
                    color: efHover.hovered ? Theme.bgHover : "transparent"

                    Column {
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 1
                        Text {
                            text: String(efRow.modelData.name || "")
                            color: efRow.on ? Theme.accent : Theme.fg
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                            font.weight: efRow.on ? 600 : 400
                        }
                        Text {
                            text: String(efRow.modelData.hint || "")
                            color: Theme.fgSubtle
                            font.family: Theme.sansFamily
                            font.pointSize: 8.625
                        }
                    }
                    Item {
                        anchors.right: parent.right
                        anchors.rightMargin: 8
                        anchors.verticalCenter: parent.verticalCenter
                        width: 14
                        height: 14
                        Icon {
                            visible: efRow.on
                            anchors.fill: parent
                            name: IconData.check
                            size: 14
                            color: Theme.accent
                        }
                    }
                    HoverHandler { id: efHover }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.effortPicked(String(efRow.modelData.level))
                    }
                }
            }
        }
    }

    // 模型态的行数（面板高度按它算）。分组标题各占 1 块 26，组间再占 9。
    readonly property int groupGapCount: Math.max(0, (groups || []).length - 1)
    readonly property int visibleRowCount: {
        var rows = groups || []
        var n = 0
        for (var i = 0; i < rows.length; i++)
            n += (rows[i].models || []).length
        return n
    }
}
