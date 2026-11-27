// F79：本地 PTY 等价终端（deva terminal.ts 的用户入口）。
import QtQuick
import QtQuick.Controls
import "."

Popup {
    id: root
    objectName: "terminalPanel"
    property string buffer: ""
    width: 720; height: 480; padding: 10
    modal: false
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgPanel; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: { if (shellBridge) shellBridge.startTerminal() }
    onClosed: if (shellBridge) shellBridge.stopTerminal()
    Connections {
        target: shellBridge
        function onTerminalOutput(text) { root.buffer += text; output.cursorPosition = output.length }
        function onTerminalFinished(code) { root.buffer += "\n[exit " + code + "]\n" }
    }
    Column {
        width: parent.width; spacing: 6
        Row {
            width: parent.width
            Text { text: "终端"; color: Theme.fg; font.pixelSize: 16; font.weight: 700; width: parent.width - 80 }
            SettingsButton { objectName: "terminalClose"; text: "关闭"; onClicked: root.close() }
        }
        TextArea {
            id: output; objectName: "terminalOutput"; width: parent.width; height: 360
            readOnly: true; text: root.buffer; color: Theme.fg; font.family: "monospace"; font.pixelSize: 12
            wrapMode: TextArea.Wrap; background: Rectangle { color: Theme.bgInset; radius: Theme.radiusSm }
        }
        TextField {
            id: input; objectName: "terminalInput"; width: parent.width
            placeholderText: "输入命令后回车"; color: Theme.fg; font.family: "monospace"
            onAccepted: { if (shellBridge.terminalInput(text)) { text = ""; input.forceActiveFocus() } }
        }
    }
}
