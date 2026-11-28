"""QR PNG data URI without an external executable (MIT Nayuki encoder)."""
import base64
import struct
import zlib
from vendor.qrcodegen import QrCode


def qr_image(text):
    qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    scale, border = 4, 4
    size = (qr.get_size() + border * 2) * scale
    raw = b''.join(b'\0' + bytes(0 if qr.get_module(x // scale - border, y // scale - border) else 255
                                for x in range(size)) for y in range(size))
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 0, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode()
