import json
from test_qml_window_controls import qapp, _build_window, _pump, _find_item, _click_item
import threading


def test_custom_model_editor_hides_secret(qapp,tmp_path,monkeypatch):
    w,bridge,ticker,engine=_build_window(tmp_path,monkeypatch)
    try:
        w.setProperty('page','settings-models'); _pump(qapp)
        _click_item(w,_find_item(w.contentItem(),'modelsCustomNetwork')); _pump(qapp)
        root=w.contentItem()
        _find_item(root,'pluginBaseUrl').setProperty('text','https://example.test/v1')
        _find_item(root,'pluginModelName').setProperty('text','custom:model')
        _find_item(root,'pluginSecret').setProperty('text','test-secret')
        _click_item(w,_find_item(root,'pluginSave')); _pump(qapp)
        result=json.loads(bridge.pluginSettings('read','{}'))
        assert result['model']['hasKey']
        assert 'test-secret' not in json.dumps(result)
        assert _find_item(root,'pluginSecret').property('text')==''
    finally:
        ticker.stop();w.close();_pump(qapp,.1);del engine


def test_mcp_and_identity_editors(qapp,tmp_path,monkeypatch):
    w,bridge,ticker,engine=_build_window(tmp_path,monkeypatch)
    try:
        w.setProperty('page','settings-mcp'); _pump(qapp)
        root=w.contentItem()
        _find_item(root,'pluginIdentifier').setProperty('text','local')
        _find_item(root,'pluginBaseUrl').setProperty('text','https://mcp.test')
        _find_item(root,'pluginEnabled').setProperty('checked',False)
        _click_item(w,_find_item(root,'pluginSave'));_pump(qapp)
        result=json.loads(bridge.pluginSettings('read','{}'))
        assert result['servers'][0]['id']=='local' and not result['servers'][0]['enabled']
        w.setProperty('page','settings-identities');_pump(qapp)
        _find_item(root,'pluginIdentifier').setProperty('text','test-persona')
        _find_item(root,'pluginPersonaBody').setProperty('text','Authoritative disk content')
        _click_item(w,_find_item(root,'pluginSave'));_pump(qapp)
        assert {'id':'test-persona','text':'Authoritative disk content'} in json.loads(bridge.pluginSettings('identities','{}'))['identities']
    finally:
        ticker.stop();w.close();_pump(qapp,.1);del engine


def test_actual_qml_approval_and_answer_buttons(qapp,tmp_path,monkeypatch):
    w,bridge,ticker,engine=_build_window(tmp_path,monkeypatch)
    workers=[]
    try:
        sid=bridge.newSession()
        controller=bridge._host.interactions
        for kind,outcome,button in [('approval','approved','interactionAccept'),('approval','denied','interactionReject'),('question','answered','interactionAccept'),('question','dismissed','interactionReject')]:
            results=[]
            worker=threading.Thread(target=lambda:results.append(controller.request(sid,kind+outcome,kind,'Test question',cancelled=None)))
            workers.append(worker);worker.start()
            _pump(qapp,1)
            assert bridge.pendingInteractions(), (sid, bridge._active)
            assert _find_item(w.contentItem(),'interactionPrompt').property('visible')
            if kind=='question': _find_item(w.contentItem(),'interactionAnswer').setProperty('text','Actual QML answer')
            _click_item(w,_find_item(w.contentItem(),button));_pump(qapp,.3)
            worker.join(1);assert not worker.is_alive()
            assert results[0]['outcome']==outcome
            if outcome=='answered': assert results[0]['answer']=='Actual QML answer'
    finally:
        for row in bridge.pendingInteractions(): bridge.answerInteraction(row['id'],'cancelled','')
        for worker in workers:worker.join(1)
        ticker.stop();w.close();_pump(qapp,.1);del engine
