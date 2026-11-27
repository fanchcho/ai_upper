// F76 本机用户资料：头像查看/选择/清除（原版 profile.ts 目前只有头像）。
import QtQuick
import QtQuick.Controls
import "."

Popup {
    id: root
    objectName: "profilePanel"
    property var profile: ({image: ""})
    width: 360; height: 330; padding: 16
    modal: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle { color: Theme.bgElevated; border.color: Theme.border; radius: Theme.radiusLg }
    onOpened: refresh()
    function refresh() { if (shellBridge) profile = shellBridge.userProfile() }
    function choose() {
        var image = shellBridge.userPickAvatar()
        if (image.length > 0) { profile = {image: image}; root.notice = "" }
    }
    function clear() { if (shellBridge.userClearAvatar()) { profile = {image: ""}; root.notice = "" } }
    property string notice: ""
    Column {
        width: parent.width; spacing: 12
        Text { text: "个人资料"; color: Theme.fg; font.pixelSize: 18; font.weight: 700; width: parent.width }
        Avatar { objectName: "profileAvatar"; anchors.horizontalCenter: parent.horizontalCenter; persona: "user"; size: 96; imageSource: root.profile.image || "" }
        Text { text: "本机用户"; color: Theme.fgMuted; font.pixelSize: 12; anchors.horizontalCenter: parent.horizontalCenter }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter; spacing: 8
            SettingsButton { objectName: "profileChoose"; text: "选择头像"; onClicked: root.choose() }
            SettingsButton { objectName: "profileClear"; text: "清除头像"; onClicked: root.clear() }
            SettingsButton { objectName: "profileClose"; text: "关闭"; onClicked: root.close() }
        }
        Text { objectName: "profileNotice"; text: root.notice; color: Theme.danger; font.pixelSize: 12; visible: text.length > 0 }
    }
}
