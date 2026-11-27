"""Real sockets + real libproxy/WebKit PAC; never substitutes a proxy resolver."""
import asyncio, json, os, socket, sys, threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0, 'app/src')
from mvvm.services.provider_setup import build_transport
from mvvm.services.http_client import ProxyConfig, _matches_no_proxy
from mvvm.services.system_proxy import system_proxy
from mvvm.services.transport import HttpxTransport, NetworkError, CancelToken
from mvvm.services.http_client import CancelledError
calls=[]
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  calls.append(['pac',self.path]); self.send_response(200); self.end_headers()
  self.wfile.write(('function FindProxyForURL(url, host) { if (url.indexOf("/pac-direct") >= 0) return "DIRECT"; return "PROXY 127.0.0.1:'+str(proxy.server_port)+'"; }').encode())
 def do_POST(self):
  data=self.rfile.read(int(self.headers.get('Content-Length','0')))
  calls.append([self.server.role,self.path,data.decode()])
  if self.path == '/delivered-reset':
   self.connection.shutdown(socket.SHUT_RDWR); self.connection.close();return
  self.send_response(200); self.end_headers();self.wfile.write(b'loopback-ok')
 def log_message(self,*args): pass
servers=[]
def start(role,port=0):
 server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.role=role
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();servers.append((server,thread));return server
proxy=start('proxy');pac=start('pac');target=start('target')
for key in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy']:os.environ.pop(key,None)
os.environ['_PX_DEBUG_PACURL']='http://127.0.0.1:'+str(pac.server_port)+'/routes.pac'
async def send(t,url):
 response=await t.post(url,headers={},body=b'fixture');assert response.status==200
 assert await response.text()=='loopback-ok'
async def run():
 # Env proxy, then NO_PROXY direct on an actual loopback target.
 proxy_uri='http://127.0.0.1:'+str(proxy.server_port)
 os.environ['HTTP_PROXY']=proxy_uri
 env=build_transport();await send(env,'http://destination.invalid/env');await env.aclose()
 os.environ['NO_PROXY']='127.0.0.0/8';direct=build_transport();await send(direct,f'http://127.0.0.1:{target.server_port}/direct');await direct.aclose()
 os.environ.pop('HTTP_PROXY');os.environ.pop('NO_PROXY')
 # A genuinely closed origin fails to connect. Real PAC routes it to proxy.
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 url=f'http://127.0.0.1:{port}'
 resolved=system_proxy(url+'/fallback');assert resolved==proxy_uri,(resolved,proxy_uri)
 assert system_proxy(url+'/pac-direct') is None
 t=build_transport();await send(t,url+'/fallback');assert t._route_by_origin[url]=='system'
 # Server starts after the first call; remembering system route must still proxy.
 recovered=start('recovered',port);await send(t,url+'/remembered')
 assert not any(c[0]=='recovered' for c in calls)
 # Stop real proxy, retry remembered system then direct, update origin memory.
 proxy.shutdown();proxy.server_close();await send(t,url+'/reverse');assert t._route_by_origin[url]=='default'
 # Delivered body + closed connection must never replay through the other route.
 count=len(calls)
 try:await send(t,url+'/delivered-reset');raise AssertionError('expected reset')
 except NetworkError:pass
 assert len(calls)==count+1
 token=CancelToken();token.cancel();count=len(calls)
 try:await t.post(url+'/cancelled',headers={},body=b'cancel',cancel=token);raise AssertionError('expected cancellation')
 except CancelledError:pass
 assert len(calls)==count
 await t.aclose()
 cases=[('127.0.0.1','127.0.0.0/8',80,True),('a.example.com','*.example.com',80,True),('example.com','*.example.com',80,True),('example.com','example.com:443',443,True),('example.com','example.com:443',80,False),('b.test','a.test b.test',80,True),('::1','[::1]:8080',8080,True)]
 for host,rule,port,expected in cases:assert _matches_no_proxy(host,rule,port)==expected,(host,rule)
 Path('out/final-port/proxy-routes.json').write_text(json.dumps({'calls':calls,'pac_resolution':resolved,'routes':t._route_by_origin,'no_proxy':cases,'real_libproxy':True},indent=2))
 print(json.dumps({'calls':calls,'no_proxy_cases':len(cases),'result':'PASS'},indent=2))
try:asyncio.run(run())
finally:
 for server,thread in servers:server.shutdown();server.server_close();thread.join()
