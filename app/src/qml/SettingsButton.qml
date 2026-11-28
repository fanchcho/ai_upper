import QtQuick
import QtQuick.Controls.Basic
import "."

Button {
    id: control
    property bool primary: false
    property bool destructive: false
    property bool ghost: false
    opacity: enabled ? 1 : 0.45
    font.family: Theme.sansFamily
    font.pixelSize: 13
    padding: 8
    contentItem: Text {
        text: control.text
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: control.destructive ? "#ffffff" : control.primary ? Theme.accentFg : Theme.fg
    }
    background: Rectangle {
        implicitWidth: 70
        implicitHeight: 34
        radius: Theme.radiusSm
        color: control.destructive ? Theme.danger : control.primary ? (control.enabled && (control.down || control.hovered) ? Theme.accentHover : Theme.accent) : control.enabled && control.down ? Theme.bgActive : control.enabled && control.hovered ? Theme.bgHover : control.ghost ? "transparent" : Theme.bgElevated
        border.color: control.destructive ? Theme.danger : control.primary || control.activeFocus ? Theme.accent : control.ghost ? "transparent" : Theme.borderStrong
        border.width: 1
    }
}
