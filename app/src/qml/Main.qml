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
    // 附件与交付卡（Python 每次 _publish 按当前会话现算）：
    //   attachments: [{name,kind,size,sizeText,thumb,index}]
    //   deliveries:  [{path,name,dir,size,sizeText,openable,missing,toolUseId}]
    property var attachments: []
    property var deliveries: []
    // 输入区待发送的附件（回形针选中后进来；未发送前可直接移除）
    property var pendingFiles: []
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
    // 打开的是哪一个菜单：模型列表 / 思考等级。空串 = 都关着。
    property string pickerMode: page === "model-picker" ? "model" : ""
    // 交互态页面：hover 指定行、右键菜单、删除确认框
    property int forceHoverRow: page === "hover-thread" ? 1 : -1
    // 输入区焦点态：focus-composer 页要让输入卡片真的拿到键盘焦点，
    // 原版此时边框从 #d5d5db 变 #5b5bd6（CDP 实测 border-color）。
    property bool composerFocused: page === "focus-composer"
    property bool ctxOpen: page === "ctx-menu" || page === "delete-confirm"
    property bool confirmOpen: page === "delete-confirm"

    // 深浅主题：Python 侧把 config.json 的 theme 解析成 bool，QML 用 Binding 写进
    // Theme 单例（单例的 property 不能从 Python 直接 setProperty，实测落不下去）。
    Binding { target: Theme; property: "dark"; value: shellBridge ? shellBridge.darkMode : false }

    // 输入区两个贴片的文案：由 Python 按 config.json 的 activeModelId / activeEffort 写入，
    // 点菜单里的选项也写回这里（见 pickModel / pickEffort）。空串时退回下面的静态初值。
    property string modelLabel: "deepseek-v4.1-flash"
    property string effortLabel: ""
    // 当前生效模型（"providerId:modelId"）与思考等级：菜单据此画勾、算支持哪几档。
    property string activeModelRef: ""
    property string activeEffort: "default"
    // 模型菜单的分组（[{id,name,models:[{id,name}]}]）、思考等级菜单（{title,toggle,current,
    // label,options:[{level,name,hint}]}）与输入区/列表文案（chatText）。三者都由 Python 的
    // `_publish()` 按当前配置现算后 setProperty 写进来；这里声明成属性，QML 才有可绑定的槽。
    property var modelGroups: []
    property var effortMenu: ({})
    property var chatText: ({})

    // 列表筛选：搜索框里的词（原版按标题 / 角色名 / 挂载目录 basename 过滤，大小写不敏感）。
    readonly property string searchTerm: window.searchQuery.trim().toLowerCase()
    // 过滤后的会话行；顺序沿用 Python 给的 updatedAt 倒序，不重排。
    readonly property var visibleSessions: {
        var all = window.sessions || []
        var q = window.searchTerm
        if (!q)
            return all
        var out = []
        for (var i = 0; i < all.length; i++) {
            var row = all[i]
            var hay = [row.title, row.personaName, row.focusName]
            var hit = false
            for (var k = 0; k < hay.length; k++) {
                var text = hay[k] ? String(hay[k]).toLowerCase() : ""
                if (text.indexOf(q) >= 0) {
                    hit = true
                    break
                }
            }
            if (hit)
                out.push(row)
        }
        return out
    }

    // 交付卡「复制路径」的短暂反馈：1.2s 后把对勾换回复制图标。
    property string copiedPath: ""
    Timer {
        id: copyReset
        interval: 1200
        onTriggered: window.copiedPath = ""
    }
    // 交付卡动作的真实结果提示：通道返回 false 才弹（原版 chat.deliver.openFailed / reveal 失败）。
    property string actionNotice: ""
    Timer {
        id: noticeReset
        interval: 3200
        onTriggered: window.actionNotice = ""
    }

    // 交付卡右侧 28×28 的动作按钮（打开 / 定位 / 复制路径共用）。
    component CardAction: Rectangle {
        id: act
        signal triggered()
        property string iconName
        property color iconColor: Theme.fgMuted
        width: 28
        height: 28
        radius: Theme.radiusSm
        color: (actMouse.containsMouse && act.enabled) ? Theme.bgHover : "transparent"
        opacity: act.enabled ? 1 : 0.4
        Icon {
            anchors.centerIn: parent
            name: act.iconName
            size: 14
            color: act.iconColor
        }
        MouseArea {
            id: actMouse
            anchors.fill: parent
            enabled: act.enabled
            hoverEnabled: true
            onClicked: act.triggered()
        }
    }

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
            // 左侧 26×26 的筛选按钮：原版对话 tab 这里是 list-filter（不是放大镜），
            // 26×26 命中区、图标 15px 居中（redesign.css `.cf-search__filter`）。
            Item {
                id: filterBtn
                x: 3
                y: (parent.height - 26) / 2
                width: 26
                height: 26
                Icon {
                    anchors.centerIn: parent
                    name: IconData.listFilter
                    size: 15
                    color: Theme.fgSubtle
                }
            }
            TextInput {
                id: searchInput
                objectName: "searchInput"
                x: 35
                width: parent.width - 35 - (clearBtn.visible ? 26 : 8)
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
                text: window.chatText.searchChats || "Search chats"
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }
            // 有检索词才出现的清空按钮：18×18，右侧留 8（原版 `.cf-search__clear`，X 13px）。
            Rectangle {
                id: clearBtn
                objectName: "searchClear"
                visible: searchInput.text.length > 0
                width: 18
                height: 18
                radius: Theme.radiusSm
                anchors.right: parent.right
                anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                color: clearHover.hovered ? Theme.bgHover : "transparent"
                Icon {
                    anchors.centerIn: parent
                    name: IconData.x
                    size: 13
                    color: clearHover.hovered ? Theme.fg : Theme.fgSubtle
                }
                HoverHandler { id: clearHover }
                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        searchInput.text = ""
                        window.searchQuery = ""
                    }
                }
            }
            MouseArea {
                anchors.fill: parent
                // 清空按钮自己处理点击：盖住它那块的鼠标事件不再触发「聚焦」。
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
            model: window.visibleSessions
            spacing: 0
            boundsBehavior: Flickable.StopAtBounds
            // 长列表两张页面：原版同样是滚动位置，但位置由 applyListScroll() 按实测像素摆。
            // 注意 `Component.onCompleted` 时 Python 还没写 page（_select_page 在 initial() 之后），
            // 所以这里只能靠 page 变化触发；onCompleted 保留给 contentHeight 已就绪的场合。
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

        // 空状态：原版 `.cf-empty`（12px / padding 20 / 文本居中）。
        //   没有任何会话        → "No conversations"（实测 x155–256 y80–89）
        //   有会话但筛选无命中  → "No matches"       （实测 x171–240 y80–89，i18n `cf.searchNoResults`）
        // 列表区从 x56 起、宽 283，文本水平居中即落在实测位置。
        Text {
            objectName: "listEmpty"
            visible: window.visibleSessions.length === 0
            x: 8
            y: 68
            width: 283
            horizontalAlignment: Text.AlignHCenter
            text: window.searchTerm !== "" ? (window.chatText.noMatches || "No matches")
                                          : (window.chatText.noSessions || "No conversations")
            color: Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 12
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
            contentHeight: bodyView.y + bodyView.implicitHeight + 24
                            + (cardsCol.visible ? cardsCol.height + 20 : 0)
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
                Component.onCompleted: shellBridge.attach(textDocument)
            }

            // 正文之后：本轮会话的附件贴片（缩略图 + 名称 + 真实体积）与交付卡。
            // 数据全部来自 Python 的 `attachment_rows()` / `delivery_rows()`（落盘会话 + 边车），
            // 这里只画，不自己读盘、不自己算体积。
            Column {
                id: cardsCol
                objectName: "cardsCol"
                x: 56
                y: bodyView.y + bodyView.implicitHeight + 16
                width: 696
                spacing: 12
                visible: window.attachments.length > 0 || window.deliveries.length > 0
                height: visible ? implicitHeight : 0

                Flow {
                    id: attachFlow
                    objectName: "attachFlow"
                    width: parent.width
                    spacing: 8
                    visible: window.attachments.length > 0
                    height: visible ? implicitHeight : 0
                    Repeater {
                        model: window.attachments
                        delegate: Rectangle {
                            required property var modelData
                            width: 210
                            height: 64
                            radius: Theme.radius
                            color: Theme.bgInset
                            border.width: 1
                            border.color: Theme.border

                            Image {
                                visible: (modelData.thumb || "") !== ""
                                x: 8
                                y: 8
                                width: 48
                                height: 48
                                fillMode: Image.PreserveAspectFit
                                source: modelData.thumb || ""
                            }
                            Icon {
                                visible: (modelData.thumb || "") === ""
                                x: 8 + (48 - 20) / 2
                                y: 8 + (48 - 20) / 2
                                name: modelData.kind === "image" ? IconData.paperclip : IconData.folder
                                size: 20
                                color: Theme.fgMuted
                            }
                            Column {
                                x: 64
                                y: 11
                                width: parent.width - 64 - 10
                                spacing: 3
                                Text {
                                    objectName: "attachName"
                                    width: parent.width
                                    text: modelData.name || ""
                                    elide: Text.ElideRight
                                    color: Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 12
                                    font.weight: 600
                                }
                                Text {
                                    objectName: "attachSize"
                                    width: parent.width
                                    text: modelData.sizeText || ""
                                    elide: Text.ElideRight
                                    color: Theme.fgMuted
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: deliveryCard
                    objectName: "deliveryCard"
                    visible: window.deliveries.length > 0
                    width: parent.width
                    height: visible ? deliveryCol.implicitHeight : 0
                    radius: Theme.radius
                    color: Theme.bgPanel
                    border.width: 1
                    border.color: Theme.border

                    Column {
                        id: deliveryCol
                        width: parent.width

                        Item {
                            width: parent.width
                            height: 34
                            Icon {
                                x: 12
                                anchors.verticalCenter: parent.verticalCenter
                                name: IconData.folder
                                size: 14
                                color: Theme.fgMuted
                            }
                            Text {
                                x: 34
                                anchors.verticalCenter: parent.verticalCenter
                                text: "交付文件"
                                color: Theme.fg
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                font.weight: 600
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: window.deliveries.length + " 个文件"
                                color: Theme.fgMuted
                                font.family: Theme.sansFamily
                                font.pixelSize: 11
                            }
                        }

                        Repeater {
                            model: window.deliveries
                            delegate: Item {
                                id: delivRow
                                required property var modelData
                                width: deliveryCol.width
                                height: 60

                                Rectangle {
                                    anchors.top: parent.top
                                    width: parent.width
                                    height: 1
                                    color: Theme.border
                                }

                                Rectangle {
                                    x: 12
                                    y: 8
                                    width: 44
                                    height: 44
                                    radius: Theme.radiusSm
                                    color: Theme.bgInset
                                    opacity: modelData.missing ? 0.5 : 1
                                    Icon {
                                        anchors.centerIn: parent
                                        name: IconData.folder
                                        size: 20
                                        color: Theme.fgMuted
                                    }
                                }

                                Text {
                                    id: delivName
                                    objectName: "delivName"
                                    x: 68
                                    y: 10
                                    width: parent.width - 68 - 100
                                    text: modelData.name || ""
                                    elide: Text.ElideMiddle
                                    color: modelData.missing ? Theme.fgMuted : Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    font.weight: 600
                                }
                                Text {
                                    objectName: "delivSub"
                                    x: 68
                                    y: 31
                                    width: parent.width - 68 - 100
                                    text: modelData.missing
                                          ? "文件已不存在"
                                          : ((modelData.sizeText || "") + " · " + (modelData.dir || ""))
                                    elide: Text.ElideMiddle
                                    color: Theme.fgMuted
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                }

                                Row {
                                    anchors.right: parent.right
                                    anchors.rightMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 2

                                    // 打开：仅白名单类型可开；文件已不存在时禁用。
                                    CardAction {
                                        objectName: "delivOpen"
                                        visible: modelData.openable && !modelData.missing
                                        iconName: IconData.externalLink
                                        iconColor: Theme.fgMuted
                                        onTriggered: window.deliverableOpen(modelData)
                                    }
                                    // 在文件夹中显示。
                                    CardAction {
                                        objectName: "delivReveal"
                                        iconName: IconData.folder
                                        iconColor: Theme.fgMuted
                                        enabled: !modelData.missing
                                        onTriggered: window.deliverableReveal(modelData)
                                    }
                                    // 复制路径：只复制边车里登记过的路径。
                                    CardAction {
                                        objectName: "delivCopy"
                                        iconName: window.copiedPath === modelData.path
                                                  ? IconData.check : IconData.copy
                                        iconColor: window.copiedPath === modelData.path
                                                   ? Theme.accent : Theme.fgMuted
                                        onTriggered: {
                                            if (window.deliverableCopy(modelData)) {
                                                window.copiedPath = modelData.path
                                                copyReset.restart()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // 交付卡动作失败提示（原版 toast 的等价物）：真实通道结果驱动。
        Rectangle {
            id: noticeBar
            objectName: "noticeBar"
            visible: window.actionNotice !== "" && !window.settingsOpen
            x: (parent.width - 780) / 2
            y: composer.y - 42
            width: Math.min(780, noticeText.implicitWidth + 28)
            height: 32
            radius: Theme.radius
            color: Theme.danger
            z: 20
            Text {
                id: noticeText
                anchors.centerIn: parent
                text: window.actionNotice
                color: "#ffffff"
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }
        }

        // 待发送附件：浮在输入卡上方一行；有文件才占位，空时不影响逐像素对位。
        Flow {
            id: pendingBar
            objectName: "pendingBar"
            visible: window.pendingFiles.length > 0 && !window.settingsOpen
            x: (parent.width - 780) / 2
            y: composer.y - (window.actionNotice !== "" ? 88 : 44)
            width: 780
            height: visible ? 36 : 0
            spacing: 6
            Repeater {
                model: window.pendingFiles
                delegate: Rectangle {
                    required property int index
                    required property var modelData
                    width: pendingRow.implicitWidth
                    height: 36
                    radius: Theme.radius
                    color: Theme.bgInset
                    border.width: 1
                    border.color: Theme.border

                    Row {
                        id: pendingRow
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 6
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: IconData.paperclip
                            size: 13
                            color: Theme.fgMuted
                        }
                        Text {
                            id: pendingName
                            anchors.verticalCenter: parent.verticalCenter
                            text: String(modelData).split("/").pop()
                            color: Theme.fg
                            font.family: Theme.sansFamily
                            font.pixelSize: 12
                        }
                        Item {
                            width: 18
                            height: 18
                            anchors.verticalCenter: parent.verticalCenter
                            Icon {
                                anchors.centerIn: parent
                                name: IconData.x
                                size: 12
                                color: Theme.fgMuted
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: window.removePending(index)
                            }
                        }
                    }
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
            // 输入框拿到键盘焦点时边框转主题色（原版 `:focus-within`，实测 91,91,214）。
            border.color: inputField.activeFocus || window.composerFocused ? Theme.accent : Theme.borderStrong

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

                // 附件图标按钮 30×30：真弹 QFileDialog（Python 侧 pickAttachments），
                // 选中的路径进 pendingFiles，随下一条消息发送。
                Rectangle {
                    id: clipBtn
                    objectName: "clipBtn"
                    x: 0
                    width: 30
                    height: 30
                    y: (parent.height - height) / 2
                    radius: Theme.radiusSm
                    color: (clipHover.hovered || clipMouse.containsMouse) ? Theme.bgHover : "transparent"
                    Icon {
                        anchors.centerIn: parent
                        name: IconData.paperclip
                        size: 16
                        color: Theme.fgSubtle
                        opacity: clipBtn.enabled ? 1 : 0.5
                    }
                    HoverHandler { id: clipHover }
                    MouseArea {
                        id: clipMouse
                        anchors.fill: parent
                        enabled: !window.busy
                        onClicked: window.pickAttachments()
                    }
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
                    color: window.busy || (inputField.text.trim() === "" && window.pendingFiles.length === 0)
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
                        enabled: !window.busy
                                 && (inputField.text.trim() !== "" || window.pendingFiles.length > 0)
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
                    // 原版 chip 无边框（CDP 实测 border-width 0）：只有状态点 + 文案 + 箭头。
                    color: "transparent"
                    border.width: 0
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
                    // 原版 chip 无边框（CDP 实测 border-width 0）：只有状态点 + 文案 + 箭头。
                    color: "transparent"
                    border.width: 0
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
        var files = window.pendingFiles
        if (window.busy || (text.trim() === "" && files.length === 0))
            return
        // 带附件走同一条宿主链路（ChatHost.send 的 attachments 参数），
        // 没有附件时仍走单参重载，保持既有行为。
        var sent = files.length > 0 ? shellBridge.sendWithAttachments(text, files) : shellBridge.send(text)
        if (sent) {
            inputField.text = ""
            window.pendingFiles = []
        }
    }

    // 回形针：真弹系统选择框（Python 侧 QFileDialog），选中项追加到待发列表。
    function pickAttachments() {
        var picked = shellBridge.pickAttachments()
        if (!picked || picked.length === 0)
            return
        var merged = window.pendingFiles.slice()
        for (var i = 0; i < picked.length; i++)
            if (merged.indexOf(picked[i]) < 0)
                merged.push(picked[i])
        window.pendingFiles = merged
    }

    function removePending(index) {
        var merged = window.pendingFiles.slice()
        if (index >= 0 && index < merged.length)
            merged.splice(index, 1)
        window.pendingFiles = merged
    }

    function notify(text) {
        window.actionNotice = text
        noticeReset.restart()
    }

    // 三个动作都把通道返回的 bool 原样交给界面：false 就弹真实失败提示，
    // 不做「点了就有反应」的假成功。
    function deliverableOpen(item) {
        var ok = shellBridge.openDeliverable(item.toolUseId, item.path)
        if (!ok)
            notify("无法打开该文件，可在文件夹中查看")
        return ok
    }

    function deliverableReveal(item) {
        var ok = shellBridge.revealDeliverable(item.toolUseId, item.path)
        if (!ok)
            notify("无法在文件夹中显示该文件")
        return ok
    }

    function deliverableCopy(item) {
        var ok = shellBridge.copyDeliverablePath(item.path)
        if (!ok)
            notify("无法复制该路径")
        return ok
    }

    // 交互态页面由 Python 在 QML 建好后写入，所以这些状态要监听 page 变化才真生效。
    onPageChanged: Qt.callLater(applyPageState)

    // 页名对应的「一次性」状态：抢焦点。列表滚动见 applyListScroll。
    function applyPageState() {
        if (window.page === "focus-composer") {
            // 原版是用户真实点进输入框：这里让输入框拿到键盘焦点，边框随之转主题色。
            inputField.forceActiveFocus()
        }
        applyListScroll()
    }

    // 模型 / 思考等级：写回 config.json（SettingsViewModel.set_active_* 同一份数据），
    // 成功才更新贴片与勾选，失败显式提示，不做「点了就有反应」的假成功。
    function pickModel(providerId, modelId) {
        if (!shellBridge.setActiveModel(String(providerId), String(modelId))) {
            notify("切换模型失败")
            return
        }
        window.modelLabel = findModelName(providerId, modelId)
        window.activeModelRef = String(providerId) + ":" + String(modelId)
        window.pickerMode = ""
        window.modelPickerOpen = false
    }

    function pickEffort(level) {
        if (!shellBridge.setActiveEffort(String(level))) {
            notify("切换思考等级失败")
            return
        }
        window.activeEffort = String(level)
        window.effortLabel = level === "default" ? "" : effortName(level)
        window.pickerMode = ""
        window.modelPickerOpen = false
    }

    function findModelName(providerId, modelId) {
        var rows = shellBridge.modelMenuGroups ? shellBridge.modelMenuGroups() : []
        for (var i = 0; i < rows.length; i++) {
            if (String(rows[i].id) !== String(providerId))
                continue
            var models = rows[i].models || []
            for (var k = 0; k < models.length; k++)
                if (String(models[k].id) === String(modelId))
                    return String(models[k].name || models[k].id)
        }
        return String(modelId)
    }

    // 档位名来自 Python 发布的 effortMenu.options（与原版 `chat.effort.levels.*` 同一份文案）。
    function effortName(level) {
        var rows = window.effortMenu && window.effortMenu.options ? window.effortMenu.options : []
        for (var i = 0; i < rows.length; i++)
            if (String(rows[i].level) === String(level))
                return String(rows[i].name)
        return String(level)
    }
    // 列表滚动：落点按原版实拍的滚动位置反算，不用「百分比」近似。
    //   行距 54px，首行顶在列表内 y8（窗口 y64）。原版 long-mid 的首个完整可见行是「会话 027」
    //   （index 26，头像顶 y83）→ contentY = 8 + 54×26 - (83-56) = 1386。
    //   long-bottom 是列表真底（原版末屏可见「会话 106」…「会话 119」），用 positionViewAtEnd。
    // page 由 Python 在 initial() 之后才写入，所以必须监听 page 变化；onCompleted 时它还是 "chat"。
    function applyListScroll() {
        if (window.page === "long-bottom") {
            // 真底：positionViewAtEnd() 在 contentHeight 还没最终确定时会落在估算位置，
            // 这里直接按 contentHeight - height 摆到底，再让 positionViewAtEnd 兜一次。
            sessionList.positionViewAtEnd()
            sessionList.contentY = Math.max(0, sessionList.contentHeight - sessionList.height)
        } else if (window.page === "long-mid")
            sessionList.contentY = Math.max(0, Math.min(1386,
                sessionList.contentHeight - sessionList.height))
        else
            sessionList.contentY = 0
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
