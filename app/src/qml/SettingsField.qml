import QtQuick
import QtQuick.Controls.Basic
import "."

TextField {
    color: Theme.fg
    placeholderTextColor: Theme.fgMuted
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentFg
    font.family: Theme.sansFamily
    font.pixelSize: 13
    padding: 8
    background: Rectangle {
        implicitHeight: 34
        radius: Theme.radiusSm
        color: Theme.bgElevated
        border.color: parent.activeFocus ? Theme.accent : Theme.borderStrong
    }
}
