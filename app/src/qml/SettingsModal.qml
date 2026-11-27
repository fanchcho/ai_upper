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
    // 截图/深链页可指定 Models 的初始子视图：list | provider | advanced。
    property string modelsView: "list"
    // About 版本号只从 ShellBridge.appVersion() 取，不在 QML 写版本字面量。
    readonly property string appVersion: shellBridge ? shellBridge.appVersion() : ""
    // 删除服务商确认：原版 `dialog.confirm({ title: name, message, confirmText: delete,
    // variant: 'danger' })`，确认后删服务商并退回列表（`ModelSettings.tsx:195-207`）。
    // 放在 root 上，确认卡片才不必依赖 Models 面板当前是否已加载。
    property bool providerDeleteOpen: false
    property string providerDeleteName: ""
    // 确认卡片的按钮/正文文案也取自同一份投影（`mvvm.services.settings_models`），
    // 卡片挂在 root 上，因此在这里取一份 labels，不在 QML 写字面量。
    readonly property var modelsLabels: shellBridge ? (I18n.locale, shellBridge.modelsPaneLabels()) : ({})
    signal close()
    signal paneRequested(string name)

    // 背板：redesign.css:3135-3142 `.cf-modal__backdrop` = rgba(0,0,0,.42) + 全屏；
    // SettingsPane.tsx:54-55 明确遮罩层不响应点击，关闭只走右上角按钮。
    Rectangle {
        anchors.fill: parent
        color: Theme.backdrop
    }

    // 阴影：原版 `.cf-modal { box-shadow: var(--shadow) }`（redesign.css:3153）＝浅色
    // `0 6px 24px rgba(0,0,0,.12)`、深色 `0 8px 30px rgba(0,0,0,.5)`（tokens.css:82/:149）。
    // 用 Canvas 版 SoftShadow（软件光栅下也出影，参数集中在 SoftShadow.qml），替换硬边外扩矩形近似。
    SoftShadow {
        target: box
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
                text: I18n.t("cf.settings")
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
                        // 原版 SettingsPane.tsx:48-51 的导航顺序/图标：
                        //   general=Cog、models=Brain、extensions=Puzzle、about=Info（size=15）。
                        // QML 旧版把前三个错写成 settings2 / blocks / cog，字形与语义都不对。
                        model: [
                            { key: "general", label: I18n.t("settings.general"), icon: IconData.cog },
                            { key: "models", label: I18n.t("settings.models"), icon: IconData.brain },
                            { key: "extensions", label: I18n.t("extensions.title"), icon: IconData.puzzle },
                            { key: "about", label: I18n.t("settings.about"), icon: IconData.info }
                        ]
                        delegate: Rectangle {
                            required property var modelData
                            objectName: "settingsNav_" + modelData.key
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
                                    objectName: "settingsNavIcon_" + modelData.key
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

            // 右窗格：原版 `.cf-modal__body` 两列 168px + minmax(0,1fr)，导航列宽 168
            // 已含右边框；内容列从 x=168 起（实测窗格内容左缘 x=449，padding 20 后 x=469）。
            Item {
                id: paneArea
                x: 168
                y: 0
                width: parent.width - 168
                height: parent.height

                Loader {
                    id: modelsLoader
                    anchors.fill: parent
                    sourceComponent: ["custom-model", "mcp", "identities"].indexOf(root.pane) >= 0 ? pluginPane
                                   : root.pane === "about" ? aboutPane
                                   : root.pane === "models" ? modelsPane
                                   : root.pane === "extensions" ? extensionsPane
                                   : generalPane
                }
            }
        }
    }

    Component { id: pluginPane; Item {
        SettingsButton { objectName: "pluginBack"; x: 20; y: 12; text: I18n.t("common.back"); onClicked: root.paneRequested(root.pane === "custom-model" ? "models" : "extensions") }
        PluginSettingsPane { anchors.fill: parent; anchors.topMargin: 48; mode: root.pane }
    } }

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
                        id: segmentOption
                        required property int index
                        required property string modelData
                        width: optText.implicitWidth + 24
                        height: 24
                        radius: Theme.radiusSm
                        color: index === row.current ? Theme.bg : "transparent"
                        // deva .cf-seg__opt.is-on 使用同一 --shadow；只给选中项投影。
                        SoftShadow {
                            target: segmentOption
                            visible: segmentOption.index === row.current
                            x: -pad
                            y: -pad
                            z: -1
                        }
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
                y: 18
                text: I18n.t("settings.general")
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
                    objectName: "settingsLanguageChoice"
                    label: I18n.t("settings.language")
                    options: [I18n.t("finish.language.chinese"), I18n.t("finish.language.english")]
                    current: shellBridge ? (I18n.locale, shellBridge.language()) === "zh" ? 0 : 1 : 1
                    onPicked: function (i) { shellBridge.setLanguage(i === 0 ? "zh" : "en") }
                }
                SetRow {
                    width: parent.width
                    objectName: "settingsThemeChoice"
                    label: I18n.t("settings.theme")
                    options: [I18n.t("settings.themeSystem"), I18n.t("settings.themeLight"), I18n.t("settings.themeDark")]
                    current: shellBridge ? ["system", "light", "dark"].indexOf(shellBridge.themeChoice) : 1
                    onPicked: function (i) { shellBridge.setTheme(["system", "light", "dark"][i]) }
                }
                SetRow {
                    width: parent.width
                    label: I18n.t("settings.chatFontSize")
                    options: [I18n.t("settings.chatFontSm"), I18n.t("settings.chatFontMd"), I18n.t("settings.chatFontLg"), I18n.t("settings.chatFontXl")]
                    current: shellBridge ? shellBridge.textSizeIndex() : 1
                    onPicked: function (i) { shellBridge.setTextSize(i) }
                }
            }
        }
    }

    // ── Models：服务商列表（52px 行）→ 详情（返回 / Wrench / 启用）→ 高级设置（自定义请求头）──
    // 几何逐值取自原版只读源码 `features/settings/ModelSettings.tsx`、
    // `features/settings/ProviderAdvanced.tsx` 与 `styles/app.css`：
    //   `.cf-pane` 内边距 16px 20px；`.models__head` 28px + 下间距 16px；
    //   `.provider-row` min-height:52px、padding:10px 14px、gap:12px；
    //   `.provider-row__dot` 10×10；`.provider-row__sub` 11.5px / fg-subtle；
    //   `.provider-detail__topbar` 30px + 下间距 16px；`.provider-detail__head` 名称 18px、
    //     下边框上方留 16px；`.provider-detail__name-input` 只用于自定义服务商；
    //   `.field` 下间距 20px；`.field__row-between` 下间距 8px；`.model-list` 1px 边框、radius 8；
    //   `.model-row` 44px、padding 0 12px、gap 8px；`.header-item__name` 占 34%。
    // 数据只走已入库的 `mvvm.services.settings_models` 投影：`modelRows()` /
    // `modelsPaneLabels()` / `providerDetail()`，写回只走 `setProviderHeaders()` /
    // `setProviderField()`；QML 不新建数据源，也不在界面重算保留头规则。
    Component {
        id: modelsPane
        Item {
            id: modPane
            property var rows: shellBridge ? (I18n.locale, shellBridge.modelRows()) : []
            property var text: shellBridge ? (I18n.locale, shellBridge.modelsPaneLabels()) : ({})
            // 列表 / 详情 / 高级设置三态；page=settings-models-* 时由 Main.qml 指定初始态。
            property string view: "list"
            property string selectedId: ""
            property var detail: ({})
            property var fetchedModels: []
            property string fetchMessage: ""
            function fetchModels() {
                if (!shellBridge || selectedId === "") return
                var result = shellBridge.providerModels(selectedId)
                fetchedModels = result.models || []
                fetchMessage = result.ok ? "" : (result.message || "拉取失败")
                modelsPopup.open()
            }
            property var headerRows: []


            function applyInitialView() {
                if (root.modelsView === "list") {
                    view = "list"
                    return
                }
                if (rows.length > 0) {
                    openProvider(rows[0].id)
                    if (root.modelsView === "advanced") view = "advanced"
                }
            }

            Component.onCompleted: applyInitialView()

            // qml_shell 在 QML 加载完成后才写 `page`；监听 modelsView 的后续变化，
            // 截图页才能从默认 list 切到 provider / advanced。
            Connections {
                target: root
                function onModelsViewChanged() { modPane.applyInitialView() }
            }

            Connections {
                target: shellBridge
                function onLocaleChanged() { modPane.refreshRows(); modPane.reloadDetail() }
            }

            function refreshRows() {
                rows = shellBridge ? (I18n.locale, shellBridge.modelRows()) : []
            }

            function openProvider(providerId) {
                selectedId = providerId
                reloadDetail()
                view = "detail"
            }

            function requestDelete() {
                if (selectedId === "") return
                root.providerDeleteName = detail.name || ""
                root.providerDeleteOpen = true
            }

            function confirmDelete() {
                if (!shellBridge || selectedId === "") {
                    root.providerDeleteOpen = false
                    return
                }
                var ok = shellBridge.deleteProvider(selectedId)
                root.providerDeleteOpen = false
                if (ok) backToList()
            }

            function reloadDetail() {
                detail = shellBridge ? shellBridge.providerDetail(selectedId) : ({})
                var list = (detail && detail.headers) ? detail.headers : []
                var next = []
                for (var i = 0; i < list.length; i++) {
                    next.push({
                        name: list[i].name || "",
                        value: list[i].value || "",
                        issueText: list[i].issueText || ""
                    })
                }
                headerRows = next
            }

            function openAdvanced() {
                reloadDetail()
                view = "advanced"
            }

            function backToList() {
                view = "list"
                selectedId = ""
                detail = ({})
                headerRows = []
                refreshRows()
            }

            function persistHeaders() {
                if (!shellBridge || selectedId === "") return
                var out = []
                for (var i = 0; i < headerRows.length; i++) {
                    out.push({
                        name: headerRows[i].name || "",
                        value: headerRows[i].value || ""
                    })
                }
                shellBridge.setProviderHeaders(selectedId, out)
            }

            function addHeader() {
                var next = []
                for (var i = 0; i < headerRows.length; i++) next.push(headerRows[i])
                next.push({ name: "", value: "", issueText: "" })
                headerRows = next
                headerSaveTimer.restart()
            }

            function removeHeader(index) {
                if (index < 0 || index >= headerRows.length) return
                var next = []
                for (var i = 0; i < headerRows.length; i++) {
                    if (i !== index) next.push(headerRows[i])
                }
                headerRows = next
                persistHeaders()
            }

            function editHeader(index, field, value) {
                if (index < 0 || index >= headerRows.length) return
                // 数组元素是 JS 对象；原地改，不重绑整个 Repeater（否则输入框会丢焦点）。
                headerRows[index][field] = value
                headerRows[index].issueText = ""
                headerSaveTimer.restart()
            }

            Timer {
                id: headerSaveTimer
                interval: 350
                repeat: false
                onTriggered: modPane.persistHeaders()
            }

            // ── 列表态 ────────────────────────────────────────────────
            Item {
                id: modelsListView
                anchors.fill: parent
                visible: modPane.view === "list"

                Item {
                    id: modHead
                    x: 20
                    y: 16
                    width: parent.width - 40
                    height: 28

                    Text {
                        id: modTitle
                        anchors.verticalCenter: parent.verticalCenter
                        text: modPane.text.providers || ""
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 15
                        font.weight: 700
                    }

                    Rectangle {
                        id: addBtn
                        objectName: "modelsAddProvider"
                        anchors.right: parent.right
                        width: 28
                        height: 28
                        radius: Theme.radius
                        color: addHover.hovered ? Theme.bgHover : Theme.bgElevated
                        border.width: 1
                        border.color: Theme.border
                        Icon {
                            anchors.centerIn: parent
                            name: IconData.plus
                            size: 16
                            color: addHover.hovered ? Theme.fg : Theme.fgMuted
                        }
                        HoverHandler { id: addHover }
                        // 原版 `onAddProvider('llm')`：新建自定义服务商后直接进其详情
                        // （`ModelSettings.tsx:223-230`；`addProvider` 返回新 id）。
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (!shellBridge) return
                                var newId = shellBridge.addProvider()
                                if (!newId) return
                                modPane.refreshRows()
                                modPane.openProvider(newId)
                            }
                        }
                    }
                    SettingsButton {
                        objectName: "modelsCustomNetwork"
                        anchors.right: addBtn.left
                        anchors.rightMargin: 8
                        height: 28
                        text: I18n.t("native.message29")
                        onClicked: root.paneRequested("custom-model")
                    }
                }

                Rectangle {
                    id: modRows
                    // 与标题/加号同处 `.cf-pane` 内容列（pane x=20、宽 pane-40）：
                    // 原版 `.models__rows` 实测外框 510×54，左边框 x=469、右边框 x=978。
                    x: 20
                    y: 60   // 16（上内边距）+ 28（head）+ 16（`.models__head` 下间距）
                    width: parent.width - 40
                    height: modPane.rows.length === 0
                            ? modEmpty.implicitHeight + 32
                            : modPane.rows.length * 52 + 2
                    radius: Theme.radiusLg
                    color: "transparent"
                    border.width: 1
                    border.color: Theme.border
                    clip: true

                    Text {
                        id: modEmpty
                        visible: modPane.rows.length === 0
                        x: 1
                        y: 17
                        width: parent.width - 2
                        horizontalAlignment: Text.AlignHCenter
                        text: modPane.text.noProvidersYet || ""
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                    }

                    ListView {
                        id: modList
                        visible: modPane.rows.length > 0
                        x: 1
                        y: 1
                        width: parent.width - 2
                        height: parent.height - 2
                        clip: true
                        model: modPane.rows
                        delegate: Rectangle {
                            id: providerRow
                            required property var modelData
                            required property int index

                            width: modList.width
                            height: 52
                            color: providerMouse.containsMouse ? Theme.bgHover : "transparent"

                            // `.provider-row + .provider-row`：只在行与行之间画 1px 顶线。
                            Rectangle {
                                visible: providerRow.index > 0
                                anchors.top: parent.top
                                width: parent.width
                                height: 1
                                color: Theme.border
                            }

                            // `.provider-row__dot`：启用绿点 / 未启用灰点。
                            Rectangle {
                                x: 14
                                anchors.verticalCenter: parent.verticalCenter
                                width: 10
                                height: 10
                                radius: 5
                                color: providerRow.modelData.enabled === true ? Theme.success : Theme.fgSubtle
                            }

                            Column {
                                id: providerMain
                                anchors.left: parent.left
                                anchors.leftMargin: 36   // 14 padding + 10 dot + 12 gap
                                anchors.right: providerAside.left
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2

                                Text {
                                    width: parent.width
                                    text: providerRow.modelData.name || ""
                                    color: Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    font.weight: 600
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: providerRow.modelData.detail || ""
                                    color: Theme.fgMuted
                                    font.family: Theme.sansFamily
                                    // `.provider-row__sub`（`app.css:4567-4573`）：font-size:11.5px。
                                    // pixelSize 只收整数，半像素用 pointSize 表达（96dpi 下
                                    // 11.5px = 8.625pt），与 Main.qml:1351 的 13.5px 同一做法。
                                    font.pointSize: 8.625
                                    elide: Text.ElideRight
                                }
                            }

                            Row {
                                id: providerAside
                                anchors.right: parent.right
                                anchors.rightMargin: 14
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8

                                // `.provider-row__aside`（`app.css:4574-4580`）是 `align-items:center`：
                                // 14px 告警三角在 16px 行高里垂直居中，故下移 1px。QML 的 Row
                                // 只排 x、不动 y，不加这一行三角会比 chevron 高 1px（实测 deva
                                // 三角上沿 y=265、改前 QML 为 264）。
                                Icon {
                                    visible: providerRow.modelData.warn === true
                                    y: 1
                                    name: IconData.alertTriangle
                                    size: 14
                                    color: Theme.warning
                                }
                                Icon {
                                    name: IconData.chevronRight
                                    size: 16
                                    color: Theme.fgSubtle
                                }
                            }

                            MouseArea {
                                id: providerMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: modPane.openProvider(providerRow.modelData.id)
                            }
                        }
                    }
                }
            }

            // ── 详情态 ────────────────────────────────────────────────
            Item {
                id: detailView
                x: 20
                y: 16
                width: parent.width - 40
                height: parent.height - 32
                visible: modPane.view === "detail"

                Item {
                    id: detailTopbar
                    width: parent.width
                    height: 30

                    Item {
                        id: detailBack
                        anchors.verticalCenter: parent.verticalCenter
                        width: detailBackRow.width + 16
                        height: 24

                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusSm
                            color: detailBackMouse.containsMouse ? Theme.bgHover : "transparent"
                        }
                        Row {
                            id: detailBackRow
                            x: 6
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Icon {
                                name: IconData.chevronLeft
                                size: 16
                                color: detailBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
                            }
                            Text {
                                text: modPane.text.back || ""
                                color: detailBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
                                font.family: Theme.sansFamily
                                font.pixelSize: 13
                            }
                        }
                        MouseArea {
                            id: detailBackMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modPane.backToList()
                        }
                    }

                    Row {
                        id: detailActions
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        SettingsButton {
                            objectName: "providerFetchModels"
                            height: 30
                            text: "拉取模型"
                            onClicked: modPane.fetchModels()
                        }

                        // `.provider-detail__del`（`app.css:4905`）：官方与自定义服务商都可删，
                        // 点按弹确认（原版 `onDeleteProvider`，`ModelSettings.tsx:195`）。
                        Rectangle {
                            id: detailDelete
                            objectName: "providerDelete"
                            visible: modPane.selectedId !== ""
                            width: 30
                            height: 30
                            radius: Theme.radiusSm
                            color: deleteMouse.containsMouse ? Theme.bgHover : "transparent"
                            Icon {
                                anchors.centerIn: parent
                                name: IconData.trash2
                                size: 15
                                color: deleteMouse.containsMouse ? Theme.danger : Theme.fgSubtle
                            }
                            MouseArea {
                                id: deleteMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: modPane.requestDelete()
                            }
                        }

                        Rectangle {
                            id: detailWrench
                            objectName: "providerWrench"
                            visible: modPane.detail.advanced === true
                            width: 30
                            height: 30
                            radius: Theme.radiusSm
                            color: wrenchMouse.containsMouse ? Theme.bgHover : "transparent"
                            Icon {
                                anchors.centerIn: parent
                                name: IconData.wrench
                                size: 15
                                color: wrenchMouse.containsMouse ? Theme.fg : Theme.fgMuted
                            }
                            MouseArea {
                                id: wrenchMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: modPane.openAdvanced()
                            }
                        }

                        Text {
                            text: modPane.text.enableProvider || modPane.text.enabled || ""
                            height: 30
                            verticalAlignment: Text.AlignVCenter
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 12
                        }

                        Item {
                            id: detailSwitch
                            width: 36
                            height: 20
                            anchors.verticalCenter: parent.verticalCenter

                            Rectangle {
                                anchors.fill: parent
                                radius: 10
                                color: modPane.detail.enabled === true ? Theme.accent : Theme.bgActive
                            }
                            Rectangle {
                                x: modPane.detail.enabled === true ? 18 : 2
                                y: 2
                                width: 16
                                height: 16
                                radius: 8
                                color: Theme.switchThumb
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!shellBridge) return
                                    shellBridge.setProviderField(modPane.selectedId, "enabled",
                                                                 modPane.detail.enabled === true ? "0" : "1")
                                    modPane.reloadDetail()
                                }
                            }
                        }
                    }
                }

                Popup {
                    id: modelsPopup
                    objectName: "providerModelsPopup"
                    x: parent.width - 300
                    y: 40
                    width: 280
                    height: Math.min(320, 40 + (modPane.fetchedModels || []).length * 26)
                    padding: 8
                    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusSm }
                    Column {
                        width: parent.width - 16
                        Text { text: modPane.fetchMessage.length ? modPane.fetchMessage : "模型列表"; color: Theme.fgMuted; height: 24 }
                        Repeater {
                            model: modPane.fetchedModels || []
                            delegate: Text {
                                required property string modelData
                                width: parent.width; height: 24
                                text: modelData; color: Theme.fg; font.pixelSize: 12
                            }
                        }
                    }
                }

                Item {
                    id: detailHead
                    y: 46   // topbar 30 + `.provider-detail__topbar` margin-bottom 16
                    width: parent.width
                    height: 38

                    Text {
                        x: 0
                        y: 0
                        width: parent.width
                        text: modPane.detail.name || ""
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 18
                        font.weight: 600
                        elide: Text.ElideRight
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.border
                    }
                }

                Rectangle {
                    id: detailWarn
                    visible: modPane.detail.warn === true
                    y: detailHead.y + detailHead.height + 12   // head 下间距 20 + `.provider-warn` margin-top -8
                    width: parent.width
                    height: detailWarnRow.implicitHeight + 16
                    radius: Theme.radiusSm
                    color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.08)
                    border.width: 1
                    border.color: Qt.rgba(Theme.warning.r, Theme.warning.g, Theme.warning.b, 0.4)

                    Row {
                        id: detailWarnRow
                        x: 10
                        y: 8
                        spacing: 6
                        Icon {
                            name: IconData.alertTriangle
                            size: 13
                            color: Theme.warning
                        }
                        Text {
                            text: modPane.text.keyMissingWarn || ""
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 12
                        }
                    }
                }

                Item {
                    id: detailModels
                    y: detailWarn.visible ? detailWarn.y + detailWarn.height + 16
                                             : detailHead.y + detailHead.height + 20
                    width: parent.width
                    height: detailModelsLabel.implicitHeight + 8 + detailModelsBox.height

                    Text {
                        id: detailModelsLabel
                        text: modPane.detail.modelList || ""
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.weight: 600
                    }

                    Rectangle {
                        id: detailModelsBox
                        y: 21   // label 行高约 13 + `.field__row-between` 下间距 8
                        width: parent.width
                        height: {
                            var list = modPane.detail.models || []
                            if (list.length === 0) return 49
                            return list.length * 44 + Math.max(0, list.length - 1) * 1 + 2
                        }
                        radius: Theme.radius
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.border
                        clip: true

                        Text {
                            visible: (modPane.detail.models || []).length === 0
                            x: 1
                            y: 17
                            width: parent.width - 2
                            horizontalAlignment: Text.AlignHCenter
                            text: modPane.text.noModels || ""
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }

                        Column {
                            x: 1
                            y: 1
                            width: parent.width - 2
                            Repeater {
                                model: modPane.detail.models || []
                                delegate: Rectangle {
                                    id: detailModelRow
                                    required property var modelData
                                    required property int index
                                    width: detailModelsBox.width - 2
                                    height: 44
                                    color: "transparent"

                                    Rectangle {
                                        visible: detailModelRow.index < (modPane.detail.models || []).length - 1
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        height: 1
                                        color: Theme.border
                                    }

                                    Row {
                                        x: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 8
                                        Text {
                                            text: detailModelRow.modelData.name || ""
                                            color: Theme.fg
                                            font.family: Theme.sansFamily
                                            font.pixelSize: 13
                                            font.weight: 500
                                        }
                                        Text {
                                            visible: detailModelRow.modelData.showId === true
                                            text: detailModelRow.modelData.id || ""
                                            color: Theme.fgMuted
                                            font.family: Theme.monoFamily
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── 高级设置态：自定义请求头 ────────────────────────────────
            Item {
                id: advancedView
                x: 20
                y: 16
                width: parent.width - 40
                height: parent.height - 32
                visible: modPane.view === "advanced"

                Item {
                    id: advancedTopbar
                    width: parent.width
                    height: 30

                    Item {
                        id: advancedBack
                        anchors.verticalCenter: parent.verticalCenter
                        width: advancedBackRow.width + 16
                        height: 24

                        Rectangle {
                            anchors.fill: parent
                            radius: Theme.radiusSm
                            color: advancedBackMouse.containsMouse ? Theme.bgHover : "transparent"
                        }
                        Row {
                            id: advancedBackRow
                            x: 6
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 4
                            Icon {
                                name: IconData.chevronLeft
                                size: 16
                                color: advancedBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
                            }
                            Text {
                                text: (modPane.text.backTo || "").replace("{name}", modPane.detail.name || "")
                                color: advancedBackMouse.containsMouse ? Theme.fg : Theme.fgMuted
                                font.family: Theme.sansFamily
                                font.pixelSize: 13
                            }
                        }
                        MouseArea {
                            id: advancedBackMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: modPane.view = "detail"
                        }
                    }
                }

                Item {
                    id: advancedField
                    y: 46   // topbar 30 + 16
                    width: parent.width
                    height: advancedFieldHead.height + 8 + headerListBox.height + 8
                            + headersHint.implicitHeight

                    Item {
                        id: advancedFieldHead
                        width: parent.width
                        height: 26

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modPane.text.headers || ""
                            color: Theme.fg
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                            font.weight: 600
                        }

                        Rectangle {
                            id: addHeaderBtn
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            width: addHeaderRow.implicitWidth + 16
                            height: 26
                            radius: Theme.radiusSm
                            color: addHeaderMouse.containsMouse ? Theme.bgHover : "transparent"

                            Row {
                                id: addHeaderRow
                                anchors.centerIn: parent
                                spacing: 8
                                Icon {
                                    name: IconData.plus
                                    size: 14
                                    color: addHeaderMouse.containsMouse ? Theme.fg : Theme.fgMuted
                                }
                                Text {
                                    text: modPane.text.addHeader || ""
                                    color: addHeaderMouse.containsMouse ? Theme.fg : Theme.fgMuted
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 12
                                    font.weight: 500
                                }
                            }
                            MouseArea {
                                id: addHeaderMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: modPane.addHeader()
                            }
                        }
                    }

                    Rectangle {
                        id: headerListBox
                        y: 34   // field__row-between 26 + 下间距 8
                        width: parent.width
                        height: {
                            if (modPane.headerRows.length === 0) return 49
                            var issueExtra = 0
                            for (var i = 0; i < modPane.headerRows.length; i++) {
                                if (modPane.headerRows[i].issueText) issueExtra += 18
                            }
                            return modPane.headerRows.length * 44
                                 + Math.max(0, modPane.headerRows.length - 1) * 1
                                 + issueExtra + 2
                        }
                        radius: Theme.radius
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.border
                        clip: true

                        Text {
                            visible: modPane.headerRows.length === 0
                            x: 1
                            y: 17
                            width: parent.width - 2
                            horizontalAlignment: Text.AlignHCenter
                            text: modPane.text.noHeaders || ""
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }

                        Column {
                            x: 1
                            y: 1
                            width: parent.width - 2
                            Repeater {
                                model: modPane.headerRows
                                delegate: Item {
                                    id: headerRow
                                    required property var modelData
                                    required property int index
                                    width: headerListBox.width - 2
                                    height: 44 + (modelData.issueText ? 18 : 0)
                                            + (headerRow.index > 0 ? 1 : 0)

                                    Rectangle {
                                        visible: headerRow.index > 0
                                        anchors.top: parent.top
                                        width: parent.width
                                        height: 1
                                        color: Theme.border
                                    }

                                    Rectangle {
                                        id: headerNameBox
                                        x: 12
                                        y: 6 + (headerRow.index > 0 ? 1 : 0)
                                        width: Math.round((headerRow.width - 24) * 0.34)
                                        height: 32
                                        radius: Theme.radiusSm
                                        color: Theme.bgElevated
                                        border.width: 1
                                        border.color: headerNameInput.activeFocus ? Theme.accent : Theme.borderStrong

                                        Text {
                                            visible: headerNameInput.text.length === 0
                                            x: 12
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modPane.text.headerName || ""
                                            color: Theme.fgMuted
                                            font.family: Theme.sansFamily
                                            font.pixelSize: 13
                                            enabled: false
                                        }
                                        TextInput {
                                            id: headerNameInput
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            text: headerRow.modelData.name || ""
                                            color: Theme.fg
                                            font.family: Theme.sansFamily
                                            font.pixelSize: 13
                                            selectByMouse: true
                                            clip: true
                                            onTextEdited: modPane.editHeader(headerRow.index, "name", text)
                                        }
                                    }

                                    Rectangle {
                                        id: headerValueBox
                                        x: headerNameBox.x + headerNameBox.width + 8
                                        y: headerNameBox.y
                                        width: headerRow.width - 12 - 28 - 8 - x
                                        height: 32
                                        radius: Theme.radiusSm
                                        color: Theme.bgElevated
                                        border.width: 1
                                        border.color: headerValueInput.activeFocus ? Theme.accent : Theme.borderStrong

                                        Text {
                                            visible: headerValueInput.text.length === 0
                                            x: 12
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: modPane.text.headerValue || ""
                                            color: Theme.fgMuted
                                            font.family: Theme.sansFamily
                                            font.pixelSize: 13
                                            enabled: false
                                        }
                                        TextInput {
                                            id: headerValueInput
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            text: headerRow.modelData.value || ""
                                            color: Theme.fg
                                            font.family: Theme.sansFamily
                                            font.pixelSize: 13
                                            selectByMouse: true
                                            clip: true
                                            onTextEdited: modPane.editHeader(headerRow.index, "value", text)
                                        }
                                    }

                                    Rectangle {
                                        id: headerDelete
                                        anchors.right: parent.right
                                        anchors.rightMargin: 12
                                        y: headerNameBox.y
                                        width: 28
                                        height: 28
                                        radius: Theme.radiusSm
                                        color: headerDeleteMouse.containsMouse ? Theme.bgHover : "transparent"

                                        Icon {
                                            anchors.centerIn: parent
                                            name: IconData.trash2
                                            size: 14
                                            color: headerDeleteMouse.containsMouse ? Theme.fg : Theme.fgSubtle
                                        }
                                        MouseArea {
                                            id: headerDeleteMouse
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: modPane.removeHeader(headerRow.index)
                                        }
                                    }

                                    Text {
                                        visible: (headerRow.modelData.issueText || "") !== ""
                                        x: 12
                                        y: 40 + (headerRow.index > 0 ? 1 : 0)
                                        width: headerRow.width - 24
                                        text: headerRow.modelData.issueText || ""
                                        color: Theme.fgMuted
                                        font.family: Theme.sansFamily
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                    }

                    Text {
                        id: headersHint
                        y: headerListBox.y + headerListBox.height + 8
                        width: parent.width
                        text: modPane.text.headersHint || ""
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
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
            property var selected: null
            property string loadError: ""

            Component.onCompleted: refresh()
            Connections { target: shellBridge; function onExtensionsChanged() { extPane.refresh() } }

            function refresh() {
                try { rows = shellBridge ? (I18n.locale, shellBridge.extensionRows()) : [] }
                catch (error) { rows = [] }
                var result = JSON.parse(shellBridge.extensionAction("errors", "", "", "{}"))
                loadError = result.ok ? result.errors.join("\n") : result.error
            }

            Text {
                x: 20
                y: 18
                text: I18n.t("extensions.title")
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }

            SettingsButton {
                objectName: "extensionsManageMcp"
                anchors.right: parent.right; anchors.rightMargin: 20; y: 12
                text: I18n.t("finish.mcp")
                onClicked: root.paneRequested("mcp")
            }
            SettingsButton {
                objectName: "extensionsImportSkill"
                anchors.right: parent.right; anchors.rightMargin: 100; y: 12
                text: I18n.t("extensions.importSkill")
                onClicked: {
                    var result = JSON.parse(shellBridge.extensionAction("import-skill", "skill", "", "{}"))
                    if (result.ok) extPane.refresh()
                    else if (result.error !== "cancelled") extPane.loadError = result.error
                }
            }

            Text {
                x: 20; y: 40; width: parent.width - 40
                visible: extPane.loadError.length > 0
                text: extPane.loadError; color: Theme.danger; wrapMode: Text.Wrap
            }
            Loader {
                anchors.fill: parent; z: 10
                active: extPane.selected !== null
                sourceComponent: Component {
                    ExtensionDetail {
                        item: extPane.selected || ({})
                        Rectangle { anchors.fill: parent; color: Theme.bgPanel; z: -1 }
                        onBack: { extPane.selected = null; extPane.refresh() }
                    }
                }
            }

            // 空态：原版 `.cf-empty`（padding 20、居中、12px subtle）。
            Text {
                visible: extPane.rows.length === 0
                x: 20
                y: 55
                width: parent.width - 40
                horizontalAlignment: Text.AlignHCenter
                text: shellBridge ? (I18n.locale, shellBridge.labels()).extEmpty : ""
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }

            Text {
                visible: extPane.rows.length > 0 && extPane.rows.every(function(row) { return row.builtin })
                x: 20
                y: 70 + extColumn.height
                width: parent.width - 40
                horizontalAlignment: Text.AlignHCenter
                text: I18n.t("cf.extUserEmpty")
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 12
            }

            // 行列表：卡片自带 1px 外框，行间用 1px 分隔线（原版 .cf-rows + .cf-setrow）。
            Flickable {
                objectName: "extensionListScroll"; boundsBehavior: Flickable.StopAtBounds
                x: 20; y: extPane.loadError.length ? 100 : 55
                width: parent.width - 40; height: parent.height - y - 20
                clip: true; contentHeight: extColumn.height + 2
                ScrollBar.vertical: SettingsScrollBar { visible: size < 1 }
            Rectangle {
                visible: extPane.rows.length > 0
                width: parent.width
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
                                    color: extRow.modelData.warning ? Theme.warning : Theme.fgSubtle
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                }
                            }

                            AvatarStack {
                                anchors.right: parent.right; anchors.rightMargin: 86; anchors.verticalCenter: parent.verticalCenter
                                roles: extRow.modelData.roles || []; images: extRow.modelData.roleAvatars || ({})
                            }
                            Icon {
                                visible: !extRow.modelData.builtin
                                anchors.right: parent.right; anchors.rightMargin: 66
                                anchors.verticalCenter: parent.verticalCenter
                                name: IconData.chevronRight; size: 15; color: Theme.fgSubtle
                            }
                            MouseArea {
                                anchors.fill: parent; anchors.rightMargin: 60
                                enabled: !extRow.modelData.builtin
                                onClicked: {
                                    var result = JSON.parse(shellBridge.extensionAction("detail", extRow.modelData.kind, extRow.modelData.id, "{}"))
                                    if (result.ok) extPane.selected = result.item; else extPane.loadError = result.error
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
                                    color: Theme.switchThumb
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    enabled: !extRow.modelData.builtin
                                    onClicked: {
                                        // 无条件重读：写失败时行数据保持原样，开关不会假装翻面。
                                        var result = JSON.parse(shellBridge.extensionAction("update", extRow.modelData.kind, extRow.modelData.id, JSON.stringify({enabled: !extRow.modelData.enabled})))
                                        if (!result.ok) { extPane.loadError = result.error; return }
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
    }

    // ── About：56px 图标 + 名称 + 版本 + 检查更新 ─────────────────────────
    // 几何逐项取自原版：.cf-about padding 24px 0；.cf-about__name margin-top 12px、
    // font-size 20/weight 750；.cf-about__ver margin-top 2px、12px；.cf-update margin-top 16px、gap 8px。
    Component {
        id: aboutPane
        Item {
            id: aboutPaneRoot
            objectName: "aboutPaneRoot"
            // 文案与状态都从 Python 投影取；QML 只画。
            property var labels: shellBridge ? (I18n.locale, shellBridge.modelsPaneLabels()) : ({})
            property var updateState: ({phase: "idle"})
            property string updatePhase: "idle"
            property bool checking: updatePhase === "checking"

            function applyUpdateState(state) {
                updateState = state || {phase: "idle"}
                var phase = state ? (state["phase"] || state.phase || "idle") : "idle"
                updatePhase = "" + phase
            }

            function checkUpdates() {
                if (!shellBridge || checking)
                    return
                applyUpdateState({phase: "checking"})
                shellBridge.checkForUpdates()
            }

            Component.onCompleted: {
                if (shellBridge)
                    applyUpdateState(shellBridge.updateState())
            }

            Connections {
                target: shellBridge
                function onUpdateStateChanged(state) { aboutPaneRoot.applyUpdateState(state) }
            }

            // SettingsPane.tsx::AboutPane 先绘制 cf-pane__title，再绘制居中的品牌区。
            Text {
                objectName: "aboutPaneHeading"
                x: 20
                // CSS h2 的 22.5px 行盒比 Qt 字形盒多出的 leading，实测基线需补 2px。
                y: 18
                text: I18n.t("settings.about")
                color: Theme.fg
                font.family: Theme.sansFamily
                font.pixelSize: 15
                font.weight: 700
            }

            Column {
                id: aboutColumn
                width: parent.width
                y: 63
                spacing: 0

                Image {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 56
                    height: 56
                    source: "assets/deva-icon.svg"
                    smooth: true
                }
                // .cf-about__name { margin-top: 12px }；Text 的隐式盒比字形高，留 15px 对齐实测。
                Item { width: parent.width; height: 15 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: I18n.t("finish.brand")
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 20
                    font.weight: 750
                }
                // .cf-about__ver { margin-top: 2px }
                Item { width: parent.width; height: 6 }
                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: (labels.version || I18n.t("settings.version")) + " " + root.appVersion
                    color: Theme.fgMuted
                    font.family: Theme.sansFamily
                    font.pixelSize: 12
                }
                // .cf-update { margin-top: var(--space-4); gap: var(--space-2) }
                Item { width: parent.width; height: 19 }

                Column {
                    id: updateSection
                    width: parent.width
                    spacing: Theme.space2

                    Rectangle {
                        id: updateButton
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: updateButtonRow.implicitWidth + Theme.space2 * 2 + 2
                        height: 26
                        radius: Theme.radiusSm
                        color: updateMouse.containsMouse && !aboutPaneRoot.checking
                               ? Theme.bgHover : Theme.bgElevated
                        border.width: 1
                        border.color: Theme.borderStrong
                        opacity: 1

                        Row {
                            id: updateButtonRow
                            anchors.centerIn: parent
                            spacing: Theme.space2
                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                name: IconData.refreshCw
                                size: 13
                                color: Theme.fg
                                visible: !aboutPaneRoot.checking
                            }
                            Icon {
                                anchors.verticalCenter: parent.verticalCenter
                                name: IconData.refreshCw
                                size: 13
                                color: Theme.fg
                                visible: aboutPaneRoot.checking
                                RotationAnimator on rotation {
                                    from: 0
                                    to: 360
                                    duration: 800
                                    loops: Animation.Infinite
                                    running: aboutPaneRoot.checking
                                }
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: aboutPaneRoot.checking
                                      ? (aboutPaneRoot.labels.checkingUpdates || I18n.t("settings.update.checking"))
                                      : (aboutPaneRoot.labels.checkForUpdates || I18n.t("settings.update.check"))
                                color: Theme.fg
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                font.weight: 500
                            }
                        }
                        MouseArea {
                            id: updateMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: !aboutPaneRoot.checking
                            cursorShape: aboutPaneRoot.checking ? Qt.ForbiddenCursor : Qt.PointingHandCursor
                            onClicked: aboutPaneRoot.checkUpdates()
                        }
                    }

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 8
                        visible: aboutPaneRoot.updatePhase === "available"
                        SettingsButton { objectName: "updateDownload"; height: 26; text: "下载安装包"; onClicked: shellBridge.downloadUpdate("") }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        visible: aboutPaneRoot.updatePhase === "downloading"
                        text: "下载中 " + String(aboutPaneRoot.updateState.percent || 0) + "%"
                        color: Theme.fgMuted; font.pixelSize: 12
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 8
                        visible: aboutPaneRoot.updatePhase === "downloaded"
                        SettingsButton { objectName: "updateInstall"; height: 26; text: "打开安装包"; onClicked: shellBridge.installUpdate("") }
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 6
                        visible: aboutPaneRoot.updatePhase === "latest"
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: IconData.check
                            size: 13
                            color: Theme.success
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: aboutPaneRoot.labels.latestVersion || ""
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }
                    }
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 6
                        visible: aboutPaneRoot.updatePhase === "error"
                        Icon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: IconData.alertTriangle
                            size: 13
                            color: Theme.danger
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: aboutPaneRoot.labels.updateCheckFailed || ""
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
    }

    // ── 删除服务商确认：沿用 `out/qml-shell/dom` 实测的 Modal 卡片规格
    //    （420×186、radius 12、背板 rgba(0,0,0,.42)、Cancel 70 / Delete 69、按钮 30px）──
    Item {
        id: providerDeleteLayer
        objectName: "providerDeleteLayer"
        anchors.fill: parent
        visible: root.providerDeleteOpen
        z: 40

        Rectangle {
            anchors.fill: parent
            color: Theme.backdrop
            MouseArea {
                anchors.fill: parent
                onClicked: root.providerDeleteOpen = false
            }
        }

        Rectangle {
            id: providerDeleteCard
            objectName: "providerDeleteCard"
            anchors.centerIn: parent
            width: 420
            height: 186
            radius: Theme.radiusLg
            color: Theme.bgElevated
            border.width: 1
            border.color: Theme.border

            MouseArea { anchors.fill: parent; onClicked: {} }

            Text {
                x: 20
                y: 20
                width: parent.width - 40
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                text: root.providerDeleteName
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
                text: root.modelsLabels.deleteProviderConfirm || ""
                color: Theme.fgMuted
                font.family: Theme.sansFamily
                font.pixelSize: 13
            }

            Rectangle {
                id: providerDeleteCancel
                objectName: "providerDeleteCancel"
                x: 253
                y: 136
                width: 70
                height: 30
                radius: Theme.radiusSm
                color: providerCancelMouse.containsMouse ? Theme.bgHover : "transparent"
                Text {
                    anchors.centerIn: parent
                    text: root.modelsLabels.cancel || ""
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: providerCancelMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.providerDeleteOpen = false
                }
            }

            Rectangle {
                id: providerDeleteConfirm
                objectName: "providerDeleteConfirm"
                x: 330
                y: 135
                width: 69
                height: 30
                radius: Theme.radiusSm
                color: providerConfirmMouse.containsMouse ? Theme.bgHover : Theme.bgElevated
                border.color: Theme.danger
                border.width: 2
                Text {
                    anchors.centerIn: parent
                    text: root.modelsLabels.delete || ""
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.weight: 500
                }
                MouseArea {
                    id: providerConfirmMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        // 确认删除要落到 Models 面板（它持有 selectedId 与删除后的回列表）。
                        if (modelsLoader.item) modelsLoader.item.confirmDelete()
                        else root.providerDeleteOpen = false
                    }
                }
            }
        }
    }

}
