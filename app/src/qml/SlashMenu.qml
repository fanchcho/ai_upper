// 输入框 `/` 指令联想（原版 Composer.tsx:382-420）。
import QtQuick
import "."

Rectangle {
    id: menu
    objectName: "slashMenu"
    property var rows: []
    property int current: 0
    signal picked(string name)
    width: 320
    height: rows.length === 0 ? 0 : 34 + rows.length * 34 + 8
    visible: rows.length > 0
    radius: Theme.radiusLg
    color: Theme.bgElevated
    border.width: 1
    border.color: Theme.border
    Column {
        x: 8; y: 6; width: parent.width - 16
        Text {
            height: 22; text: I18n.t("cf.slash.title"); color: Theme.fgMuted
            font.family: Theme.sansFamily; font.pixelSize: 11
        }
        Repeater {
            model: menu.rows
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: parent.width; height: 34; radius: Theme.radius
                color: index === menu.current ? Theme.bgActive : "transparent"
                Text {
                    x: 8; anchors.verticalCenter: parent.verticalCenter
                    text: "/" + modelData.name
                    color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13; font.weight: 600
                }
                Text {
                    x: 92; width: parent.width - 100; anchors.verticalCenter: parent.verticalCenter
                    text: modelData.desc; color: Theme.fgMuted; elide: Text.ElideRight
                    font.family: Theme.sansFamily; font.pixelSize: 11
                }
                MouseArea { anchors.fill: parent; onClicked: menu.picked(modelData.name) }
            }
        }
    }
}
