"""Device-owned upload staging, matching remote/web/files.ts."""
import base64
import re
import time
from pathlib import Path


class Uploads:
    def __init__(self, host):
        self.host=host;self.rows={}

    def drop(self, uid, remove=True):
        row=self.rows.pop(uid,None)
        if row and remove:row['path'].unlink(missing_ok=True)

    def handle(self, device, frame, send):
        now=time.time()
        for uid,row in list(self.rows.items()):
            if now-row['at']>7200:self.drop(uid,not row['done'])
        uid=frame.get('uid');kind=frame['t']
        if not isinstance(uid,str) or not re.fullmatch(r'[\w-]{4,40}',uid):return
        def fail(message):send({'t':'upload','uid':uid,'state':'failed','message':message})
        if kind=='up_begin':
            size=frame.get('size')
            if not isinstance(size,int) or isinstance(size,bool) or not 0<=size<=50*1024*1024:return fail('文件大小无效或超过 50 MB')
            if uid in self.rows:return fail('重复的上传')
            if sum(not r['done'] for r in self.rows.values())>=20:return fail('同时上传的文件太多')
            name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(frame.get('name','')).replace('\\','/').split('/')[-1]).strip()[:120]
            if not name or not name.strip('.'):name='手机上传'
            directory=Path(self.host.home)/'uploads'/time.strftime('%Y-%m-%d');directory.mkdir(parents=True,exist_ok=True)
            path=directory/name;n=1
            while True:
                try:
                    with path.open('xb'):pass
                    break
                except FileExistsError:
                    n+=1;path=directory/(Path(name).stem+' ('+str(n)+')'+Path(name).suffix)
            self.rows[uid]={'device':device,'path':path,'size':size,'received':0,'seq':0,'done':False,'at':now}
            send({'t':'upload','uid':uid,'state':'ready'});return
        row=self.rows.get(uid)
        if not row or row['device']!=device:return fail('上传不存在或属于另一设备')
        if kind=='up_cancel':self.drop(uid);return
        if row['done']:return fail('上传已完成')
        try:
            if kind=='up_chunk':
                raw=frame.get('data','');data=base64.b64decode(raw+'='*((-len(raw))%4),altchars=b'-_',validate=True)
                if frame.get('seq')!=row['seq'] or row['received']+len(data)>row['size']:raise ValueError('上传的数据不完整')
                with row['path'].open('ab') as file:file.write(data)
                row['seq']+=1;row['received']+=len(data);row['at']=now
            elif kind=='up_end':
                if row['received']!=row['size']:raise ValueError('上传的数据不完整')
                self.host.attachments.inspect_paths([str(row['path'])]);row['done']=True;row['at']=now
                send({'t':'upload','uid':uid,'state':'done'})
        except Exception as exc:
            self.drop(uid);fail(str(exc))

    def take(self,device,ids):
        if not isinstance(ids,list) or len(ids)>20:raise ValueError('上传列表无效')
        rows=[self.rows.get(uid) if isinstance(uid,str) else None for uid in ids]
        if any(not r or r['device']!=device or not r['done'] for r in rows):raise ValueError('附件未完成或属于另一设备')
        paths=[str(r['path']) for r in rows]
        for uid in ids:self.rows.pop(uid,None)
        return paths
