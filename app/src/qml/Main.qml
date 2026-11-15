// 主壳：按原版 Deva 的真实渲染逐区对位（几何全部来自 CDP 实测，见
// out/qml-shell/dom/*.json 与 out/qml-shell/parity/SPEC.md）。
//
// 栅格（1280×820，实测）：
//   图标栏  x 0–55    宽 56   bg #f0f0f2  右边框 1px #e6e6ea
//   会话栏  x 56–355  宽 300  bg #f7f7f8  右边框 1px #e6e6ea
//   正文区  x 356–1279         bg #ffffff；正文列 780 居中（x 428–1207），
//          消息行 grid 32px + 12px gap + 696px，正文字块 x 488、宽 696
// 正文由 Python 渲染进 QTextDocument（markdown 层是唯一真相源），QML 只承载。
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "."

ApplicationWindow {
    id: window
    visible: true
    width: 1280
    height: 820
    minimumWidth: 940
    minimumHeight: 600
    title: "Deva"
    color: Theme.bg

    // ── Python 注入的状态 ─────────────────────────────────────────────
    property var sessions: []
    property string activeId: ""
    property string activeTitle: ""
    property string activePersona: "Deva"
    property bool busy: false
    property string status: ""
    // 页名：由 Python 按环境变量选择要呈现的界面状态（设置页/搜索等，见 qml_shell.py）。
    property string page: "chat"
    property bool dark: Theme.dark
    property bool settingsOpen: page === "settings-general" || page === "settings-models"
                              || page === "settings-extensions" || page === "settings-about"
    property string settingsPane: page === "settings-about" ? "about"
                                : page === "settings-models" ? "models"
                                : page === "settings-extensions" ? "extensions" : "general"
    property bool searchActive: page === "search-open" || page === "search-results"
                                || page === "search-none"
    property string searchQuery: page === "search-results" ? "00"
                               : page === "search-none" ? "zzz" : ""
    property bool modelPickerOpen: page === "model-picker"
    // 交互态页面：hover 指定行、右键菜单、删除确认框
    property int forceHoverRow: page === "hover-thread" ? 1 : -1
    property bool ctxOpen: page === "ctx-menu" || page === "delete-confirm"
    property bool confirmOpen: page === "delete-confirm"

    // 深浅主题：Python 侧把 config.json 的 theme 解析成 bool，QML 用 Binding 写进
    // Theme 单例（单例的 property 不能从 Python 直接 setProperty，实测落不下去）。
    Binding { target: Theme; property: "dark"; value: shellBridge ? shellBridge.darkMode : false }

    // 输入区：true 时占位文案与模型名同步原版（原版就是这个形状）。
    property string modelLabel: "deepseek-v4.1-flash"
    property string effortLabel: "Default"

    // ── 图标栏 ────────────────────────────────────────────────────────
    component RailButton: Rectangle {
        id: btn
        signal clicked()
        property string iconName
        property bool active: false
        property bool dim: false
        width: 40
        height: 40
        radius: Theme.radius
        color: active ? Theme.bgActive
                      : railHover.hovered ? Theme.bgHover
                                          : "transparent"
        Icon {
            anchors.centerIn: parent
            name: btn.iconName
            // 原版图标 20px（.cf-navbtn svg{width:20px} → 实测外框 24 内 20 可见）
            size: 20
            color: btn.active ? Theme.accent : Theme.fgSubtle
            opacity: btn.dim ? 0.7 : 1
        }
        HoverHandler { id: railHover }
        MouseArea {
            anchors.fill: parent
            onClicked: btn.clicked()
        }
        // 选中项左侧 3×18 的强调条：原版 ::before{left:-8px;width:3px;height:18px}
        Rectangle {
            visible: btn.active
            x: -8
            y: (btn.height - 18) / 2
            width: 3
            height: 18
            radius: 2
            color: Theme.accent
        }
    }

    Rectangle {
        id: rail
        x: 0
        y: 0
        width: Theme.railWidth
        height: parent.height
        color: Theme.bgInset

        Rectangle {
            anchors.right: parent.right
            width: 1
            height: parent.height
            color: Theme.border
        }

        // 头像按钮：实测外框 38×38 于 (8.5, 20)，内部 34×34 的圆。
        Item {
            id: meBtn
            x: 9
            y: 20
            width: 38
            height: 38
            Avatar {
                anchors.centerIn: parent
                persona: "user"
                size: 34
            }
        }

        Column {
            x: 8
            y: 70
            spacing: 4
            RailButton { iconName: IconData.messageCircle; active: true }
            RailButton { iconName: IconData.users }
            RailButton { iconName: IconData.alarmClock }
        }

        Column {
            x: 8
            y: 724
            spacing: 4
            RailButton { iconName: IconData.bot }
            RailButton {
                iconName: IconData.cog
                onClicked: window.page = "settings-general"
            }
        }
    }

    // ── 会话栏 ────────────────────────────────────────────────────────
    Rectangle {
        id: side
        x: Theme.railWidth
        y: 0
        width: Theme.sideWidth
        height: parent.height
        color: Theme.bgPanel

        Rectangle {
            anchors.right: parent.right
            width: 1
            height: parent.height
            color: Theme.border
        }

        // 顶部：搜索框 (68,12,235×32) + 加号按钮 (311,12,32×32)
        Rectangle {
            id: searchBox
            x: 12
            y: 12
            width: 235
            height: 32
            radius: Theme.radius
            color: Theme.bg
            border.width: 1
            border.color: window.searchActive ? Theme.borderStrong : Theme.border
            // 左侧 26×26 的过滤按钮（实测 x 71 → 相对 3），内部放大镜 15px
            Icon {
                x: 3 + (26 - 15) / 2
                y: (parent.height - 15) / 2
                name: IconData.search
                size: 15
                color: Theme.fgSubtle
            }
            TextInput {
                id: searchInput
                objectName: "searchInput"
                x: 35
                width: parent.width - 35 - 8
                y: (parent.height - height) / 2
                height: 16
                text: window.searchQuery
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 12
                selectionColor: Theme.bgSelected
                selectedTextColor: Theme.fg
                clip: true
                readOnly: !window.searchActive
                onTextChanged: if (window.searchActive) window.searchQuery = text
            }
            Text {
                visible: searchInput.text.length === 0
                x: 35
                anchors.verticalCenter: parent.verticalCenter
                text: "Search chats"
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }
            MouseArea {
                anchors.fill: parent
                onClicked: {
                    window.searchActive = true
                    searchInput.forceActiveFocus()
                }
            }
        }

        Rectangle { // 加号按钮
            id: addBtn
            x: 255
            y: 12
            width: 32
            height: 32
            radius: Theme.radius
            color: Theme.bg
            border.width: 1
            border.color: Theme.border
            Icon {
                anchors.centerIn: parent
                name: IconData.plus
                size: 16
                color: Theme.fgMuted
            }
            MouseArea {
                anchors.fill: parent
                onClicked: shellBridge.newSession()
            }
        }

        // 会话列表：行宽 275（栏 300 - 左右各 8 + 行内 12×2 的视觉边距实测为 64..339）
        ListView {
            id: sessionList
            objectName: "sessionList"
            x: 8
            y: 56
            width: 283
            height: parent.height - 56 - 8
            clip: true
            model: window.sessions
            spacing: 0
            boundsBehavior: Flickable.StopAtBounds
            // 长列表两张页面：滚到中途 / 滚到底（原版是真实滚轮事件）。
            onContentHeightChanged: window.applyListScroll()
            Component.onCompleted: window.applyListScroll()

            delegate: ThreadRow {
                required property int index
                required property var modelData
                width: ListView.view.width
                title: modelData.title || ""
                time: modelData.time || ""
                persona: modelData.persona || "general"
                ownerName: modelData.personaName || "Deva"
                active: modelData.id === window.activeId
                forceHover: index === window.forceHoverRow
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: window.activate(modelData.id)
                }
            }
        }

        // 空状态：原版此处只有一行 "No conversations"（实测 x 152–257, y 79–93）
        Text {
            visible: window.sessions.length === 0
            x: 96
            y: 79
            text: "No conversations"
            color: Theme.fgMuted
            font.family: Theme.sansFamily
            font.pixelSize: 13
        }
    }

    // ── 正文区 ────────────────────────────────────────────────────────
    Item {
        id: conv
        x: Theme.railWidth + Theme.sideWidth
        y: 0
        width: parent.width - x
        height: parent.height

        // 顶部 26px 的会话头：下缘 1px 分隔线横贯 x 356–1183（实测 828px 宽）
        Item {
            id: head
            x: 0
            y: 0
            width: parent.width - 96
            height: 27
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
            // 标题按钮：原版 .cf-idbtn 只有名字，padding 5/10
            Text {
                anchors.left: parent.left
                anchors.leftMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                text: window.activePersonaName
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 13
                font.weight: 600
            }
        }

        // 空状态：中列 "Start a conversation" + 提示（实测 title y 393.25 居中）
        Column {
            visible: window.sessions.length === 0 && !window.settingsOpen
            anchors.horizontalCenter: parent.horizontalCenter
            y: 388
            spacing: 6
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Start a conversation"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 20
                font.weight: 700
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Pick a persona — tap its avatar to begin"
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 13
            }
        }

        // 消息区：780 列居中，正文 696 宽，左头像 32。
        Flickable {
            id: bodyScroll
            objectName: "bodyScroll"
            visible: window.sessions.length > 0 && !window.settingsOpen
            x: (parent.width - 780) / 2
            y: 27
            width: 780
            height: parent.height - 27 - 175
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: width
            contentHeight: bodyView.implicitHeight + 40
            topMargin: 20

            TextEdit {
                id: bodyView
                objectName: "bodyView"
                // 消息头（头像列 32 + gap 12）之外是 696 的正文块
                x: 56
                y: 20
                width: 696
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                textFormat: TextEdit.RichText
                font.family: Theme.sansFamily
                font.pixelSize: Math.round(Theme.bodyPx)
                color: Theme.fg
                selectionColor: Theme.bgSelected
                selectedTextColor: Theme.fg
                Component.onCompleted: {
                    shellBridge.attach(textDocument)
                    // focus-composer 页面：原版是真实点进输入框，这里让输入框拿到焦点。
                    if (window.page === "focus-composer")
                        inputField.forceActiveFocus()
                }
            }
        }

        // ── 输入区 ────────────────────────────────────────────────────
        // 卡片实测：(428,658) 780×146，padding 12，边框 #d5d5db，圆角 12，阴影 0 6 24。
        Rectangle {
            id: composer
            objectName: "composer"
            visible: window.sessions.length > 0 && !window.settingsOpen
            x: (parent.width - 780) / 2
            y: parent.height - 162
            width: 780
            height: 146
            radius: Theme.radiusLg
            color: Theme.bg
            border.width: 1
            border.color: Theme.borderStrong

            // 草稿区：y 671（卡片内 13），高 80，占位 13.5px
            TextArea {
                id: inputField
                objectName: "inputField"
                x: 13
                y: 13
                width: parent.width - 26
                height: 80
                padding: 2
                placeholderText: "Message " + (window.activePersonaName || "Assistant") + "…"
                placeholderTextColor: Theme.fgSubtle
                color: Theme.fg
                font.family: Theme.sansFamily
                // 13.5px → QML pixelSize 取整会变成 13；用 pointSize(10.125pt) 得真实 13.5
                font.pointSize: 10.125
                wrapMode: TextArea.Wrap
                background: null
                enabled: !window.busy
                Keys.onPressed: function (event) {
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                        if (event.modifiers & Qt.ShiftModifier) {
                            event.accepted = false
                        } else {
                            window.submit()
                            event.accepted = true
                        }
                    }
                }
            }

            // 工具栏：y 759（卡片内 101），高 32
            Item {
                id: toolbar
                x: 13
                y: 101
                width: parent.width - 26
                height: 32

                // 附件图标按钮 30×30
                Rectangle {
                    x: 0
                    width: 30
                    height: 30
                    y: (parent.height - height) / 2
                    radius: Theme.radiusSm
                    color: clipHover.hovered ? Theme.bgHover : "transparent"
                    Icon {
                        anchors.centerIn: parent
                        name: IconData.paperclip
                        size: 16
                        color: Theme.fgSubtle
                    }
                    HoverHandler { id: clipHover }
                }

                // 挂载工作区 chip
                Row {
                    id: mountChip
                    x: 34
                    y: (parent.height - 30) / 2
                    height: 30
                    spacing: 0
                    Item {
                        width: 15
                        height: 30
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: IconData.folder
                            size: 15
                            color: Theme.fgSubtle
                        }
                    }
                    Text {
                        text: "Mount workspace"
                        anchors.verticalCenter: undefined
                        y: (30 - height) / 2
                        color: Theme.fgSubtle
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        rightPadding: 8
                        leftPadding: 9
                    }
                }

                // 右侧：模型 chip + 强度 chip + 发送
                Rectangle {
                    id: sendBtn
                    anchors.right: parent.right
                    width: 69
                    height: 32
                    y: 0
                    radius: Theme.radius
                    color: window.busy || inputField.text.trim() === ""
                           ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45)
                           : Theme.accent
                    Text {
                        anchors.centerIn: parent
                        text: "Send"
                        color: Theme.accentFg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.weight: 600
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !window.busy && inputField.text.trim() !== ""
                        onClicked: window.submit()
                    }
                }

                Rectangle {
                    id: effortChip
                    anchors.right: sendBtn.left
                    anchors.rightMargin: 4
                    width: 94
                    height: 28
                    y: 2
                    radius: Theme.radius
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.border
                    Icon {
                        x: 5
                        anchors.verticalCenter: parent.verticalCenter
                        name: IconData.sparkles
                        size: 13
                        color: Theme.fgMuted
                    }
                    Text {
                        x: 23
                        anchors.verticalCenter: parent.verticalCenter
                        text: window.effortLabel
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        font.weight: 500
                    }
                    Icon {
                        anchors.right: parent.right
                        anchors.rightMargin: 5
                        anchors.verticalCenter: parent.verticalCenter
                        name: IconData.chevronDown
                        size: 13
                        color: Theme.fgMuted
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: window.modelPickerOpen = !window.modelPickerOpen
                    }
                }

                Rectangle {
                    id: modelChip
                    anchors.right: effortChip.left
                    anchors.rightMargin: 4
                    width: 172
                    height: 28
                    y: 2
                    radius: Theme.radius
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.border
                    // 状态点 7px #d97757
                    Rectangle {
                        x: 9
                        anchors.verticalCenter: parent.verticalCenter
                        width: 7
                        height: 7
                        radius: 3.5
                        color: Theme.statusDot
                    }
                    Text {
                        x: 21
                        anchors.verticalCenter: parent.verticalCenter
                        text: window.modelLabel
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        font.weight: 500
                    }
                    Icon {
                        anchors.right: parent.right
                        anchors.rightMargin: 5
                        anchors.verticalCenter: parent.verticalCenter
                        name: IconData.chevronDown
                        size: 13
                        color: Theme.fgMuted
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: window.modelPickerOpen = !window.modelPickerOpen
                    }
                }
            }
        }
    }

    // ── 设置浮层 ──────────────────────────────────────────────────────
    SettingsModal {
        anchors.fill: parent
        visible: window.settingsOpen
        pane: window.settingsPane
        onClose: window.page = "chat"
        onPaneRequested: function (name) { window.page = "settings-" + name }
    }

    // ── 模型/强度下拉 ─────────────────────────────────────────────────
    ModelPicker {
        visible: window.modelPickerOpen
        x: 700
        y: 542
        onClose: window.modelPickerOpen = false
    }

    // ── 函数 ──────────────────────────────────────────────────────────
    function activate(id) {
        if (!id || id === window.activeId)
            return
        shellBridge.openSession(id)
    }

    function submit() {
        var text = inputField.text
        if (window.busy || text.trim() === "")
            return
        if (shellBridge.send(text))
            inputField.text = ""
    }

    // 长列表页面状态：原版是真实滚轮事件，这里按同一目标位置摆好列表。
    function applyListScroll() {
        if (window.page === "long-bottom")
            sessionList.positionViewAtEnd()
        else if (window.page === "long-mid")
            sessionList.contentY = Math.max(0, (sessionList.contentHeight - sessionList.height) * 0.45)
    }

    // 右键菜单：原版 .cf-menu 实测 (165,88) 175×124，圆角 10，1px #e6e6ea，四项各 31。
    Rectangle {
        id: ctxMenu
        objectName: "ctxMenu"
        visible: window.ctxOpen
        x: 165
        y: 88
        width: 175
        height: 124
        radius: 10
        color: Theme.bg
        border.width: 1
        border.color: Theme.border
        z: 40

        Column {
            x: 5
            y: 5
            spacing: 0
            Repeater {
                model: [
                    { label: "New chat", icon: IconData.plus, danger: false },
                    { label: "Rename", icon: IconData.pencil, danger: false },
                    { label: "Archive", icon: IconData.archive, danger: false },
                    { label: "Delete conversation", icon: IconData.trash2, danger: true }
                ]
                delegate: Rectangle {
                    required property var modelData
                    width: 165
                    height: 28
                    radius: Theme.radiusSm
                    color: "transparent"
                    Row {
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: modelData.icon
                            size: 14
                            color: modelData.danger ? Theme.danger : Theme.fg
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            color: modelData.danger ? Theme.danger : Theme.fg
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
    }

    // 删除确认框：背板 42%，弹窗 420×180 居中偏上（实测 430,320），标题 15/700。
    Item {
        id: confirmLayer
        objectName: "confirmLayer"
        visible: window.confirmOpen
        anchors.fill: parent
        z: 60
        Rectangle {
            anchors.fill: parent
            color: Theme.backdrop
        }
        Rectangle {
            x: 430
            y: 320
            width: 420
            height: 180
            radius: Theme.radiusLg
            color: Theme.bg
            Text {
                x: 20
                y: 18
                width: parent.width - 40
                wrapMode: Text.WordWrap
                text: "Delete conversation “" + window.activeTitle + "”?"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }
            Text {
                x: 20
                y: 74
                width: parent.width - 40
                wrapMode: Text.WordWrap
                text: "This conversation and all its messages will be permanently removed. This cannot be undone."
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 13
                lineHeight: 1.5
            }
            Text {
                id: cancelText
                x: 266
                y: 135
                text: "Cancel"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 13
            }
            Rectangle {
                x: 330
                y: 127
                width: 70
                height: 30
                radius: Theme.radiusSm
                color: Theme.danger
                Text {
                    anchors.centerIn: parent
                    text: "Delete"
                    color: "#ffffff"
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 600
                }
            }
        }
    }

    // 当前会话的头像角色（用于输入框占位文案 "Message <name>…"）
    readonly property string activePersonaName: {
        for (var i = 0; i < sessions.length; i++)
            if (sessions[i].id === activeId)
                return sessions[i].personaName || "Assistant"
        return "Assistant"
    }
}
