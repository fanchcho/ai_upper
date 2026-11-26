import QtQuick
import QtQuick.Controls.Basic
import "."

CheckBox {
    id: control
    spacing: 8
    padding: 0
    indicator: Rectangle {
        x: 0
        y: (control.height - height) / 2
        implicitWidth: 18
        implicitHeight: 18
        radius: 4
        color: control.checked ? Theme.accent : Theme.bg
        border.color: control.activeFocus ? Theme.accent : Theme.borderStrong
        Text { anchors.centerIn: parent; text: "✓"; visible: control.checked; color: Theme.accentFg; font.pixelSize: 14 }
    }
    contentItem: Text {
        text: control.text
        leftPadding: control.indicator.width + control.spacing
        verticalAlignment: Text.AlignVCenter
        color: control.enabled ? Theme.fg : Theme.fgMuted
        font.family: Theme.sansFamily
        font.pixelSize: 13
    }
}
