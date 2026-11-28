from types import SimpleNamespace
from mvvm.services.phone_tasks import task_action


def test_phone_completed_task_resume_and_unknown_action_refused():
    calls=[]
    api=SimpleNamespace(read=lambda:[{'id':'once','status':'completed'}],running={},deciding=set(),action=lambda *a:calls.append(a))
    shell=SimpleNamespace(tasksService=lambda:api)
    # Errors must not call the task service mutation path.
    import mvvm.services.phone_tasks as module
    original=module.task_list
    module.task_list=lambda shell:[]
    try:
        replies=[]
        for action in ('resume','unknown'):
            task_action(shell,{'id':'once','action':action},replies.append)
            assert replies[-2]['ok'] is False
        assert not calls
    finally:module.task_list=original
