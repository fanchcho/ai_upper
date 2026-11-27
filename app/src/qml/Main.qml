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
import QtQuick.Shapes
import QtQuick.Window
import QtQuick.Dialogs as Dialogs
import "."

ApplicationWindow {
    id: window
    property string focusRoot: ""
    Dialogs.FolderDialog {
        id: workspaceDialog
        objectName: "workspaceDialog"
        title: I18n.t("cf.mountWorkspace")
        onAccepted: {
            window.actionNotice = shellBridge.acceptWorkspace(selectedFolder)
        }
        onRejected: shellBridge.cancelWorkspace()
    }

    visible: true
    property bool macChrome: Qt.platform.os === "osx"
    readonly property int railWidth: macChrome ? 72 : Theme.railWidth
    // deva main/index.ts:85-118: macOS uses native traffic lights, no overlay.
    flags: macChrome
           ? Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
             | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint
             | Qt.ExpandedClientAreaHint | Qt.NoTitleBarBackgroundHint
           : Qt.Window | Qt.FramelessWindowHint
    topPadding: 0
    width: 1280
    height: 820
    minimumWidth: 940
    minimumHeight: 600
    title: I18n.t("finish.brand")
    color: Theme.bg

    InteractionPrompt { }

    // 原版 Ctrl/Cmd+B：对话页收起/展开会话列表。两个 sequence 分开写，
    // 让 Linux/Windows 用 Ctrl、macOS 用 Cmd；Qt 的 "Ctrl+B" 在 macOS 也映射 Command，
    // 但显式写 Meta+B 可读性更好。
    // 编辑区右键菜单（原版主进程 index.ts:183-217 的原生菜单）。
    // composer：可编辑（剪切/复制/粘贴/全选）；正文：只读（复制/全选）。
    EditContextMenu {
        id: composerMenu
        objectName: "composerMenu"
        target: inputField
        editable: true
    }
    EditContextMenu {
        id: bodyMenu
        objectName: "bodyMenu"
        target: bodyView
        editable: false
    }

    // 窗口拖放：原版 Composer.tsx:576-596 在 window 上监听 dragover/drop。
    // 真实文件由 Python AttachmentService 判定并登记白名单，QML 只收集路径。
    DropArea {
        id: dropArea
        objectName: "dropArea"
        anchors.fill: parent
        onDropped: function (drop) { window.acceptDrop(drop.urls) }
    }
    Rectangle {
        objectName: "dropOverlay"
        anchors.fill: parent
        visible: dropArea.containsDrag
        color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.05)
        border.width: 2
        border.color: Theme.accent
        z: 90
    }

    Shortcut {
        sequence: "Ctrl+B"
        context: Qt.ApplicationShortcut
        enabled: window.page === "chat"
        onActivated: window.toggleSidebar()
    }
    Shortcut {
        sequence: "Meta+B"
        context: Qt.ApplicationShortcut
        enabled: window.page === "chat"
        onActivated: window.toggleSidebar()
    }

    // ── Python 注入的状态 ─────────────────────────────────────────────
    property var sessions: []
    property string activeId: ""
    // Composer.tsx keeps drafts in memory per session, including pending attachments.
    property var composerDrafts: ({})
    property string composerSessionId: ""
    onActiveIdChanged: {
        if (composerSessionId) {
            composerDrafts[composerSessionId] = {
                text: inputField.text, files: pendingFiles.slice()
            }
        }
        var draft = composerDrafts[activeId]
        inputField.clear()
        inputField.text = draft ? draft.text : ""
        pendingFiles = draft ? draft.files.slice() : []
        composerSessionId = activeId
    }
    property string activeTitle: ""
    property string activePersona: I18n.t("finish.brand")
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
    // 会话列表收起（原版 ChatFirstShell.tsx:143-160）：Ctrl/Cmd+B 切换并落盘；
    // 收起后悬停「对话」图标 200ms 浮出列表（peek），列表盖在正文上而不改变正文宽度。
    property bool sideCollapsed: false
    property bool sidePeek: false
    property bool _sidePeekHover: false
    // 空态快速开启的角色卡片（Python 每次 _publish 现读 PersonaStore 写进来）。
    property var quickStartPersonas: []
    property bool dark: Theme.dark
    property bool settingsOpen: page === "settings-custom-model" || page === "settings-mcp" || page === "settings-identities" || page === "settings-general" || page === "settings-models"
                              || page === "settings-models-provider" || page === "settings-models-advanced"
                              || page === "settings-extensions" || page === "settings-about"
    property string settingsPane: page === "settings-custom-model" ? "custom-model"
                                : page === "settings-mcp" ? "mcp"
                                : page === "settings-identities" ? "identities"
                                : page === "settings-about" ? "about"
                                : (page === "settings-models" || page === "settings-models-provider"
                                   || page === "settings-models-advanced") ? "models"
                                : page === "settings-extensions" ? "extensions" : "general"
    property string settingsModelsView: page === "settings-models-provider" ? "provider"
                                       : page === "settings-models-advanced" ? "advanced" : "list"
    property bool searchActive: page === "search-open" || page === "search-results"
                                || page === "search-none"
    property string searchQuery: page === "search-results" ? "00"
                               : page === "search-none" ? "zzz" : ""
    property bool modelPickerOpen: page === "model-picker"
    // 打开的是哪一个菜单：模型列表 / 思考等级。空串 = 都关着。
    property string pickerMode: page === "model-picker" ? "model" : ""
    // 上下文容量小卡片：独立于两个 picker；任一贴片展开时必须收起。
    property bool contextOpen: false
    // 交互态页面：deva 截图的鼠标停在 (200,700)，落在第 11 行（y=56+54×11=650..703）；
    // 只有列表页会照原版显示该行 hover，设置页/弹层/确认层不造悬停。
    // `hover-thread` 原图指针不在任何行上（probe-hover.log 仅 42 px 噪声），因此保持 -1。
    // long-mid 的截图指针仍在窗口 y700；随 contentY 绑定可见行，不能固定到已滚走的第 11 行。
    property int forceHoverRow: page === "long-mid"
                               ? Math.floor((sessionList.contentY + 700 - sessionList.y) / 54)
                               : (page === "chat" || page === "search-open"
                                 || page === "focus-composer"
                                 || page === "long-bottom" || page === "dark-chat") ? 11 : -1
    // 输入区焦点态：focus-composer 页要让输入卡片真的拿到键盘焦点，
    // 原版此时边框从 #d5d5db 变 #5b5bd6（CDP 实测 border-color）。
    property bool composerFocused: page === "focus-composer"
    // 右键菜单 / 删除确认框：页面深链负责截图初始态，用户点击后可独立开关。
    property bool ctxDismissed: false
    property bool confirmDismissed: false
    property bool ctxUserOpen: false
    property bool confirmUserOpen: false
    readonly property bool ctxOpen: (page === "ctx-menu" && !ctxDismissed) || ctxUserOpen
    readonly property bool confirmOpen: (page === "delete-confirm" && !confirmDismissed) || confirmUserOpen
    property string ctxSessionId: ""
    property string ctxTitle: ""
    property string pendingDeleteId: ""
    property string pendingDeleteTitle: ""
    // 归档列表：Python 每次 _publish 把已归档会话投影写进来；列表右键 Archive 后从这里可查。
    property var archivedSessions: []
    property bool archiveView: false
    // 多选：右键菜单「Select」进入；selectedSessions 只存 id，落盘仍走 ShellBridge 的会话服务。
    property bool selectMode: false
    property var selectedSessions: []
    // 全选后滚动不逐行扫描整个选择数组；任一集合变化使快路径失效。
    property bool allListedSelected: false
    property var listedSessionIds: []
    onSelectedSessionsChanged: allListedSelected = false
    onListedSessionsChanged: {
        allListedSelected = false
        var rows = listedSessions
        var ids = []
        for (var i = 0; i < rows.length; i++)
            ids.push(rows[i].id)
        listedSessionIds = ids
    }
    // 重命名：原版是居中输入框（dialog.prompt），不是行内编辑；空串提交 = 恢复自动标题。
    property bool renameOpen: false
    property string renameId: ""
    property string renameOriginalTitle: ""
    property string renameValue: ""

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
    // 上下文圆环读数（Python `contextUsage()`）：{used, estimated, window, trigger}。
    // used=None 时整个圆环不占宽（原版 ModelPanel 不渲染 ContextRing）。
    property var contextUsage: ({})

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
    // 已归档会话同样按搜索词过滤；只有 archiveView 打开时列表才绑定它。
    readonly property var archivedVisibleSessions: {
        var all = window.archivedSessions || []
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
    readonly property var listedSessions: window.archiveView ? archivedVisibleSessions : visibleSessions

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

    // 滚动条：原版 app.css `::-webkit-scrollbar`（width 8 / thumb 圆角 999 /
    // border 2px transparent + background-clip: content-box / track 透明）。
    // 用 QML ScrollBar 附件挂到 Flickable，拖动与滚轮由控件原生处理；
    // hover 只改滑块颜色，形态与 deva 的 :hover 规则一致（--fg-subtle）。
    component DevaScrollBar: ScrollBar {
        id: devaBar
        width: Theme.scrollbarWidth
        padding: Theme.scrollbarInset
        policy: ScrollBar.AsNeeded
        hoverEnabled: true
        background: Rectangle { color: "transparent" }
        contentItem: Rectangle {
            implicitWidth: Theme.scrollbarWidth - 2 * Theme.scrollbarInset
            implicitHeight: 26
            radius: Theme.radiusFull
            color: (devaBar.pressed || devaBar.hovered) ? Theme.scrollbarHover
                                                        : Theme.scrollbar
        }
    }

    // 原版 Electron Linux `titleBarOverlay` 的单按钮：32×40 命中区，透明底，hover 时
    // 叠 18/255 黑（原版实拍量得；遮罩压不暗它，因为原生叠加层画在网页之上）。
    //
    // 几何/配色来源（只读参考，未改动 deva）：
    //   deva/apps/desktop/src/main/index.ts:79-81  OVERLAY_BG light #ffffff / dark #1e1e20
    //   deva/apps/desktop/src/main/index.ts:89-97  overlayOptions 的 height 40
    //   deva/apps/desktop/src/main/index.ts:112-116 titleBarStyle 'hidden' + titleBarOverlay
    //   deva/node_modules/electron/electron.d.ts:21424-21439 Linux 不吃 symbolColor（系统色）
    //   deva 原版 1280×820 实拍 out/latest-parity/deva/chat-deva.png 逐像素：
    //     整块 96×40 @ x1184；最小化 10×2 @ x1195 y23；最大化 10×10 框 @ x1227 y15；
    //     关闭 10×10 X @ x1259 y15、线宽 2.1；图标 #5F6368 light / #E8EAED dark。
    component WindowControlButton: Rectangle {
        id: winBtn
        signal clicked()
        // 0 = 最小化，1 = 最大化，2 = 关闭。
        property int kind: 0
        width: 32
        height: 40
        color: winMouse.containsMouse ? Qt.rgba(0, 0, 0, 18 / 255) : "transparent"
        readonly property color glyphColor: Theme.dark ? "#E8EAED" : "#5F6368"

        // 最小化：10×2 实心横条。按钮内坐标 = 全局 x1195..1204 / y23..24 - 按钮左边界。
        Rectangle {
            visible: winBtn.kind === 0
            x: 11
            y: 23
            width: 10
            height: 2
            color: winBtn.glyphColor
        }

        // 最大化：10×10 描边方框，四条边各 2px（与原版实拍逐像素一致）。
        Item {
            visible: winBtn.kind === 1
            x: 11
            y: 15
            width: 10
            height: 10
            Rectangle { width: 10; height: 2; color: winBtn.glyphColor }
            Rectangle { y: 8; width: 10; height: 2; color: winBtn.glyphColor }
            Rectangle { width: 2; height: 10; color: winBtn.glyphColor }
            Rectangle { x: 8; width: 2; height: 10; color: winBtn.glyphColor }
        }

        // 关闭：10×10 的 X，2.1px 平头线；端点取原版实拍拟合值。
        Shape {
            visible: winBtn.kind === 2
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: winBtn.glyphColor
                strokeWidth: 2.1
                fillColor: "transparent"
                capStyle: ShapePath.FlatCap
                startX: 11.75
                startY: 15.75
                PathLine { x: 20.25; y: 24.25 }
            }
            ShapePath {
                strokeColor: winBtn.glyphColor
                strokeWidth: 2.1
                fillColor: "transparent"
                capStyle: ShapePath.FlatCap
                startX: 20.25
                startY: 15.75
                PathLine { x: 11.75; y: 24.25 }
            }
        }

        MouseArea {
            id: winMouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: winBtn.clicked()
        }
    }

    // ── 图标栏 ────────────────────────────────────────────────────────
    component RailButton: Rectangle {
        id: btn
        signal clicked()
        property string iconName
        property bool active: false
        property bool dim: false
        signal hoverChanged(bool entered)
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
            color: btn.active ? Theme.accent : railHover.hovered ? Theme.fg : Theme.fgSubtle
            opacity: btn.dim ? 0.7 : 1
        }
        HoverHandler {
            id: railHover
            onHoveredChanged: btn.hoverChanged(hovered)
        }
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
        width: window.railWidth
        height: parent.height
        color: Theme.bgInset

        MouseArea {
            id: railDrag
            objectName: "windowDragRail"
            anchors.fill: parent
            containmentMask: QtObject {
                function contains(p: point): bool {
                    if (p.x < 0 || p.y < 0 || p.x >= railDrag.width || p.y >= railDrag.height)
                        return false
                    if (window.macChrome && p.y < 40)
                        return false
                    var shift = window.macChrome ? 40 : 0
                    // deva .cf-iconrail: drag; avatar/nav buttons: no-drag.
                    return !(p.x >= 8 && p.x < 48 &&
                             ((p.y >= 20 + shift && p.y < 58 + shift) ||
                              (p.y >= 70 + shift && p.y < 198 + shift) ||
                              (p.y >= 724 && p.y < 808)))
                }
            }
            onPressed: window.startSystemMove()
        }

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
            y: window.macChrome ? 60 : 20
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
            y: window.macChrome ? 110 : 70
            spacing: 4
            RailButton {
                objectName: "railChats"
                iconName: IconData.messageCircle
                active: true
                onHoverChanged: function (entered) { window.chatRailHover(entered) }
            }
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
        objectName: "sessionSide"
        x: window.railWidth
        y: 0
        width: window.sideCollapsed ? (window.sidePeek ? Theme.sideWidth : 0) : Theme.sideWidth
        visible: !window.sideCollapsed || window.sidePeek
        z: window.sidePeek ? 20 : 0
        height: parent.height
        color: Theme.bgPanel
        HoverHandler { onHoveredChanged: window.sideHover(hovered) }

        Rectangle {
            anchors.right: parent.right
            width: 1
            height: parent.height
            color: Theme.border
        }

        // deva .cf-rail__top 的空白可拖动；搜索框、加号在其上接收事件。
        MouseArea {
            id: sidebarDrag
            objectName: "windowDragSidebar"
            width: parent.width
            height: 56
            containmentMask: QtObject {
                function contains(p: point): bool {
                    if (p.x < 0 || p.y < 0 || p.x >= sidebarDrag.width || p.y >= sidebarDrag.height)
                        return false
                    return !(p.y >= 12 && p.y < 44 &&
                             ((p.x >= 12 && p.x < 247) || (p.x >= 255 && p.x < 287)))
                }
            }
            onPressed: window.startSystemMove()
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
                text: window.chatText.searchChats || I18n.t("cf.searchChats")
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

        // 已归档对话视图的标题条：点右侧入口进来，左侧返回对话列表。
        Rectangle {
            id: archiveHeader
            objectName: "archiveHeader"
            visible: window.archiveView
            x: 8
            y: 56
            width: parent.width - 16
            height: 32
            color: "transparent"

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.t("native.message2") + window.archivedSessions.length + ")"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 13
                font.weight: 600
            }
            Rectangle {
                objectName: "archiveBack"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 24
                height: 24
                radius: Theme.radiusSm
                color: archiveBackMouse.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: "←"
                    color: Theme.fgMuted
                    font.family: Theme.sansFamily
                    font.pixelSize: 15
                }
                MouseArea {
                    id: archiveBackMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.closeArchiveView()
                }
            }
        }

        // 会话列表：第二列 --cf-side 300（redesign.css:32），.cf-rail 右框 1px（:193）
        // => .cf-list clientWidth 299；左右 padding 8（redesign.css:741-746），
        // 滚动条再占 8（styles/app.css:45-62），行内容宽 = 299 - 8×2 - 8 = 275；行 x=64..338。
        ListView {
            id: sessionList
            objectName: "sessionList"
            x: 0
            y: window.archiveView ? 92 : 56
            width: Theme.sideWidth - 1
            height: parent.height - y - 8
            clip: true
            leftMargin: 8
            rightMargin: 8
            model: window.listedSessions
            spacing: 0
            boundsBehavior: Flickable.StopAtBounds

            // 原版 ::-webkit-scrollbar：8px 宽，thumb 2px 透明内缩后可见 4px。
            ScrollBar.vertical: DevaScrollBar {
                objectName: "sidebar-scrollbar"
            }

            // 长列表两张页面：原版同样是滚动位置，但位置由 applyListScroll() 按实测像素摆。
            // 注意 `Component.onCompleted` 时 Python 还没写 page（_select_page 在 initial() 之后），
            // 所以这里只能靠 page 变化触发；onCompleted 保留给 contentHeight 已就绪的场合。
            onContentHeightChanged: window.applyListScroll()
            Component.onCompleted: window.applyListScroll()

            delegate: ThreadRow {
                objectName: "threadRow" + index
                required property int index
                required property var modelData
                x: 8
                // 299 - 左右 padding 8×2 - 滚动条 8 = 275（deva DOM threads[0].rect.w）。
                width: ListView.view.width - 2 * Theme.space2 - Theme.scrollbarWidth
                title: modelData.title || ""
                time: modelData.time || ""
                persona: modelData.persona || "general"
                ownerName: modelData.personaName || I18n.t("finish.brand")
                active: modelData.id === window.activeId
                forceHover: index === window.forceHoverRow
                selectionMode: window.selectMode
                selected: window.allListedSelected || window.selectedSessions.indexOf(modelData.id) >= 0
                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    onClicked: function (mouse) {
                        if (mouse.button === Qt.RightButton)
                            window.openCtxMenu(modelData.id, modelData.title)
                        else if (window.selectMode)
                            window.toggleSelect(modelData.id)
                        else
                            window.activate(modelData.id)
                    }
                }
            }
        }

        // 空状态：原版 `.cf-empty`（12px / padding 20 / 文本居中）。
        //   没有任何会话        → "No conversations"（实测 x155–256 y80–89）
        //   有会话但筛选无命中  → "No matches"       （实测 x171–240 y80–89，i18n `cf.searchNoResults`）
        // 列表区从 x56 起、宽 283，文本水平居中即落在实测位置。
        Text {
            objectName: "listEmpty"
            visible: window.listedSessions.length === 0
            x: 8
            y: window.archiveView ? 104 : 68
            width: 283
            horizontalAlignment: Text.AlignHCenter
            text: window.searchTerm !== "" ? (window.chatText.noMatches || I18n.t("cf.searchNoResults"))
                                          : (window.archiveView
                                             ? I18n.t("native.message15")
                                             : (window.chatText.noSessions || I18n.t("chat.noSessions")))
            color: Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 12
        }

        // 已归档入口：原版在加号菜单里显示 `Archived chats`；这里固定贴在列表底部，
        // 只在确实有归档项时出现，点击后用同一列表展示已归档会话。
        Rectangle {
            id: archiveEntry
            objectName: "archiveEntry"
            visible: window.archivedSessions.length > 0 && !window.archiveView && !window.selectMode
            x: 8
            y: parent.height - 40
            width: parent.width - 16
            height: 30
            radius: Theme.radius
            color: archiveEntryMouse.containsMouse ? Theme.bgHover : "transparent"

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                text: I18n.t("native.message2") + window.archivedSessions.length + ")"
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }
            MouseArea {
                id: archiveEntryMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: window.openArchiveView()
            }
        }

        // 多选操作条：原版 `.cf-railsel` 贴在列表底部；数量、全选、归档、退出都走同一份会话服务。
        Rectangle {
            id: selectionBar
            objectName: "selectionBar"
            visible: window.selectMode
            x: 0
            y: parent.height - 44
            width: parent.width
            height: 44
            color: Theme.bgElevated

            Text {
                objectName: "selectionCount"
                x: 12
                anchors.verticalCenter: parent.verticalCenter
                text: window.selectedSessions.length + I18n.t("native.message0")
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }
            Rectangle {
                objectName: "selectionAll"
                x: 92
                anchors.verticalCenter: parent.verticalCenter
                width: 78
                height: 28
                radius: Theme.radiusSm
                color: selectionAllMouse.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: window.selectedSessions.length === window.listedSessions.length
                          && window.listedSessions.length > 0 ? I18n.t("cf.selectNone") : I18n.t("cf.selectAll")
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 12
                }
                MouseArea {
                    id: selectionAllMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.toggleSelectAll()
                }
            }
            Row {
                anchors.right: parent.right
                anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                Rectangle {
                    objectName: "selectionArchive"
                    width: 30
                    height: 28
                    radius: Theme.radiusSm
                    color: selectionArchiveMouse.containsMouse ? Theme.bgHover : "transparent"
                    Icon { anchors.centerIn: parent; name: IconData.archive; size: 15; color: Theme.fg }
                    MouseArea {
                        id: selectionArchiveMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: window.archiveSelected()
                    }
                }
                Rectangle {
                    objectName: "selectionExit"
                    width: 30
                    height: 28
                    radius: Theme.radiusSm
                    color: selectionExitMouse.containsMouse ? Theme.bgHover : "transparent"
                    Icon { anchors.centerIn: parent; name: IconData.x; size: 15; color: Theme.fg }
                    MouseArea {
                        id: selectionExitMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: window.exitSelect()
                    }
                }
            }
        }
    }

    // ── 正文区 ────────────────────────────────────────────────────────
    Item {
        id: conv
        objectName: "convColumn"
        x: window.railWidth + (window.sideCollapsed ? 0 : Theme.sideWidth)
        y: 0
        width: parent.width - x
        height: parent.height

        // deva .cf-conv__head / .cf-dragbar；角色名按钮区域排除。
        MouseArea {
            objectName: "windowDragHeader"
            x: head.visible ? 16 + personaTitle.width + 20 : 0
            width: parent.width - (window.macChrome ? 0 : 96) - x
            height: head.visible ? 27 : 40
            onPressed: window.startSystemMove()
        }

        // 顶部 26px 的会话头：下缘 1px 分隔线横贯 x 356–1183（实测 828px 宽）
        Item {
            id: head
            // 原版无任何对话时中列是 `QuickStart`（只有 DragBar，没有会话头），
            // 会话头（含下缘分隔线）仅在存在对话时出现。
            visible: window.sessions.length > 0
            x: 0
            y: 0
            width: parent.width - (window.macChrome ? 0 : 96)
            height: 27
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
            // 标题按钮：原版 .cf-idbtn 只有名字，padding 5/10
            Text {
                id: personaTitle
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

        // 空状态：原版 `QuickStart`（`Rail.tsx:1296-1326`）。无任何对话时中列列出花名册
        // 全部角色，点卡片/头像即以该角色开一条新对话（`startQuickStart` → `startWith` 同语义）。
        //
        // 几何取自原版 `redesign.css:3054-3131` 与 `out/qml-shell/dom/empty.json` 实测：
        //   `.cf-quick` 从 DragBar（40px）下沿起、占满余下高度；`.cf-quick__inner` 宽 780
        //   居中、padding 24/20、纵向 flex 居中；标题 20/750（line-height 30）、提示
        //   margin-top 6 / 13px；网格 margin-top 24、flex 居中、gap 16；卡片宽 130、
        //   纵向 flex、gap 8、padding 16/12、1px 边框、radius-lg、底色 bg-panel。
        //   2 张卡片：130+16+130 = 276 居中 → x 682..812 / 828..958（与实测一致）。
        Item {
            id: quickStart
            objectName: "quickStart"
            visible: window.sessions.length === 0
            x: 0
            y: 40
            width: parent.width
            height: parent.height - 40

            SettingsButton {
                objectName: "chatManagePersonas"; x: 20; y: 12
                text: I18n.t("cf.filterRoles"); onClicked: window.page = "personas-editor"
            }

            // `.cf-quick__inner`：max-width 780 的居中列，容器内纵向居中。
            // 宽度取内容列可用宽 740（780 - 左右各 20 的 padding）；窄窗时跟随容器。
            Column {
                id: quickInner
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(740, quickStart.width - 40)
                // 原版 `justify-content: center` 把标题+提示+网格整体居中：
                // 内容总高 30 + (6+19.5) + 24 + 卡片高，实测标题行盒上沿 315.25。
                y: Math.round((parent.height - height) / 2)
                spacing: 0

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: window.chatText.quickStartTitle || I18n.t("cf.quickStartTitle")
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 20
                    // 原版 750：QML 只有整数字重，最接近的是 Bold(700)。
                    font.weight: 700
                    // 原版 line-height 30px（1.5 × 20）。
                    // Qt 的 FixedHeight 行盒与 Chromium 的半行距算法不同：同样 30px 行盒，
                    // 基线比原版高 3px（实测墨迹 319 vs 322），用 topPadding 补偿；
                    // 高度锁回 30，避免 padding 把下面整列（提示/网格）整体推低。
                    topPadding: 3
                    height: 30
                    lineHeight: 30
                    lineHeightMode: Text.FixedHeight
                }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    // 原版 `margin-top: 6px` + 19.5 行盒 = 25.5 总高。Qt 的行内基线比
                    // Chromium 高 2px（实测墨迹 353 vs 355），把 2px 从 padding 挪进来、
                    // 高度仍锁 25.5，网格位置不动。
                    topPadding: 8
                    height: 25.5
                    text: window.chatText.quickStartHint || I18n.t("cf.quickStartHint")
                    color: Theme.fgMuted
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    // 原版 19.5px（1.5 × 13）。
                    lineHeight: 19.5
                    lineHeightMode: Text.FixedHeight
                }

                // `.cf-quick__grid`：margin-top 24、flex wrap 居中、gap 16。
                // 卡片 130 宽。QML 没有 flex-wrap，用 Grid 按可用宽算列数再整块居中：
                // 一行能放几列 = floor((可用宽 + 16) / (130 + 16))，等于 CSS 的折行结果。
                // 单行（当前花名册 2 人）与原版逐像素一致；折成多行时 CSS 的最后一行
                // 也会居中，Grid 靠左——这是 QML 无 flexbox 的已知残差。
                Grid {
                    id: quickGrid
                    readonly property int gap: 16
                    readonly property int cardW: 130
                    readonly property int avail: parent.width
                    // 一行最多能排几列（= CSS flex-wrap 的折行容量）。
                    readonly property int capacity: Math.max(1, Math.floor((avail + gap) / (cardW + gap)))
                    // 只有一行时按实际卡片数收紧宽度，`horizontalCenter` 才能把整行摆到
                    // 容器正中；否则 2 张卡会贴在第 1、2 列（实测左移 219px）。
                    columns: Math.max(1, Math.min(quickRepeater.count, capacity))
                    rowSpacing: gap
                    columnSpacing: gap
                    width: columns * cardW + (columns - 1) * gap
                    anchors.horizontalCenter: parent.horizontalCenter
                    topPadding: 24
                    // 原版网格是 flex，默认 `align-items: stretch`：同一行的卡片等高，
                    // 高度取该行最高那张（实测 150 = 内容 116 + 上下 padding 32 + 边框 2，
                    // 由 CJK 名称 19px 行盒撑起；纯拉丁名称时是 146）。QML 的 Grid 不会拉伸
                    // 子项，所以这里显式取「同行最高」。
                    readonly property real cellHeight: {
                        var m = 0
                        for (var i = 0; i < quickRepeater.count; ++i) {
                            var item = quickRepeater.itemAt(i)
                            if (item)
                                m = Math.max(m, item.naturalHeight)
                        }
                        return m
                    }

                    Repeater {
                        id: quickRepeater
                        model: window.quickStartPersonas
                        delegate: Rectangle {
                            required property var modelData
                            // 原版 `.cf-qcard`：宽 130、padding 16/12、1px 边框（border-box）。
                            // 内容盒宽 = 130 - 2×1(边框) - 2×12(padding) = 104。
                            width: 130
                            // 内容自然高（Column + 上下 padding 32 + 边框 2）；实际高度按行拉伸。
                            readonly property real naturalHeight: cardColumn.height + 34
                            height: quickGrid.cellHeight
                            radius: Theme.radiusLg
                            color: cardHover.hovered ? Theme.bgHover : Theme.bgPanel
                            border.width: 1
                            border.color: cardHover.hovered ? Theme.borderStrong : Theme.border

                            HoverHandler { id: cardHover }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: window.quickStart(modelData.id)
                            }

                            Column {
                                id: cardColumn
                                x: 13
                                y: 17
                                width: parent.width - 26
                                spacing: 8

                                Avatar {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    persona: modelData.id || "general"
                                    // 原版 `Avatar size={48}`：48 > 20 且未传 compact，
                                    // PersonaFace 走探出构图（POP_BOX），人脸比框内构图大一档
                                    // ——这是 Avatar 按尺寸自动判定的，这里不用再写。
                                    size: 48
                                }
                                Text {
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: modelData.name
                                    color: Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    // 原版 650 → 600（QML 整数字重）。
                                    font.weight: 600
                                    // 原版 `.cf-qcard__name` 未设 line-height：computed normal，
                                    // 拉丁名行盒 15px、CJK 名 19px。Qt 默认行盒各多 1px，
                                    // 会把下面的描述整体推低；这里锁回原版行盒高（墨迹位置不变）。
                                    property int rowBox: {
                                        var m = /[^\x00-\x7F]/.test(text) ? 19 : 15
                                        return m
                                    }
                                    height: rowBox
                                    elide: Text.ElideRight
                                }
                                Text {
                                    visible: (modelData.desc || "") !== ""
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    text: modelData.desc
                                    color: Theme.fgSubtle
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                    // 原版 11 × 1.5 = 16.5，clamp 2 行。Qt 在固定行盒里
                                    // 把 11px 字的墨迹整体压低 1px（实测墨迹首行 493 vs 492）。
                                    // 用 16 的行盒并把两行总高锁回 33（= 2 × 16.5），再给 -1 的
                                    // topPadding 把墨迹提上去：列高/卡片高一个像素都不动，只有
                                    // 墨迹对齐。实测描述带 AE 1786 → 1590、卡片区 2893 → 2697。
                                    lineHeight: 16
                                    lineHeightMode: Text.FixedHeight
                                    height: 33
                                    topPadding: -1
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }
        }

        // 消息区：Flickable 占满正文栏（滚动条贴窗口右缘，同原版 `.cf-msgs`），
        // 内部仍是 780 列居中、正文 696 宽、左头像 32。
        Flickable {
            id: bodyScroll
            objectName: "bodyScroll"
            visible: window.sessions.length > 0
            x: 0
            y: 27
            width: parent.width
            height: parent.height - 27 - 175
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: width
            contentHeight: bodyView.y + bodyView.implicitHeight + 24
                            + (cardsCol.visible ? cardsCol.height + 20 : 0)
            topMargin: 20

            // 原版 ::-webkit-scrollbar：8px 宽，thumb 2px 透明内缩后可见 4px，贴正文栏右缘。
            ScrollBar.vertical: DevaScrollBar {
                id: bodyScrollbar
                objectName: "body-scrollbar"
            }

            TextEdit {
                id: bodyView
                objectName: "bodyView"
                clip: true
                // 消息头（头像列 32 + gap 12）之外是 696 的正文块；列宽 780 在正文栏内居中。
                x: (bodyScroll.width - Theme.mainWidth) / 2 + 56
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
                // 原版正文里的 <a> 由 Chromium 直接打开；QML 的 TextEdit 必须显式接
                // linkActivated（readOnly 时才发），再交给 ShellBridge 转系统浏览器。
                onLinkActivated: function (link) { shellBridge.openExternal(link) }
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onSingleTapped: function (eventPoint) {
                        bodyMenu.x = eventPoint.scenePosition.x
                        bodyMenu.y = eventPoint.scenePosition.y
                        bodyMenu.open()
                    }
                }
                Component.onCompleted: shellBridge.attach(textDocument)
            }

            // 正文之后：本轮会话的附件贴片（缩略图 + 名称 + 真实体积）与交付卡。
            // 数据全部来自 Python 的 `attachment_rows()` / `delivery_rows()`（落盘会话 + 边车），
            // 这里只画，不自己读盘、不自己算体积。
            Column {
                id: cardsCol
                objectName: "cardsCol"
                x: (bodyScroll.width - Theme.mainWidth) / 2 + 56
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
                                text: I18n.t("chat.deliver.title")
                                color: Theme.fg
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                font.weight: 600
                            }
                            Text {
                                anchors.right: parent.right
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                text: window.deliveries.length + I18n.t("native.message1")
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
                                          ? I18n.t("chat.deliver.missing")
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
            visible: window.actionNotice !== ""
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
            visible: window.pendingFiles.length > 0
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
        // 卡片实测：(428,658) 780×146，padding 12，边框 #d5d5db，圆角 12。
        // 阴影：原版 `.cf-box { box-shadow: var(--shadow) }`（redesign.css:2661），
        // 深色 `0 8px 30px rgba(0,0,0,.5)`、浅色 `0 6px 24px rgba(0,0,0,.12)`
        // （tokens.css:149 / :82）。参数字面量集中在 SoftShadow.qml。
        SoftShadow {
            id: composerShadow
            target: composer
        }

        Rectangle {
            id: composer
            objectName: "composer"
            visible: window.sessions.length > 0
            x: (parent.width - 780) / 2
            y: parent.height - 162
            width: 780
            height: 146
            radius: Theme.radiusLg
            // 原版 `.cf-box` 底色是 `--bg-elevated`（redesign.css:2655-2662），不是页面底色
            // `--bg`：深色下两者不同（#2a2a2e vs #1e1e20），浅色下都是 #ffffff。
            color: Theme.bgElevated
            border.width: 1
            // 输入框拿到键盘焦点时边框转主题色（原版 `.cf-box:focus-within`，实测 91,91,214）。
            // 贴片也是卡片内的 focusable 元素：点开模型/思考等级菜单时焦点落在贴片上，
            // 原版四边同为 `#5b5bd6`——所以菜单打开时也按聚焦态上色。
            border.color: inputField.activeFocus || window.composerFocused
                          || window.modelPickerOpen ? Theme.accent : Theme.borderStrong

            // 草稿区：y 671（卡片内 13），高 80，占位 13.5px
            TextArea {
                id: inputField
                objectName: "inputField"
                x: 13
                y: 13
                width: parent.width - 26
                height: 80
                padding: 2
                placeholderText: I18n.t("native.message13") + (window.activePersonaName || I18n.t("cf.assistant")) + "…"
                placeholderTextColor: Theme.fgSubtle
                color: Theme.fg
                font.family: Theme.sansFamily
                // 13.5px → QML pixelSize 取整会变成 13；用 pointSize(10.125pt) 得真实 13.5
                font.pointSize: 10.125
                wrapMode: TextArea.Wrap
                background: null
                enabled: !window.busy
                TapHandler {
                    acceptedButtons: Qt.RightButton
                    onSingleTapped: function (eventPoint) {
                        composerMenu.x = eventPoint.scenePosition.x
                        composerMenu.y = eventPoint.scenePosition.y
                        composerMenu.open()
                    }
                }
                Keys.onPressed: function (event) {
                    if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_V) {
                        // 剪贴板里是图片时按附件处理（原版 Composer 的 paste 处理）；纯文本走默认粘贴。
                        var pasted = shellBridge.attachClipboardImage()
                        if (pasted && pasted.length > 0) {
                            window.appendPendingFiles(pasted)
                            event.accepted = true
                            return
                        }
                    }
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
                    objectName: "mountChip"
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
                        text: window.focusRoot ? (window.focusRoot.split("/").pop() || window.focusRoot) : I18n.t("cf.mountWorkspace")
                        width: Math.min(180, implicitWidth)
                        elide: Text.ElideMiddle
                        anchors.verticalCenter: undefined
                        y: (30 - height) / 2
                        color: Theme.fgSubtle
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        rightPadding: 8
                        leftPadding: 9
                    }
                }

                MouseArea {
                    anchors.fill: mountChip
                    onClicked: {
                        if (workspaceDialog.visible) return
                        var error = shellBridge.beginWorkspace()
                        window.actionNotice = error
                        if (!error) workspaceDialog.open()
                    }
                }

                // 右侧：模型 chip + 强度 chip + 发送/停止
                //
                // 原版 `Composer.tsx:973-991`：回合进行中同一枚键切成停止态
                // （`.cf-send.is-stop` 中性底色 + lucide Square 14 实心，最小宽度 68
                // 保证两态同宽不跳动，`redesign.css:2823-2829`）。本移植版没有「回合中
                // 插入消息」能力，所以 busy 时恒定显示停止键，不假装能发送。
                Rectangle {
                    id: sendBtn
                    objectName: "sendBtn"
                    anchors.right: parent.right
                    width: 69
                    height: 32
                    y: 0
                    radius: Theme.radius
                    color: window.busy
                           ? Theme.bgHover
                           : (inputField.text.trim() === "" && window.pendingFiles.length === 0)
                             ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45)
                             : Theme.accent
                    Text {
                        anchors.centerIn: parent
                        visible: !window.busy
                        text: I18n.t("cf.send")
                        color: Theme.accentFg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.weight: 600
                    }
                    Icon {
                        objectName: "stopGlyph"
                        anchors.centerIn: parent
                        visible: window.busy
                        name: IconData.square
                        size: 14
                        color: Theme.fg
                    }
                    MouseArea {
                        id: sendMouse
                        anchors.fill: parent
                        enabled: window.busy
                                 || inputField.text.trim() !== ""
                                 || window.pendingFiles.length > 0
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (window.busy)
                                window.stopGeneration()
                            else
                                window.submit()
                        }
                    }
                }

                Rectangle {
                    id: effortChip
                    objectName: "effortChip"
                    anchors.right: sendBtn.left
                    anchors.rightMargin: 4
                    // 原版 `EffortPicker.tsx:50-62`：`.chip` 内容自适应（padding-left 4 +
                    // Lightbulb 13 + 可选 gap 5 + 档位名 + padding-right 8），没有箭头；
                    // 当前档位是「默认」时不写名字（`current !== 'default'` 才渲染 label）。
                    // `.chip.cf-mp__effort { padding-left: 4px }`（redesign/model-panel.css:15-17）。
                    width: 4 + 13 + (effortLabelText.visible ? 5 + effortLabelText.implicitWidth : 0) + 8
                    height: 28
                    y: 2
                    radius: Theme.radius
                    readonly property bool open: window.modelPickerOpen && window.pickerMode === "thinking"
                    // 原版 `levels.length === 0` 时整个贴片不出现（EffortPicker.tsx:37）。
                    visible: ((window.effortMenu && window.effortMenu.options) || []).length > 0
                    // 原版 chip 无边框（CDP 实测 border-width 0）：只有灯泡 + 可选文案。
                    // 展开态 `.chip.is-open { background: var(--bg-active); color: var(--fg) }`
                    // （styles/app.css:2874-2877）。
                    color: open ? Theme.bgActive : "transparent"
                    border.width: 0
                    Icon {
                        x: 4
                        anchors.verticalCenter: parent.verticalCenter
                        // 原版 EffortPicker.tsx:60 用 lucide `Lightbulb`，不是 sparkles。
                        name: IconData.lightbulb
                        size: 13
                        color: effortChip.open ? Theme.fg : Theme.fgMuted
                    }
                    Text {
                        id: effortLabelText
                        x: 22
                        anchors.verticalCenter: parent.verticalCenter
                        text: window.effortLabel
                        visible: text !== ""
                        color: effortChip.open ? Theme.fg : Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        font.weight: 500
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: window.openPicker("thinking")
                    }

                    // 思考等级菜单：原版 EffortPicker 把 `.model-pick__menu` 挂在这个贴片
                    // 自己的 `.model-pick` 容器里（`right:0; bottom: calc(100% + 8px)`），
                    // 所以右缘对齐贴片右缘、底边在贴片上沿往上 8px。
                    // 只在本页呈现（`pickerMode === "thinking"`），不靠 z 序猜。
                    ModelPicker {
                        objectName: "thinkingPicker"
                        visible: window.modelPickerOpen && window.pickerMode === "thinking"
                        mode: "thinking"
                        effortMenu: window.effortMenu
                        // deva 实测面板外框 x847..1094（248 宽）；QML 贴片右缘比 deva
                        // 短 1px，面板本身又按贴片内容宽内缩，统一 +2 后左右边框逐像素对齐。
                        x: parent.width - width + 2
                        y: -height - 8
                        onEffortPicked: function (level) { window.pickEffort(level) }
                    }
                }

                // 上下文圆环：在模型贴片左侧，28×28；读数缺失时宽高为 0，不占位。
                ContextRing {
                    id: contextRing
                    objectName: "contextRing"
                    anchors.right: modelChip.left
                    y: 2
                    usage: window.contextUsage
                    labels: window.chatText
                    open: window.contextOpen
                    viewportWidth: window.width
                    onToggleRequested: window.toggleContext()
                }

                Rectangle {
                    id: modelChip
                    objectName: "modelChip"
                    anchors.right: effortChip.left
                    anchors.rightMargin: 4
                    // 原版 `ModelPanel.tsx:70-79`：模型贴片只写模型名（不放服务商色点），
                    // `.chip` 内容自适应：padding-left 8 + label（max-width 168，省略号）+
                    // gap 5 + caret 13 + padding-right 4（redesign/model-panel.css:12-14）。
                    // 宽度自适应后，贴片右缘与弹层右缘一起回到 deva 的 x≈1094。
                    width: 8 + Math.min(modelLabelText.implicitWidth, 168) + 5 + 13 + 4
                    height: 28
                    y: 2
                    radius: Theme.radius
                    readonly property bool open: window.modelPickerOpen && window.pickerMode === "model"
                    // 原版 chip 无边框（CDP 实测 border-width 0）：只有文案 + 箭头。
                    // 展开态同 `.chip.is-open`：底 `--bg-active`、文字转 `--fg`、箭头翻转。
                    color: open ? Theme.bgActive : "transparent"
                    border.width: 0
                    Text {
                        id: modelLabelText
                        x: 8
                        anchors.verticalCenter: parent.verticalCenter
                        // `.chip__label { max-width: 168px; text-overflow: ellipsis }`
                        // （styles/app.css:2883-2888）。
                        width: Math.min(implicitWidth, 168)
                        text: window.modelLabel
                        color: modelChip.open ? Theme.fg : Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        font.weight: 500
                        elide: Text.ElideRight
                    }
                    Icon {
                        anchors.right: parent.right
                        anchors.rightMargin: 4
                        anchors.verticalCenter: parent.verticalCenter
                        name: IconData.chevronDown
                        size: 13
                        rotation: modelChip.open ? 180 : 0
                        color: modelChip.open ? Theme.fg : Theme.fgMuted
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: window.openPicker("model")
                    }

                    // 模型菜单：与思考等级同一套外壳，挂在模型贴片自己的容器里。
                    ModelPicker {
                        objectName: "modelPicker"
                        visible: window.modelPickerOpen && window.pickerMode === "model"
                        mode: "model"
                        groups: window.modelGroups
                        activeRef: window.activeModelRef
                        emptyText: window.chatText.noModel || ""
                        // 同 thinking 面板：deva 外框 x847..1094；+2 后两边框逐像素对齐。
                        x: parent.width - width + 2
                        y: -height - 8
                        onPicked: function (providerId, modelId) { window.pickModel(providerId, modelId) }
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
        modelsView: window.settingsModelsView
        onClose: window.page = "chat"
        onPaneRequested: function (name) { window.page = "settings-" + name }
    }

    function toggleContext() {
        if (window.contextOpen) {
            window.contextOpen = false
            return
        }
        closePicker()
        window.contextOpen = true
    }

    function openPicker(mode) {
        window.contextOpen = false
        if (window.modelPickerOpen && window.pickerMode === mode) {
            closePicker()
            return
        }
        window.pickerMode = mode
        window.modelPickerOpen = true
    }

    function closePicker() {
        window.modelPickerOpen = false
        window.pickerMode = ""
    }

    // ── 函数 ──────────────────────────────────────────────────────────
    function activate(id) {
        if (!id || id === window.activeId)
            return
        shellBridge.openSession(id)
    }

    // 收起列表：Ctrl/Cmd+B 切换（原版 ChatFirstShell.tsx:191-199），并写入 config.json。
    function toggleSidebar() {
        window.sideCollapsed = !window.sideCollapsed
        window.sidePeek = false
        if (shellBridge)
            shellBridge.setSidebarCollapsed(window.sideCollapsed)
    }

    // 悬停「对话」图标：收起状态下 200ms 后浮出列表，离开图标/列表 150ms 后收回
    // （原版 ChatFirstShell.tsx:160-190 的两个定时器）。
    function chatRailHover(entered) {
        if (!window.sideCollapsed)
            return
        if (entered) {
            peekHide.stop()
            peekShow.restart()
        } else {
            peekShow.stop()
            if (!window._sidePeekHover)
                peekHide.restart()
        }
    }
    function sideHover(entered) {
        window._sidePeekHover = entered
        if (entered) {
            peekHide.stop()
            window.sidePeek = true
        } else if (!window.sideCollapsed) {
            window.sidePeek = false
        } else {
            peekHide.restart()
        }
    }
    Timer {
        id: peekShow
        interval: 200
        onTriggered: { if (window.sideCollapsed) window.sidePeek = true }
    }
    Timer {
        id: peekHide
        interval: 150
        onTriggered: { if (!window._sidePeekHover) window.sidePeek = false }
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

    // 停止当前回合（原版 Composer 的停止键 → chat:abort）。没有可停回合时不假装成功。
    function stopGeneration() {
        if (!shellBridge.stopGeneration())
            notify(I18n.t("native.message24"))
    }

    // 把 Python 判定过的附件行并入待发列表（按绝对路径去重）。
    function appendPendingFiles(rows) {
        if (!rows || rows.length === 0)
            return 0
        var merged = window.pendingFiles.slice()
        var added = 0
        for (var i = 0; i < rows.length; i++) {
            var row = rows[i]
            if (!row || !row.supported || !row.path)
                continue
            if (merged.indexOf(row.path) < 0) {
                merged.push(row.path)
                added++
            }
        }
        window.pendingFiles = merged
        return added
    }

    // 拖放：QML 传 URL 列表，Python 返回逐项判定；不支持的项给一次提示。
    function acceptDrop(urls) {
        var rows = shellBridge.acceptDroppedFiles(urls)
        var added = window.appendPendingFiles(rows)
        if (added === 0 && rows && rows.length > 0)
            notify(I18n.t("native.message24"))
    }

    // 空态卡片点击：以该角色开一条新对话（原版 `startWith`：建会话 → 切进去）。
    function quickStart(personaId) {
        if (!personaId || !shellBridge)
            return
        shellBridge.startQuickStart(String(personaId))
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
            notify(I18n.t("chat.deliver.openFailed"))
        return ok
    }

    function deliverableReveal(item) {
        var ok = shellBridge.revealDeliverable(item.toolUseId, item.path)
        if (!ok)
            notify(I18n.t("native.message26"))
        return ok
    }

    function deliverableCopy(item) {
        var ok = shellBridge.copyDeliverablePath(item.path)
        if (!ok)
            notify(I18n.t("native.message27"))
        return ok
    }

    // 右键菜单 / 删除确认：Deva 的菜单项与确认按钮都是真实可点的。
    function openCtxMenu(id, title) {
        window.ctxSessionId = String(id || "")
        window.ctxTitle = String(title || "")
        window.ctxDismissed = false
        window.confirmDismissed = false
        window.ctxUserOpen = true
        window.confirmUserOpen = false
    }

    function dismissCtxMenu() {
        window.ctxDismissed = true
        window.ctxUserOpen = false
    }

    function ctxAction(action) {
        if (action === "new") {
            window.dismissCtxMenu()
            shellBridge.newSession()
        } else if (action === "rename") {
            window.openRenameDialog()
        } else if (action === "select") {
            window.startSelect(window.ctxSessionId || window.activeId)
            window.dismissCtxMenu()
        } else if (action === "archive") {
            var archiveId = window.ctxSessionId || window.activeId
            window.dismissCtxMenu()
            if (!archiveId || !shellBridge.archiveSession(String(archiveId)))
                notify(I18n.t("native.message24"))
        } else if (action === "delete") {
            window.pendingDeleteId = window.ctxSessionId || window.activeId
            window.pendingDeleteTitle = window.ctxTitle || window.activeTitle
            window.dismissCtxMenu()
            window.confirmDismissed = false
            window.confirmUserOpen = true
        }
    }

    // 右键 Rename：原版 `dialog.prompt` 的居中输入框，默认值当前标题；空串提交由
    // `ChatHost.rename_session` 恢复自动标题（取首条用户消息派生），不是这里另写规则。
    function openRenameDialog() {
        var id = window.ctxSessionId || window.activeId
        if (!id)
            return
        window.renameId = String(id)
        window.renameOriginalTitle = String(window.ctxTitle || window.activeTitle || "")
        window.renameValue = window.renameOriginalTitle
        window.dismissCtxMenu()
        window.renameOpen = true
    }

    function cancelRename() {
        window.renameOpen = false
        window.renameId = ""
        window.renameOriginalTitle = ""
        window.renameValue = ""
    }

    function confirmRename() {
        var id = window.renameId || window.activeId
        if (!id || !shellBridge.renameSession(String(id), String(window.renameValue))) {
            notify(I18n.t("native.message31"))
            return
        }
        window.cancelRename()
    }

    // 右键 Select：原版 `select.start(id)` —— 立即把被右键的会话放进选择集并进入多选；
    // 底部 `ThreadSelectBar` 显示数量、全选、归档/移回与退出。
    function startSelect(id) {
        window.selectMode = true
        window.selectedSessions = id ? [String(id)] : []
    }

    function toggleSelect(id) {
        var key = String(id || "")
        if (!key)
            return
        // 原地更新，显式通知绑定，避免每次点击复制整个大集合。
        var next = window.selectedSessions
        var at = next.indexOf(key)
        if (at >= 0)
            next.splice(at, 1)
        else
            next.push(key)
        window.selectedSessionsChanged()
    }

    function toggleSelectAll() {
        var all = window.listedSessions || []
        if (window.selectedSessions.length === all.length && all.length > 0) {
            window.selectedSessions = []
            return
        }
        window.selectedSessions = window.listedSessionIds.slice()
        window.allListedSelected = true
    }

    function archiveSelected() {
        var ids = window.selectedSessions.slice()
        if (ids.length === 0) {
            window.exitSelect()
            return
        }
        var failed = shellBridge.archiveSessions(ids, !window.archiveView)
        window.exitSelect()
        if (failed > 0)
            notify(I18n.t("native.message30"))
    }

    function exitSelect() {
        window.selectMode = false
        window.selectedSessions = []
    }

    function openArchiveView() {
        window.archiveView = true
        window.exitSelect()
        window.dismissCtxMenu()
    }

    function closeArchiveView() {
        window.archiveView = false
        window.exitSelect()
        window.dismissCtxMenu()
    }

    function cancelDelete() {
        window.confirmUserOpen = false
        window.confirmDismissed = true
        window.pendingDeleteId = ""
        window.pendingDeleteTitle = ""
    }

    function confirmDelete() {
        var id = window.pendingDeleteId || window.activeId
        if (!id || !shellBridge.deleteSession(id)) {
            notify(I18n.t("native.message21"))
            return
        }
        window.cancelDelete()
    }

    // 交互态页面由 Python 在 QML 建好后写入，所以这些状态要监听 page 变化才真生效。
    onPageChanged: {
        window.ctxDismissed = false
        window.confirmDismissed = false
        window.ctxUserOpen = false
        window.confirmUserOpen = false
        window.renameOpen = false
        window.selectMode = false
        window.selectedSessions = []
        window.archiveView = false
        Qt.callLater(applyPageState)
    }

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
            notify(I18n.t("native.message20"))
            return
        }
        window.modelLabel = findModelName(providerId, modelId)
        window.activeModelRef = String(providerId) + ":" + String(modelId)
        window.pickerMode = ""
        window.modelPickerOpen = false
    }

    function pickEffort(level) {
        if (!shellBridge.setActiveEffort(String(level))) {
            notify(I18n.t("native.message19"))
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

    // 右键菜单：Deva `Rail.tsx` 线程菜单 5 项，CSS `.cf-ctx` 实测
    // (160,90) 148×157、padding 5、项 136×29、圆角 8、阴影 0 6 24、无分隔线。
    Item {
        id: ctxLayer
        objectName: "ctxLayer"
        visible: window.ctxOpen
        anchors.fill: parent
        z: 40

        // 点击菜单外关闭：Deva `.cf-ctx__backdrop` 的透明点击层。
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: window.dismissCtxMenu()
        }

        // `.cf-ctx` 的 `box-shadow: var(--shadow)`（redesign.css:455）：浅色 0 6 24 / 12%。
        SoftShadow {
            id: ctxMenuShadow
            target: ctxMenu
        }

        Rectangle {
            id: ctxMenu
            objectName: "ctxMenu"
            x: 160
            y: 90
            width: 148
            height: 157
            radius: Theme.radiusLg
            color: Theme.bgElevated
            border.width: 1
            border.color: Theme.border

            // 面板本身吞掉点击，避免点在 padding 上把菜单关掉。
            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            Column {
                x: 6
                y: 6
                spacing: 0
                Repeater {
                    model: [
                        { label: I18n.t("cf.newChat"), icon: IconData.plus, danger: false, action: "new" },
                        { label: I18n.t("cf.renameChat"), icon: IconData.pencil, danger: false, action: "rename" },
                        { label: I18n.t("cf.multiSelect"), icon: IconData.listChecks, danger: false, action: "select" },
                        { label: I18n.t("cf.archive"), icon: IconData.archive, danger: false, action: "archive" },
                        { label: I18n.t("common.delete"), icon: IconData.trash2, danger: true, action: "delete" }
                    ]
                    delegate: Rectangle {
                        required property int index
                        required property var modelData
                        objectName: "ctxMenuItem" + index
                        width: 136
                        height: 29
                        radius: Theme.radius
                        color: itemMouse.containsMouse
                               ? (modelData.danger
                                  ? Qt.rgba(229 / 255, 72 / 255, 77 / 255, 0.14)
                                  : Theme.bgHover)
                               : "transparent"
                        Row {
                            x: 9
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 8
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
                        MouseArea {
                            id: itemMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: window.ctxAction(modelData.action)
                        }
                    }
                }
            }
        }
    }

    // 删除确认框：Deva `Modal` / `DialogProvider` 实测卡片 (430,317) 420×186，
    // 背板 rgba(0,0,0,.42)，标题 15/600，正文 13/1.6，按钮 30px、Cancel 68、Delete 69。
    Item {
        id: confirmLayer
        objectName: "confirmLayer"
        visible: window.confirmOpen
        anchors.fill: parent
        z: 60

        Rectangle {
            id: confirmBackdrop
            objectName: "confirmBackdrop"
            anchors.fill: parent
            color: Theme.backdrop

            // Deva Modal：只有点在背板自身（卡片外）才取消。
            MouseArea {
                anchors.fill: parent
                onClicked: window.cancelDelete()
            }
        }

        // `.modal__card` 的 `box-shadow: var(--shadow)`：浅色 0 6 24 / 12%。
        SoftShadow {
            id: confirmDialogShadow
            target: confirmDialog
        }

        Rectangle {
            id: confirmDialog
            objectName: "confirmDialog"
            x: 430
            y: 317
            width: 420
            height: 186
            radius: Theme.radiusLg
            color: Theme.bgElevated
            border.width: 1
            border.color: Theme.border

            // 卡片吞掉点击，避免点正文时穿透到背板触发取消。
            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            Text {
                x: 20
                y: 20
                width: parent.width - 40
                wrapMode: Text.WordWrap
                lineHeight: 22
                lineHeightMode: Text.FixedHeight
                text: I18n.t("native.message8") + (window.pendingDeleteTitle || window.activeTitle) + "”?"
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }
            Text {
                x: 20
                y: 80
                width: parent.width - 40
                wrapMode: Text.WordWrap
                lineHeight: 21
                lineHeightMode: Text.FixedHeight
                text: I18n.t("cf.deleteChatConfirm")
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 13
            }

            Rectangle {
                id: cancelButton
                objectName: "confirmCancel"
                x: 253
                y: 136
                width: 70
                height: 30
                radius: Theme.radiusSm
                color: cancelMouse.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: I18n.t("common.cancel")
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: cancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.cancelDelete()
                }
            }

            Rectangle {
                id: deleteButton
                objectName: "confirmDelete"
                x: 330
                y: 135
                width: 69
                height: 30
                radius: Theme.radiusSm
                color: deleteMouse.containsMouse ? Qt.lighter(Theme.danger, 1.07) : Theme.danger
                Text {
                    anchors.centerIn: parent
                    anchors.horizontalCenterOffset: -1
                    anchors.verticalCenterOffset: 1
                    text: I18n.t("common.delete")
                    color: "#ffffff"
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: deleteMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.confirmDelete()
                }
            }
        }
    }

    // 重命名输入框：原版 `dialog.prompt` 的居中卡片（不是行内编辑）。标题默认当前标题，
    // 留空提交走 ChatHost 的「恢复自动标题」规则；确认按钮只在值真正变化后可用。
    Item {
        id: renameLayer
        objectName: "renameLayer"
        visible: window.renameOpen
        anchors.fill: parent
        z: 55

        Rectangle {
            objectName: "renameBackdrop"
            anchors.fill: parent
            color: Theme.backdrop
            MouseArea {
                anchors.fill: parent
                onClicked: window.cancelRename()
            }
        }

        SoftShadow {
            id: renameDialogShadow
            target: renameDialog
        }

        Rectangle {
            id: renameDialog
            objectName: "renameDialog"
            x: 430
            y: 317
            width: 420
            height: 186
            radius: Theme.radiusLg
            color: Theme.bgElevated
            border.width: 1
            border.color: Theme.border
            readonly property bool canSubmit: window.renameValue.trim() !== window.renameOriginalTitle.trim()

            MouseArea {
                anchors.fill: parent
                onClicked: {}
            }

            Text {
                x: 20
                y: 20
                text: I18n.t("cf.renameChatTitle")
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }

            Rectangle {
                objectName: "renameInputBox"
                x: 20
                y: 64
                width: parent.width - 40
                height: 40
                radius: Theme.radius
                color: Theme.bg
                border.width: 1
                border.color: renameInput.activeFocus ? Theme.accent : Theme.borderStrong

                Text {
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    visible: renameInput.text.length === 0
                    text: I18n.t("cf.renamePlaceholder")
                    color: Theme.fgSubtle
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                }

                TextInput {
                    id: renameInput
                    objectName: "renameInput"
                    x: 12
                    y: 0
                    width: parent.width - 24
                    height: parent.height
                    text: window.renameValue
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    verticalAlignment: TextInput.AlignVCenter
                    selectByMouse: true
                    clip: true
                    onTextChanged: {
                        if (window.renameValue !== text)
                            window.renameValue = text
                    }
                    Keys.onReturnPressed: window.confirmRename()
                    Keys.onEscapePressed: window.cancelRename()
                }
            }

            Rectangle {
                id: renameCancelButton
                objectName: "renameCancel"
                x: 253
                y: 136
                width: 70
                height: 30
                radius: Theme.radiusSm
                color: renameCancelMouse.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: I18n.t("common.cancel")
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: renameCancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: window.cancelRename()
                }
            }

            Rectangle {
                id: renameConfirmButton
                objectName: "renameConfirm"
                x: 330
                y: 135
                width: 69
                height: 30
                radius: Theme.radiusSm
                opacity: renameDialog.canSubmit ? 1 : 0.45
                color: renameConfirmMouse.containsMouse && renameDialog.canSubmit
                       ? Qt.lighter(Theme.accent, 1.08) : Theme.accent
                Text {
                    anchors.centerIn: parent
                    text: I18n.t("cf.renameChat")
                    color: Theme.accentFg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: renameConfirmMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (renameDialog.canSubmit)
                            window.confirmRename()
                    }
                }
            }
        }

        onVisibleChanged: {
            if (visible)
                Qt.callLater(function () {
                    renameInput.forceActiveFocus()
                    renameInput.selectAll()
                })
        }
    }

    // 窗口控制叠加层：原版 Electron Linux `titleBarOverlay` 的实色块，右上角 96×40，
    // 三个 32×40 按钮右对齐贴边。z 高于设置弹框/遮罩（Main.qml 内最高 60），
    // 因为原生叠加层永远画在网页与遮罩之上；按钮行为对应 deva main/index.ts:311-318
    // 的 minimize / isMaximized ? unmaximize : maximize / close。
    Rectangle {
        id: windowControls
        visible: !window.macChrome
        objectName: "windowControls"
        x: window.width - width
        y: 0
        width: 96
        height: 40
        z: 1000
        color: Theme.dark ? "#1e1e20" : "#ffffff"

        Row {
            anchors.fill: parent
            spacing: 0

            WindowControlButton {
                objectName: "windowControlMinimize"
                kind: 0
                onClicked: window.showMinimized()
            }
            WindowControlButton {
                objectName: "windowControlMaximize"
                kind: 1
                onClicked: {
                    if (window.visibility === Window.Maximized)
                        window.showNormal()
                    else
                        window.showMaximized()
                }
            }
            WindowControlButton {
                objectName: "windowControlClose"
                kind: 2
                onClicked: window.close()
            }
        }
    }

    // 5px 边缘交给 WM 缩放；最大化/全屏时禁用，不覆盖正文。
    Repeater {
        model: [Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge, Qt.TopEdge | Qt.RightEdge,
                Qt.LeftEdge, Qt.RightEdge, Qt.BottomEdge | Qt.LeftEdge,
                Qt.BottomEdge, Qt.BottomEdge | Qt.RightEdge]
        MouseArea {
            id: resizeHit
            objectName: "windowResize" + index
            readonly property int edges: modelData
            readonly property bool edgeLeft: (edges & Qt.LeftEdge) !== 0
            readonly property bool edgeRight: (edges & Qt.RightEdge) !== 0
            readonly property bool edgeTop: (edges & Qt.TopEdge) !== 0
            readonly property bool edgeBottom: (edges & Qt.BottomEdge) !== 0
            x: edgeLeft ? 0 : edgeRight ? window.width - 5 : 5
            y: edgeTop ? 0 : edgeBottom ? window.height - 5 : 5
            width: edgeLeft || edgeRight ? 5 : window.width - 10
            height: edgeTop || edgeBottom ? 5 : window.height - 10
            z: 2000
            // 正文滚动条占右侧 8px：保留其 hover/拖动，贴窗沿 1px 仍可缩放。
            containmentMask: QtObject {
                function contains(p: point): bool {
                    if (p.x < 0 || p.y < 0 || p.x >= resizeHit.width || p.y >= resizeHit.height)
                        return false
                    if (index !== 4 || !bodyScrollbar.visible || bodyScrollbar.size >= 1)
                        return true
                    var local = bodyScrollbar.mapFromItem(resizeHit, p.x, p.y)
                    return local.y < 0 || local.y >= bodyScrollbar.height || p.x >= 4
                }
            }
            enabled: !window.macChrome && window.visibility !== Window.Maximized && window.visibility !== Window.FullScreen
            hoverEnabled: true
            cursorShape: (edgeLeft || edgeRight) && (edgeTop || edgeBottom)
                         ? ((edgeLeft && edgeTop) || (edgeRight && edgeBottom) ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor)
                         : (edgeLeft || edgeRight ? Qt.SizeHorCursor : Qt.SizeVerCursor)
            onPressed: window.startSystemResize(edges)
        }
    }

    // 当前会话的头像角色（用于输入框占位文案 "Message <name>…"）
    readonly property string activePersonaName: {
        for (var i = 0; i < sessions.length; i++)
            if (sessions[i].id === activeId)
                return sessions[i].personaName || I18n.t("cf.assistant")
        return I18n.t("cf.assistant")
    }
    Rectangle {
        anchors.fill: parent; z: 100; visible: window.page === "personas-editor"; color: Theme.bg
        SettingsButton { x: 20; y: 20; text: I18n.t("common.back"); onClicked: window.page = "chat" }
        Loader { anchors.fill: parent; anchors.margins: 20; anchors.topMargin: 64
            active: window.page === "personas-editor"
            sourceComponent: Component { PluginSettingsPane { mode: "identities" } }
        }
    }

}
