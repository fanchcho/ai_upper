// 三栏壳：左固定宽侧栏 / 中会话列表 / 右正文区。
//
// 只做壳与正文承载，不做逐页还原：侧栏是导航按钮列，中列是 ListView + delegate，
// 右列是 QML 的 TextEdit，文档由 Python 侧 markdown 渲染器写入（见 qml_shell.py 的
// ShellBridge）——那是正文层唯一真相源，QML 里不重复解析 Markdown，也不再给
// TextEdit 绑 text 属性（那会把渲染好的文档覆盖成源文）。
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

    // 由 Python 在创建引擎后注入：
    // sessions = [{title, preview}]，activeIndex 指定选中项。
    property var sessions: []
    property string activeTitle: ""
    property int activeIndex: 0

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
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: window.sessions
                    currentIndex: window.activeIndex
                    spacing: 2

                    delegate: Rectangle {
                        required property int index
                        required property var modelData
                        width: ListView.view.width - Theme.space2 * 2
                        x: Theme.space2
                        height: 56
                        radius: Theme.radius
                        color: index === sessionList.currentIndex ? Theme.bgSelected : "transparent"

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Theme.space3
                            anchors.right: parent.right
                            anchors.rightMargin: Theme.space3
                            spacing: 2

                            Text {
                                text: parent.parent.modelData.title || ""
                                color: Theme.fg
                                font.family: Theme.sansFamily
                                font.pixelSize: 13
                                font.bold: true
                                elide: Text.ElideRight
                                width: parent.width
                            }
                            Text {
                                text: parent.parent.modelData.preview || ""
                                color: Theme.fgSubtle
                                font.family: Theme.sansFamily
                                font.pixelSize: 12
                                elide: Text.ElideRight
                                width: parent.width
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: window.activate(index)
                        }
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

        // ── 右：正文区 ────────────────────────────────────────────────
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
                        text: window.activeTitle
                        color: Theme.fg
                        font.family: Theme.sansFamily
                        font.pixelSize: 13
                        font.bold: true
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.border
                    }
                }

                TextEdit {
                    id: bodyView
                    objectName: "bodyView"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.leftMargin: Theme.space5
                    Layout.rightMargin: Theme.space5
                    Layout.topMargin: Theme.space5
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.Wrap
                    font.family: Theme.sansFamily
                    font.pixelSize: Theme.bodyPx
                    color: Theme.fg
                    // 文档内容由 Python 写入（QQuickTextDocument）；这里只负责把对象交出去。
                    Component.onCompleted: bodyBridge.attach(textDocument)
                }
            }
        }
    }

    function activate(index) {
        if (index < 0 || index >= window.sessions.length)
            return
        window.activeIndex = index
        window.activeTitle = window.sessions[index].title || ""
        // 取 TextEdit 自己的文档对象交给 Python：渲染是「重绘进这份文档」，不换实例。
        bodyBridge.render(bodyView.textDocument, window.sessions[index].body || "")
    }
}
