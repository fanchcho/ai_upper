// 三栏壳：左固定宽侧栏 / 中会话列表 / 右正文区 + 输入区。
//
// 只做壳与正文承载，不做逐页还原：侧栏是导航按钮列，中列是 ListView + delegate，
// 右列是 QML 的 TextEdit，文档由 Python 侧 markdown 渲染器写入（见 qml_shell.py 的
// ShellBridge）——那是正文层唯一真相源，QML 里不重复解析 Markdown，也不再给
// TextEdit 绑 text 属性（那会把渲染好的文档覆盖成源文）。
//
// 数据同样来自 Python：sessions 是真实会话列表（qml_shell_sessions.session_rows），
// 选中会话由 shellBridge.openSession(id) 让 Python 按落盘消息重渲染正文；输入区发送
// 走 shellBridge.send(text)，助理回复的流式增量由 Python 重渲染进正文。
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

ApplicationWindow {
    id: window
    visible: true
    width: 1280
    height: 820
    minimumWidth: 940
    minimumHeight: 600
    title: "ai_upper · QML 壳"
    color: Theme.bg

    // 由 Python 注入：sessions = [{id,title,preview,time}]，activeId 是选中会话的 id。
    property var sessions: []
    property string activeId: ""
    property string activeTitle: ""
    property bool busy: false
    property string status: "就绪"

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── 左：固定宽侧栏 ────────────────────────────────────────────
        Rectangle {
            Layout.preferredWidth: Theme.sidebarWidth
            Layout.fillHeight: true
            color: Theme.bgPanel

            Column {
                id: sidebar
                anchors.fill: parent
                anchors.margins: Theme.space3
                spacing: Theme.space1 + 2

                Text {
                    text: "ai_upper"
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 15
                    font.bold: true
                    bottomPadding: Theme.space3
                }

                Repeater {
                    model: ["新建会话", "搜索", "设置"]
                    delegate: Rectangle {
                        required property string modelData
                        width: sidebar.width
                        height: 34
                        radius: Theme.radius
                        color: navMouse.containsMouse ? Theme.bgInset : "transparent"

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.space3
                            text: parent.modelData
                            color: Theme.fgMuted
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                        }
                        MouseArea {
                            id: navMouse
                            anchors.fill: parent
                            hoverEnabled: true
                        }
                    }
                }

                Text {
                    y: sidebar.height - height
                    text: "QML 壳 · 预览"
                    color: Theme.fgSubtle
                    font.family: Theme.sansFamily
                    font.pixelSize: 11
                }
            }

            Rectangle { // 右缘 1px 分隔线
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: Theme.border
            }
        }

        // ── 中：会话列表 ──────────────────────────────────────────────
        Rectangle {
            Layout.preferredWidth: 300
            Layout.fillHeight: true
            color: Theme.bg

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Text {
                    text: "会话"
                    color: Theme.fg
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                    font.bold: true
                    Layout.margins: Theme.space3
                }

                ListView {
                    id: sessionList
                    objectName: "sessionList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: window.sessions
                    spacing: 2
                    visible: window.sessions.length > 0

                    delegate: Rectangle {
                        required property int index
                        required property var modelData
                        width: ListView.view.width - Theme.space2 * 2
                        x: Theme.space2
                        height: 62
                        radius: Theme.radius
                        color: modelData.id === window.activeId ? Theme.bgSelected : "transparent"

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.space3
                            anchors.right: parent.right
                            anchors.rightMargin: Theme.space3
                            spacing: 3

                            RowLayout {
                                width: parent.width
                                spacing: Theme.space2

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.title || ""
                                    color: Theme.fg
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 13
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: modelData.time || ""
                                    color: Theme.fgSubtle
                                    font.family: Theme.sansFamily
                                    font.pixelSize: 11
                                }
                            }
                            Text {
                                text: modelData.preview || ""
                                color: Theme.fgSubtle
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                width: parent.width
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: window.activate(modelData.id)
                        }
                    }
                }

                // 空状态：没有会话时列表区的真实渲染（不是拿假数据顶替）。
                Column {
                    visible: window.sessions.length === 0
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: Theme.space2

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "还没有会话"
                        color: Theme.fgMuted
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "发一条消息就会出现在这里"
                        color: Theme.fgSubtle
                        font.family: Theme.sansFamily
                        font.pixelSize: 12
                    }
                }
            }

            Rectangle { // 右缘 1px 分隔线
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: Theme.border
            }
        }

        // ── 右：正文区 + 输入区 ───────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.bg

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Theme.titlebarHeight + Theme.space2
                    color: Theme.bg

                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: Theme.space5
                        anchors.verticalCenter: parent.verticalCenter
                        text: window.activeTitle !== "" ? window.activeTitle : "未选择会话"
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: Theme.space5
                        anchors.verticalCenter: parent.verticalCenter
                        text: window.status
                        color: Theme.fgSubtle
                        font.family: Theme.sansFamily
                        font.pixelSize: 11
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.border
                    }
                }

                Text {
                    id: bodyEmpty
                    visible: window.activeId === ""
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: window.sessions.length === 0
                          ? "这里还没有任何对话。\n在下面输入一条消息试试。"
                          : "从左侧选择一个会话，正文会显示在这里。"
                    color: Theme.fgSubtle
                    font.family: Theme.sansFamily
                    font.pixelSize: 13
                }

                // TextEdit 放在 Flickable 里：正文要能滚，且流式追加时自动贴到底部。
                Flickable {
                    id: bodyScroll
                    objectName: "bodyScroll"
                    visible: window.activeId !== ""
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.leftMargin: Theme.space5
                    Layout.rightMargin: Theme.space5
                    Layout.topMargin: Theme.space5
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    contentWidth: width
                    contentHeight: bodyView.implicitHeight
                    TextEdit {
                        id: bodyView
                        objectName: "bodyView"
                        width: bodyScroll.width
                        readOnly: true
                        selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        font.family: Theme.sansFamily
                        font.pixelSize: Theme.bodyPx
                        color: Theme.fg
                        // 文档内容由 Python 写入（QQuickTextDocument）；这里只负责把对象交出去。
                        Component.onCompleted: shellBridge.attach(textDocument)
                    }
                }

                // ── 输入区 ────────────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 108
                    color: Theme.bg

                    Rectangle { // 上缘分隔线
                        anchors.top: parent.top
                        width: parent.width
                        height: 1
                        color: Theme.border
                    }

                    Rectangle {
                        id: inputBox
                        anchors.fill: parent
                        anchors.margins: Theme.space4
                        anchors.rightMargin: Theme.space5
                        anchors.leftMargin: Theme.space5
                        radius: Theme.radius
                        color: Theme.bgPanel
                        border.width: 1
                        border.color: inputField.activeFocus ? Theme.accent : Theme.borderStrong

                        TextArea {
                            id: inputField
                            objectName: "inputField"
                            anchors.fill: parent
                            anchors.margins: Theme.space2
                            anchors.rightMargin: 84
                            placeholderText: "输入消息，Enter 发送，Shift+Enter 换行"
                            placeholderTextColor: Theme.fgSubtle
                            color: Theme.fg
                            font.family: Theme.sansFamily
                            font.pixelSize: 13
                            wrapMode: TextArea.Wrap
                            background: null
                            enabled: !window.busy
                            Keys.onPressed: function (event) {
                                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                    if (event.modifiers & Qt.ShiftModifier) {
                                        event.accepted = false; // 换行交给 TextArea 自己处理
                                    } else {
                                        window.submit();
                                        event.accepted = true;
                                    }
                                }
                            }
                        }

                        Rectangle {
                            id: sendButton
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: Theme.space2
                            width: 64
                            height: 28
                            radius: Theme.radius
                            enabled: !window.busy && inputField.text.trim() !== ""
                            color: !enabled ? Theme.bgInset
                                 : sendMouse.containsMouse ? Theme.accent : Theme.bgSelected

                            Text {
                                anchors.centerIn: parent
                                text: window.busy ? "输出中" : "发送"
                                color: sendButton.enabled ? Theme.fg : Theme.fgSubtle
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                font.bold: true
                            }
                            MouseArea {
                                id: sendMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                enabled: sendButton.enabled
                                onClicked: window.submit()
                            }
                        }
                    }
                }
            }
        }
    }

    function activate(id) {
        if (!id || id === window.activeId)
            return
        shellBridge.openSession(id)
    }

    function submit() {
        var text = inputField.text;
        if (window.busy || text.trim() === "")
            return
        if (shellBridge.send(text)) {
            inputField.text = "";
        }
    }
}
