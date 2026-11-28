"""Download only recorded deliverables; never accept a client supplied path."""
import base64
import mimetypes
from pathlib import Path
from mvvm.services.deliverables import delivered_path
from mvvm.services.office_text import office_text

TEXT = set(('.md .markdown .txt .log .csv .tsv .json .jsonc .yaml .yml .toml .ini .xml .html .htm .css .js .jsx .ts .tsx .mjs .cjs .py .go .rs .java .kt .c .h .cpp .cs .php .rb .swift .sh .ps1 .bat .sql .vue .svelte .lua .dart .r .env').split())


def send_file(session, frame, send):
    rid = frame.get('rid')
    if not isinstance(rid, str): return
    def fail(message): send({'t': 'file', 'rid': rid, 'ok': False, 'message': message})
    raw = delivered_path(session, frame.get('tool'), frame.get('index'))
    if not raw: return fail('找不到这个文件，可能对话已被修改。')
    path = Path(raw)
    try:
        size = path.stat().st_size
        head = {'t': 'file', 'rid': rid, 'ok': True, 'name': path.name, 'size': size}
        ext = path.suffix.lower()
        text = None
        if ext in TEXT:
            with path.open('rb') as file: text = file.read(1200000).decode('utf-8', errors='replace')
        elif size > 30 * 1024 * 1024:
            return fail('文件超过 30 MB，请在电脑上打开。')
        elif ext in ('.docx', '.xlsx', '.pptx'):
            text = office_text(path.read_bytes(), ext)
        if text is not None:
            send(dict(head, kind='markdown' if ext in ('.md', '.markdown') else 'text', text=text[:400000], truncated=len(text)>400000 or size>1200000));return
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        chunks = max(1, (size+192*1024-1)//(192*1024))
        send(dict(head, kind='image' if mime.startswith('image/') else 'binary', mime=mime, chunks=chunks))
        with path.open('rb') as file:
            for seq in range(chunks):
                send({'t': 'file_chunk', 'rid': rid, 'seq': seq, 'data': base64.urlsafe_b64encode(file.read(192*1024)).decode().rstrip('=')})
    except OSError as exc:
        fail(str(exc))
