
import QtQuick
Item {
  width: 800; height: 900
  Flickable {
    id: scroll
    objectName: "scroll"
    x: 0; y: 0; width: 800; height: 900
    contentWidth: te.width
    contentHeight: te.contentHeight
    flickableDirection: Flickable.VerticalFlick
    TextEdit {
      id: te
      objectName: "te"
      width: 696
      readOnly: true
      selectByMouse: true
      textFormat: TextEdit.RichText
      wrapMode: TextEdit.Wrap
    }
  }
  function bodyItem() { return te }
}
