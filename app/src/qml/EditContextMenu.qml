// 编辑区右键菜单：对应 deva 主进程 `index.ts:183-217` 的原生编辑菜单。
// 可编辑处：剪切/复制/粘贴/全选（按选区与剪贴板可用性灰显）；不可编辑但有选区：复制/全选。
import QtQuick
import QtQuick.Controls
import "."

Menu {
    id: root
    objectName: "editContextMenu"
    property var target: null
    property bool editable: false
    signal quoteRequested(string text)
    signal deleteTurnRequested()
    signal chooseDeleteRequested()
    signal chooseRewindRequested()
    width: 148
    padding: 6
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: Theme.bgElevated
        border.width: 1
        border.color: Theme.border
        radius: Theme.radiusLg
    }

    MenuItem {
        id: cutItem
        objectName: "editMenuCut"
        text: I18n.t("common.cut")
        visible: root.editable
        enabled: root.target && root.target.selectedText.length > 0
        height: 29
        contentItem: Text {
            text: cutItem.text
            color: cutItem.enabled ? Theme.fg : Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 13
            leftPadding: 9
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { radius: Theme.radius; color: cutItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: if (root.target) root.target.cut()
    }
    MenuItem {
        id: copyItem
        objectName: "editMenuCopy"
        text: I18n.t("common.copy")
        enabled: root.target && root.target.selectedText.length > 0
        height: 29
        contentItem: Text {
            text: copyItem.text
            color: copyItem.enabled ? Theme.fg : Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 13
            leftPadding: 9
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { radius: Theme.radius; color: copyItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: if (root.target) root.target.copy()
    }
    MenuItem {
        id: pasteItem
        objectName: "editMenuPaste"
        text: I18n.t("common.paste")
        visible: root.editable
        enabled: root.target !== null
        height: 29
        contentItem: Text {
            text: pasteItem.text
            color: pasteItem.enabled ? Theme.fg : Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 13
            leftPadding: 9
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { radius: Theme.radius; color: pasteItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: if (root.target) root.target.paste()
    }
    MenuItem {
        id: quoteItem
        objectName: "editMenuQuote"
        text: "引用选中"
        enabled: root.target && root.target.selectedText.length > 0
        height: 29
        contentItem: Text { text: quoteItem.text; color: quoteItem.enabled ? Theme.fg : Theme.fgSubtle; font.family: Theme.sansFamily; font.pixelSize: 13; leftPadding: 9; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: Theme.radius; color: quoteItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: if (root.target) root.quoteRequested(root.target.selectedText)
    }
    MenuSeparator { height: 9; contentItem: Rectangle { color: Theme.border; implicitHeight: 1 } }
    MenuItem {
        objectName: "editMenuChooseDelete"
        text: "选择删除轮次"
        height: 29
        contentItem: Text { text: "选择删除轮次"; color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13; leftPadding: 9; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: Theme.radius; color: parent.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: root.chooseDeleteRequested()
    }
    MenuItem {
        objectName: "editMenuRewind"
        text: "回滚本轮"
        height: 29
        contentItem: Text { text: "回滚本轮"; color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13; leftPadding: 9; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: Theme.radius; color: parent.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: root.chooseRewindRequested()
    }
    MenuItem {
        id: deleteTurnItem
        objectName: "editMenuDeleteTurn"
        text: "删除最后一轮"
        height: 29
        contentItem: Text { text: deleteTurnItem.text; color: Theme.fg; font.family: Theme.sansFamily; font.pixelSize: 13; leftPadding: 9; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: Theme.radius; color: deleteTurnItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: root.deleteTurnRequested()
    }
    MenuSeparator {
        visible: root.editable
        height: visible ? 9 : 0
        contentItem: Rectangle { color: Theme.border; implicitHeight: 1 }
    }
    MenuItem {
        id: selectAllItem
        objectName: "editMenuSelectAll"
        text: I18n.t("cf.selectAll")
        enabled: root.target !== null
        height: 29
        contentItem: Text {
            text: selectAllItem.text
            color: selectAllItem.enabled ? Theme.fg : Theme.fgSubtle
            font.family: Theme.sansFamily
            font.pixelSize: 13
            leftPadding: 9
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { radius: Theme.radius; color: selectAllItem.highlighted ? Theme.bgHover : "transparent" }
        onTriggered: if (root.target) root.target.selectAll()
    }
}
