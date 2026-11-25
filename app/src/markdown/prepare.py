"""Build rich text privately; return value objects, never a worker QObject."""
from utils.qt_compat import QtGui
from .document import render_markdown, render_plain_text
from .body import _image_names


def prepare_document(source, plain, style, width, resolver):
    document = QtGui.QTextDocument()
    if plain:
        render_plain_text(document, source, style, width)
    else:
        render_markdown(document, source, style, width, resolver)
    kind = QtGui.QTextDocument.ResourceType.ImageResource.value
    images = [(url, document.resource(kind, url)) for url in _image_names(document)]
    return QtGui.QTextDocumentFragment(document), images
