import QtQuick
import QtQuick.Controls.Basic
import "."

Button {
    id: control
    property bool primary: false
    property bool destructive: false
    font.family: Theme.sansFamily
    font.pixelSize: 13
    padding: 8
    contentItem: Text {
        text: control.text
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !control.enabled ? Theme.fgMuted : control.primary ? Theme.accentFg : Theme.fg
    }
    background: Rectangle {
        implicitWidth: 70
        implicitHeight: 34
        radius: Theme.radiusSm
        color: !control.enabled ? Theme.bgInset : control.primary ? (control.down || control.hovered ? Theme.accentHover : Theme.accent) : control.down ? Theme.bgActive : control.hovered ? Theme.bgHover : Theme.bgElevated
        border.color: control.destructive ? Theme.danger : control.activeFocus ? Theme.accent : Theme.borderStrong
        border.width: control.destructive ? 2 : 1
    }
}
