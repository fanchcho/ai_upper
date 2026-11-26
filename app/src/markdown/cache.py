"""GUI-owned display snapshots. No QTextDocument crosses a thread boundary."""
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256


@dataclass
class Display:
    body: object
    target: object

    def visible(self, value):
        for item in self.body._grids + self.body._viewports:
            item.setVisible(value)

    def release(self):
        for item in self.body._grids + self.body._viewports:
            item.setParentItem(None)
            item.deleteLater()
        self.body._grids = []
        self.body._viewports = []
        if self.body.highlighter is not None:
            self.body.highlighter.setDocument(None)
        # setTextDocument retains caller ownership. Explicitly delete evicted
        # documents: Python/Qt signal ownership can outlive the LRU entry.
        self.target.deleteLater()
        self.body.document.deleteLater()

    @property
    def charge(self):
        # Qt exposes no allocated-byte count. Budget deliberately includes a
        # generous allowance for per-character layout and per-block/format data;
        # it is an estimate, NOT a hard bound on Qt/process resident memory.
        return (self.target.characterCount() * 512
                + self.target.blockCount() * 2048
                + len(self.target.allFormats()) * 1024)


class DisplayCache:
    def __init__(self, max_entries=32, max_bytes=128 * 1024 * 1024):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.entries = OrderedDict()
        self.current = None
        self.bytes = 0
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(session_id, source, plain, style, width):
        return session_id, sha256(source.encode('utf-8')).digest(), plain, style, width

    def get(self, key):
        entry = self.entries.pop(key, None)
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        self.entries[key] = entry
        return entry[0]

    def activate(self, display, quick_document):
        previous = self.current
        if previous is not None:
            previous.visible(False)
        quick_document.setTextDocument(display.target)
        self.current = display
        # A normal session open rebuilt horizontal code viewports at x=0.
        for viewport in display.body._viewports:
            if viewport.contentX:
                viewport._content_x = 0.0
                viewport.contentXChanged.emit()
                viewport.update()
        display.visible(True)
        if previous is not None and not any(v[0] is previous for v in self.entries.values()):
            previous.release()

    def put(self, key, display):
        # Drop obsolete content/style/width snapshots of this session.
        for old in list(self.entries):
            if old[0] == key[0]:
                self._remove(old)
        charge = display.charge
        if charge > self.max_bytes:
            return  # Oversized active body works normally but is never cached.
        while self.entries and (len(self.entries) >= self.max_entries
                                or self.bytes + charge > self.max_bytes):
            self._remove(next(iter(self.entries)))
        self.entries[key] = display, charge
        self.bytes += charge

    def _remove(self, key):
        display, charge = self.entries.pop(key)
        self.bytes -= charge
        if display is not self.current:
            display.release()

    def invalidate_current(self):
        # Synchronous streaming/edit/theme rendering mutates the active body.
        for key, (display, _) in list(self.entries.items()):
            if display is self.current:
                self._remove(key)
