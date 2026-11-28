"""Loopback OpenAI SSE fixture. This is not an external model."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,threading,os
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  out=Path(os.environ.get('PARITY_OUTPUT_DIR','docs/audit/next-boundary'))
  (out/('http-request-'+str(self.server.server_port)+'.json')).write_text(json.dumps({'path':self.path,'body':data},ensure_ascii=False,indent=2))
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  for delta,finish in [({'role':'assistant','content':'本地 fixture 收到你好'},None),({},'stop')]:
   event={'id':'local-fixture','object':'chat.completion.chunk','choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
   self.wfile.write(('data: '+json.dumps(event,ensure_ascii=False)+'\n\n').encode())
  self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
 def log_message(self,*args):pass
def start():
 s=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=s.serve_forever,daemon=True).start();return s
