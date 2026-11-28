from types import SimpleNamespace
import base64
from mvvm.services.phone_uploads import Uploads


def test_upload_owner_order_size_and_consumption(tmp_path):
    registered=[];uploads=Uploads(SimpleNamespace(home=tmp_path,attachments=SimpleNamespace(inspect_paths=registered.extend)))
    frames=[];send=frames.append
    uploads.handle('a',{'t':'up_begin','uid':'test1','name':'../../a.txt','size':3},send)
    uploads.handle('b',{'t':'up_chunk','uid':'test1','seq':0,'data':'YWJj'},send)
    assert frames[-1]['state']=='failed' and uploads.rows['test1']['received']==0
    uploads.handle('a',{'t':'up_chunk','uid':'test1','seq':0,'data':'YWJj'},send)
    uploads.handle('a',{'t':'up_end','uid':'test1'},send)
    paths=uploads.take('a',['test1']);assert paths==registered
    from pathlib import Path
    assert Path(paths[0]).read_bytes()==b'abc' and Path(paths[0]).name=='a.txt'
    assert 'test1' not in uploads.rows
    uploads.handle('a',{'t':'up_begin','uid':'test2','name':'b.txt','size':3},send)
    path=uploads.rows['test2']['path']
    uploads.handle('a',{'t':'up_chunk','uid':'test2','seq':1,'data':'YWJj'},send)
    assert frames[-1]['state']=='failed' and not path.exists()
