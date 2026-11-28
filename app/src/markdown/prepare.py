"""Build rich text privately and transfer ownership to the GUI thread."""
from utils.qt_compat import QtCore, QtGui
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
    # QTextDocumentFragment contains an implicitly shared private QTextDocument.
    # Constructing it here and inserting it on the GUI thread lazily creates
    # layouts/timers with the wrong affinity. Transfer the source document first;
    # the GUI creates and destroys the fragment in its own thread.
    document.moveToThread(QtCore.QCoreApplication.instance().thread())
    return document, images
