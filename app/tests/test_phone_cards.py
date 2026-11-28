from types import SimpleNamespace
import threading
import time
from mvvm.services.plugin_interactions import Interactions
from mvvm.services.phone_cards import action


def test_mobile_card_answer_cannot_cross_scope_or_replay(tmp_path):
    interactions=Interactions(tmp_path,timeout=10)
    worker=threading.Thread(target=lambda:interactions.request('private','op','plan','plan'));worker.start()
    for _ in range(100):
        if interactions.pending('private'):break
        time.sleep(.01)
    shell=SimpleNamespace(_host=SimpleNamespace(interactions=interactions));out=[]
    frame={'value':{'k':'plan','key':'private:op','d':'approve'},'rid':'r'}
    action(shell,{'allowed'},frame,out.append)
    assert out[-1]['ok'] is False
    action(shell,{'private'},frame,out.append)
    assert out[-1]['ok'] is True
    worker.join(1)
    action(shell,{'private'},frame,out.append)
    assert out[-1]['ok'] is False
