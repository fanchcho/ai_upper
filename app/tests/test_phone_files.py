from types import SimpleNamespace
from mvvm.services.phone_files import send_file


def test_download_is_bound_to_delivered_sidecar(tmp_path):
    file=tmp_path/'report.txt';file.write_text('report')
    session=SimpleNamespace(delivered={'tool':[str(file)]});out=[]
    send_file(session,{'rid':'r','tool':'other','index':0,'path':str(file)},out.append)
    assert out[-1]['ok'] is False
    send_file(session,{'rid':'r','tool':'tool','index':True},out.append)
    assert out[-1]['ok'] is False
    send_file(session,{'rid':'r','tool':'tool','index':0},out.append)
    assert out[-1]['text']=='report'
    file.unlink()
    send_file(session,{'rid':'r','tool':'tool','index':0},out.append)
    assert out[-1]['ok'] is False
