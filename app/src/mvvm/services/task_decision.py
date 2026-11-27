"""Original task-decision.ts -> decision.ts Jev gate, non-streaming HTTP."""
import asyncio,json,math,time
from mvvm.services.provider_setup import build_transport


def config(settings,gate):
    providers=settings.models_section().get('providers',[])
    provider=next((p for p in providers if p.get('id')==gate.get('providerId')),None)
    if not provider or not provider.get('enabled') or provider.get('purpose')!='decision' or provider.get('adapter')!='jev':
        raise ValueError('决策供应商不存在、未启用或协议不受支持')
    threshold=gate.get('threshold',provider.get('threshold',.6))
    if not isinstance(threshold,(int,float)) or isinstance(threshold,bool) or not math.isfinite(threshold) or not 0<=threshold<=1:
        raise ValueError('决策阈值必须在 0 到 1 之间')
    return provider,threshold


def evaluate(settings,vault,task):
    gate=task.get('decision',{});result={'providerId':gate.get('providerId','')}
    try:
        provider,threshold=config(settings,gate);result['threshold']=threshold
        key=vault.get_secret(provider['id'])
        if not key:raise ValueError('no-key')
        payload={'state':task['prompt']+'\n\n'+json.dumps({'taskId':task['id'],'title':task['title'],'scheduledAt':task.get('nextRunAt'),'lastRunAt':task.get('lastRunAt'),'now':int(time.time()*1000)}),'model':'jev-latest','questions':{'execute':{'type':'noul','instructions':'根据任务指令与当前状态，现在是否应该执行这项任务？'}}}
        async def request():
            transport=build_transport()
            try:
                response=await transport.post(provider['apiHost'].rstrip('/')+'/v1/systemone',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},body=json.dumps(payload).encode())
                if response.status!=200:raise ValueError('decision HTTP '+str(response.status))
                return json.loads(await response.text())
            finally:await transport.aclose()
        async def bounded():return await asyncio.wait_for(request(),15)
        data=asyncio.run(bounded());confidence=data.get('answers',{}).get('execute',{}).get('noul')
        if type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=1:raise ValueError('Invalid decision answer: execute')
        return dict(result,status='allowed' if confidence>=threshold else 'denied',confidence=confidence)
    except asyncio.TimeoutError:return dict(result,status='timeout',message='请求超时（15s）')
    except Exception as exc:return dict(result,status='error',message=str(exc))
