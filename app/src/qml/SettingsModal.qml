// 设置浮层：几何逐项取自原版实测（out/qml-shell/dom/settings-general.json）：
//   背板 #000 42%；弹窗 720×560 居中（实测 x280 y130），bg #f7f7f8，圆角 12，1px #e6e6ea，阴影 0 6 24；
//   头部 padding 12/16 + 下缘 1px，标题 14/700，关闭按钮 28×28 于右侧；
//   主体 grid 168px + 1fr；左导航 bg #f0f0f2，右边框 1px，padding 12，项 143×31 radius 8；
//   右窗格 padding 16/20，标题 15/700，分组卡 510 宽 radius 12 1px 边框，行 padding 12/14 + 行间 1px。
import QtQuick
import QtQuick.Controls
import "."

Item {
    id: root
    property string pane: "general"
    signal close()
    signal paneRequested(string name)

    // 背板（点击关闭 = 原版行为）
    Rectangle {
        anchors.fill: parent
        color: Theme.backdrop
    }

    Rectangle {
        id: box
        objectName: "settingsModal"
        width: 720
        height: 560
        anchors.centerIn: parent
        radius: Theme.radiusLg
        color: Theme.bgPanel
        border.width: 1
        border.color: Theme.border

        // 阴影：QML 没有 box-shadow，用一层外扩半透明矩形近似（原版 0 6 24, .12）。
        Rectangle {
            z: -1
            anchors.fill: parent
            anchors.margins: -6
            radius: Theme.radiusLg + 4
            color: Theme.shadow
            opacity: 0.5
        }

        // ── 头部 ──────────────────────────────────────────────────────
        Item {
            id: head
            x: 1
            y: 1
            width: parent.width - 2
            height: 53
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
            Text {
                x: 16
                anchors.verticalCenter: parent.verticalCenter
                text: "Settings"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 14
                font.weight: 700
            }
            Rectangle {
                id: closeBtn
                width: 28
                height: 28
                anchors.right: parent.right
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                radius: Theme.radiusSm
                color: closeHover.hovered ? Theme.bgHover : "transparent"
                Icon {
                    anchors.centerIn: parent
                    name: IconData.x
                    size: 15
                    color: Theme.fgSubtle
                }
                HoverHandler { id: closeHover }
                MouseArea {
                    anchors.fill: parent
                    onClicked: root.close()
                }
            }
        }

        // ── 主体：168 + 剩余 ──────────────────────────────────────────
        Item {
            id: body
            x: 1
            y: 54
            width: parent.width - 2
            height: parent.height - 55

            // 左导航
            Rectangle {
                id: nav
                width: 168
                height: parent.height
                color: Theme.bgInset
                Rectangle {
                    anchors.right: parent.right
                    width: 1
                    height: parent.height
                    color: Theme.border
                }

                Column {
                    x: 12
                    y: 12
                    spacing: 2
                    Repeater {
                        model: [
                            { key: "general", label: "General", icon: IconData.settings2 },
                            { key: "models", label: "Models", icon: IconData.blocks },
                            { key: "extensions", label: "Extensions", icon: IconData.cog },
                            { key: "about", label: "About", icon: IconData.info }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            width: 143
                            height: 31
                            radius: Theme.radius
                            color: modelData.key === root.pane ? Theme.bgActive
                                  : navHover.hovered ? Theme.bgHover
                                                     : "transparent"
                            Row {
                                x: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8
                                Icon {
                                    anchors.verticalCenter: parent.verticalCenter
                                    name: modelData.icon
                                    size: 15
                                    color: modelData.key === root.pane ? Theme.fg : Theme.fgSubtle
                                }
                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    color: modelData.key === root.pane ? Theme.fg : Theme.fgMuted
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    font.weight: modelData.key === root.pane ? 600 : 400
                                }
                            }
                            HoverHandler { id: navHover }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.paneRequested(modelData.key)
                            }
                        }
                    }
                }
            }

            // 右窗格
            Item {
                id: paneArea
                x: 169
                y: 0
                width: parent.width - 169
                height: parent.height

                Loader {
                    anchors.fill: parent
                    sourceComponent: root.pane === "about" ? aboutPane
                                   : root.pane === "models" ? modelsPane
                                   : root.pane === "extensions" ? extensionsPane
                                   : generalPane
                }
            }
        }
    }

    // ── General：语言 / 主题 / 字号（三行分段控件，实测宽 510 的设置卡）─────
    component SetRow: Item {
        id: row
        property string label: ""
        property var options: []
        property int current: 0
        property var keys: []
        property int rowHeight: 55
        signal picked(int index)

        width: parent ? parent.width : 508
        height: rowHeight
        Rectangle {
            anchors.top: parent.top
            visible: row.parent && row.parent.children[0] !== row
            width: parent.width
            height: 1
            color: Theme.border
        }
        Text {
            x: 14
            anchors.verticalCenter: parent.verticalCenter
            text: row.label
            color: Theme.fg
            font.family: Theme.sansFamily
            font.pixelSize: 13
            font.weight: 600
        }
        // 分段控件：bg #f0f0f2、1px #e6e6ea、padding 2、gap 2；选中项白底 6px 圆角、600 字重
        Rectangle {
            id: seg
            anchors.right: parent.right
            anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            width: segRow.implicitWidth + 2 * 2 + 2
            height: 30
            radius: Theme.radius
            color: Theme.bgInset
            border.width: 1
            border.color: Theme.border
            Row {
                id: segRow
                anchors.centerIn: parent
                spacing: 2
                Repeater {
                    model: row.options
                    delegate: Rectangle {
                        required property int index
                        required property string modelData
                        width: optText.implicitWidth + 24
                        height: 24
                        radius: Theme.radiusSm
                        color: index === row.current ? Theme.bg : "transparent"
                        Text {
                            id: optText
                            anchors.centerIn: parent
                            text: modelData
                            color: index === row.current ? Theme.fg : Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 12
                            font.weight: index === row.current ? 600 : 400
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: row.picked(index)
                        }
                    }
                }
            }
        }
    }

    Component {
        id: generalPane
        Item {
            Rectangle {
                // 原版 cf-set 实测：pane 内 (20, 54.5)，510×169（标题 h2 22.5 + 间距 16）。
                x: 20
                y: 55
                width: parent.width - 40
                height: 169
                radius: Theme.radiusLg
                color: "transparent"
                border.width: 1
                border.color: Theme.border
            }
            Text {
                x: 20
                y: 16
                text: "General"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }
            Column {
                // 行：首行 57、其余 55（原版 cf-set__row 实测），整体贴着卡片内缘。
                x: 21
                y: 56
                width: parent.width - 42
                SetRow {
                    width: parent.width
                    rowHeight: 57
                    label: "Language"
                    options: ["简体中文", "English"]
                    current: shellBridge ? shellBridge.language() === "zh" ? 0 : 1 : 1
                    onPicked: function (i) { shellBridge.setLanguage(i === 0 ? "zh" : "en") }
                }
                SetRow {
                    width: parent.width
                    label: "Theme"
                    options: ["System", "Light", "Dark"]
                    current: shellBridge ? shellBridge.themeIndex() : 1
                    onPicked: function (i) { shellBridge.setTheme(["system", "light", "dark"][i]) }
                }
                SetRow {
                    width: parent.width
                    label: "Text size"
                    options: ["Small", "Default", "Large", "Extra large"]
                    current: shellBridge ? shellBridge.textSizeIndex() : 1
                    onPicked: function (i) { shellBridge.setTextSize(i) }
                }
            }
        }
    }

    // ── Models：真实模型列表来自 config.json 的 models 段 ────────────────
    Component {
        id: modelsPane
        Item {
            Text {
                x: 20
                y: 16
                text: "Models"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }
            ListView {
                x: 20
                y: 55
                width: parent.width - 40
                height: parent.height - 75
                clip: true
                model: shellBridge ? shellBridge.modelRows() : []
                delegate: Rectangle {
                    required property var modelData
                    width: ListView.view.width
                    height: 52
                    radius: Theme.radius
                    color: "transparent"
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.border
                    }
                    Text {
                        x: 4
                        y: 8
                        text: modelData.name
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.weight: 600
                    }
                    Text {
                        x: 4
                        y: 27
                        text: modelData.detail
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                    }
                }
            }
        }
    }

    // ── Extensions：真实技能行（内置三条 + 磁盘技能），几何取自原版实测 ────
    // 原版 SettingsPane.tsx:195-260 + redesign.css `.cf-rows/.cf-setrow/.cf-badge/.cf-switch`：
    //   卡片 pane 内 x=20、宽 510、1px 边框（实测左缘 469 / 右缘 978）；
    //   行 padding 11/14，行间 1px 分隔（实测 y=239/284/329/374，即 45px 行距）；
    //   名字 13/600、徽标 10.5/500 底 inset 全圆角、注记 11/400 subtle、行尾开关 38×22。
    // 旧的 `shellBridge.extensionsSummary()` 在桥里根本不存在（grep 全仓 0 处定义），
    // 运行时抛 TypeError 且整页空白；这里换成真实数据源 `extensionRows()`。
    Component {
        id: extensionsPane
        Item {
            id: extPane
            property var rows: []

            Component.onCompleted: refresh()

            function refresh() {
                rows = shellBridge ? shellBridge.extensionRows() : []
            }

            Text {
                x: 20
                y: 16
                text: "Extensions"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }

            // 空态：原版 `.cf-empty`（padding 20、居中、12px subtle）。
            Text {
                visible: extPane.rows.length === 0
                x: 20
                y: 55
                width: parent.width - 40
                horizontalAlignment: Text.AlignHCenter
                text: shellBridge ? shellBridge.labels().extEmpty : ""
                color: Theme.fgSubtle
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }

            // 行列表：卡片自带 1px 外框，行间用 1px 分隔线（原版 .cf-rows + .cf-setrow）。
            Rectangle {
                visible: extPane.rows.length > 0
                x: 20
                y: 55
                width: parent.width - 40
                height: extColumn.height + 2
                radius: Theme.radiusLg
                color: "transparent"
                border.width: 1
                border.color: Theme.border

                Column {
                    id: extColumn
                    x: 1
                    y: 1
                    width: parent.width - 2

                    Repeater {
                        model: extPane.rows
                        delegate: Item {
                            id: extRow
                            required property var modelData
                            required property int index

                            width: extColumn.width
                            // 原版 `.cf-setrow` 内容盒高 44px，而 `.cf-setrow + .cf-setrow`
                            // 的 border-top 画在盒外，第 2/3 行各多占 1px。实测原版分隔线在
                            // y=284 / 329、末行底边 374；若把分隔线画进 44px 行内，
                            // 每行净内容只剩 43px，第三行底边落到 372、分隔线落到 328（差 2px）。
                            height: 44 + (extRow.index > 0 ? 1 : 0)

                            // 行间分隔线：首行没有（原版 `.cf-setrow + .cf-setrow`）。
                            Rectangle {
                                visible: extRow.index > 0
                                anchors.top: parent.top
                                width: parent.width
                                height: 1
                                color: Theme.border
                            }

                            Row {
                                x: 13
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: extRow.modelData.name
                                    color: Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    font.weight: 600
                                }
                                // 类型徽标：底 inset、1px 边框、全圆角、上下 1px / 左右 7px
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: badgeText.implicitWidth + 14
                                    height: badgeText.implicitHeight + 2
                                    radius: Theme.radiusFull
                                    color: Theme.bgInset
                                    border.width: 1
                                    border.color: Theme.border
                                    Text {
                                        id: badgeText
                                        anchors.centerIn: parent
                                        text: extRow.modelData.badge
                                        color: Theme.fgMuted
                                        font.family: Theme.sansFamily
                                        // 原版 10.5px；QML 的 pixelSize 只收 int，四舍五入到 11。
                                        font.pixelSize: 11
                                        font.weight: 500
                                    }
                                }
                                Text {
                                    visible: extRow.modelData.note !== ""
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: extRow.modelData.note
                                    color: Theme.fgSubtle
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                }
                            }

                            // 开关：38×22 胶囊，开启=accent、滑块白 18 圆 16px 位移；
                            // 内置技能 locked → 整组 0.55 不透明、不可点（原版 `.cf-switch:disabled`）。
                            // 注意：CSS 的 opacity 作用在元素整体（先合成再调透明度），
                            // 所以必须开 layer 把轨道+滑块先画进一张纹理再整体 0.55，
                            // 否则 QML 会逐图元各乘 0.55，白色滑块叠在 accent 轨道上时
                            // 得到 (213,213,244) 而不是原版的 (251,251,251)。
                            Item {
                                id: sw
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 38
                                height: 22
                                opacity: extRow.modelData.builtin ? 0.55 : 1.0
                                layer.enabled: extRow.modelData.builtin

                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.radiusFull
                                    color: extRow.modelData.enabled ? Theme.accent : Theme.bgActive
                                }
                                Rectangle {
                                    x: extRow.modelData.enabled ? 18 : 2
                                    y: 2
                                    width: 18
                                    height: 18
                                    radius: Theme.radiusFull
                                    color: "#ffffff"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    enabled: !extRow.modelData.builtin
                                    onClicked: {
                                        // 无条件重读：写失败时行数据保持原样，开关不会假装翻面。
                                        if (shellBridge) shellBridge.setSkillEnabled(extRow.modelData.id)
                                        extPane.refresh()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── About：56px 渐变图标 + 名称 + 版本 + 检查更新 ─────────────────────
    Component {
        id: aboutPane
        Item {
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 80
                spacing: 10
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 56
                    height: 56
                    radius: 14
                    gradient: Gradient {
                        GradientStop { position: 0; color: "#4F46E5" }
                        GradientStop { position: 1; color: "#7C3AED" }
                    }
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Deva"
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 20
                    font.weight: 700
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "0.1.15"
                    color: Theme.fgSubtle
                    font.family: Theme.sansFamily
                    font.pixelSize: 12
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 120
                    height: 30
                    radius: Theme.radius
                    color: Theme.bgInset
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        anchors.centerIn: parent
                        text: "Check for updates"
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        font.weight: 600
                    }
                }
            }
        }
    }
}
