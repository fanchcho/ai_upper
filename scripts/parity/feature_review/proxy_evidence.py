"""Real loopback HTTP requests proving env-proxy and direct routes (no system proxy claim)."""
import asyncio,json,os,sys,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,'app/src')
from mvvm.services.http_client import ProxyConfig,build_client
paths=[]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  paths.append(self.path);self.send_response(200);self.end_headers();self.wfile.write(b'route evidence')
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
async def run():
 proxy='http://127.0.0.1:'+str(server.server_port)
 for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy']:os.environ.pop(key,None)
 os.environ['HTTP_PROXY']=proxy
 route=ProxyConfig.from_env().for_url('http://target.invalid/evidence')
 assert route==proxy
 async with build_client(route) as c:assert (await c.get('http://target.invalid/evidence')).status_code==200
 os.environ['NO_PROXY']='127.0.0.1'
 direct=ProxyConfig.from_env().for_url(proxy+'/direct');assert direct is None
 async with build_client(direct) as c:assert (await c.get(proxy+'/direct')).status_code==200
 assert paths==['http://target.invalid/evidence','/direct'],paths
 Path('out/parity-close/proxy.json').write_text(json.dumps({'requests':paths,'env_proxy':route,'no_proxy_route':direct,'system_proxy':'absent in source; not emulated'},indent=2))
try:asyncio.run(run())
finally:server.shutdown();server.server_close();thread.join()
