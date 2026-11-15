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

    Component {
        id: extensionsPane
        Item {
            Text {
                x: 20
                y: 16
                text: "Extensions"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }
            Text {
                x: 20
                y: 55
                width: parent.width - 40
                text: shellBridge ? shellBridge.extensionsSummary() : ""
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 13
                wrapMode: Text.WordWrap
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
