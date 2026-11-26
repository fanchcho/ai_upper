import QtQuick
import QtQuick.Controls.Basic
import "."

ScrollBar {
    id: control
    contentItem: Rectangle {
        implicitWidth: Theme.scrollbarWidth
        implicitHeight: Theme.scrollbarWidth
        radius: Theme.radiusSm
        color: control.hovered || control.pressed ? Theme.scrollbarHover : Theme.scrollbar
    }
    background: Item {}
}
