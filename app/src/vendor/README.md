# QR encoder

`qrcodegen.py` is the MIT-licensed Python implementation from
https://github.com/nayuki/QR-Code-generator/blob/master/python/qrcodegen.py
retrieved 2026-11-28. Its copyright and MIT license are retained in the file.
Upstream SHA-256: d09f22750a8d5adfb1643e64c5cd7071b8f02c1d04858f814ca9a7cc6f1f0b23.

Used to render real QR codes without Node or an additional runtime dependency.

Local compatibility change: `_BitBuffer` inherits `typing.List[int]` instead of
`list[int]`, whose base-class expression is evaluated during import and fails
on Python 3.8. The existing Python 3.8 guard caught this; no test was changed.
