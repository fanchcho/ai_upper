"""MCP tools for the desktop worker: stdio and Streamable HTTP.

Lifecycle/transport: modelcontextprotocol.io/specification/2025-06-18/basic.
Connections live for one turn and are closed on disable, cancellation and completion.
"""
from __future__ import annotations
from locale_runtime import tr

import hashlib
import json
import os
import queue
import subprocess
import threading
import time
import weakref
from urllib.parse import urljoin, urlsplit

import httpx

from mvvm.services.tool_runtime import ToolResult, ToolSpec

_active = weakref.WeakSet()


def stop_server(scope, name):
    for group in list(_active):
        if group.service.scope == scope:
            group.stop(name)


class McpConnection:
    def __init__(self, config, secret="", cancelled=lambda: False, timeout=60):
        self.config, self.cancelled, self.timeout = config, cancelled, timeout
        self.process = None
        self.client = None
        self.messages = queue.Queue()
        self.serial = 0
        self.closed = False
        self.headers = {"Accept": "application/json, text/event-stream"}
        if config.get("url"):
            if secret:
                if secret.lstrip().startswith('{'):
                    values = json.loads(secret)
                    if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
                        raise ValueError(tr('legacy.ff8404a7dd4c'))
                    self.headers.update(values)
                else:
                    self.headers["Authorization"] = "Bearer " + secret
            self.client = httpx.Client(timeout=timeout, follow_redirects=False)
        else:
            env = os.environ.copy()
            if secret:
                # A JSON map permits MCP servers with their own credential names.
                values = json.loads(secret)
                if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in values.items()):
                    raise ValueError(tr('legacy.c2f59ad62975'))
                env.update(values)
            self.process = subprocess.Popen(
                [config["command"], *config.get("args", [])], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                encoding="utf-8", env=env, bufsize=1,
            )
            threading.Thread(target=self._read_stdio, daemon=True).start()

    def _read_sse(self):
        # Legacy MCP SSE: GET announces a same-origin POST endpoint.
        # specification/2024-11-05/basic/transports; SDK client/sse.ts.
        try:
            with self.client.stream("GET", self.config["url"], headers=self.headers) as response:
                response.raise_for_status()
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise ValueError("Expected an SSE stream")
                event, data = "message", []
                for line in response.iter_lines():
                    if self.closed or self.cancelled(): break
                    if line.startswith("event:"): event = line[6:].strip()
                    elif line.startswith("data:"): data.append(line[5:].lstrip())
                    elif not line and data:
                        value = "\n".join(data)
                        if event == "endpoint":
                            endpoint = urljoin(self.config["url"], value)
                            original, target = urlsplit(self.config["url"]), urlsplit(endpoint)
                            if (original.scheme, original.netloc) != (target.scheme, target.netloc):
                                raise ValueError("SSE endpoint origin mismatch")
                            self.sse_endpoint = endpoint
                            self.sse_ready.set()
                        elif event == "message": self.messages.put(json.loads(value))
                        event, data = "message", []
        except Exception as exc:
            self.sse_error = type(exc).__name__
        finally:
            self.sse_ready.set()
            self.messages.put({"transportClosed": True})

    def _read_stdio(self):
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        except Exception:
            pass
        finally:
            self.messages.put({"transportClosed": True})

    def _http(self, payload, responses):
        try:
            with self.client.stream("POST", self.config["url"], json=payload, headers=self.headers) as response:
                response.raise_for_status()
                session = response.headers.get("mcp-session-id")
                if session:
                    self.headers["Mcp-Session-Id"] = session
                if "id" not in payload:
                    responses.put({"notificationAccepted": True})
                elif "text/event-stream" in response.headers.get("content-type", ""):
                    data = []
                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            message = json.loads("\n".join(data)); data = []
                            responses.put(message)
                            if message.get("id") == payload["id"] and "method" not in message:
                                return
                    responses.put({"transportClosed": True})
                else:
                    response.read()
                    responses.put(response.json())
        except Exception as exc:
            # Never expose server responses/headers containing credentials to UI.
            responses.put({"transportError": type(exc).__name__})

    def send(self, payload, responses=None):
        if self.closed:
            raise OSError(tr('legacy.61b329a7034e'))
        if self.process:
            self.process.stdin.write(json.dumps(payload) + "\n")
            self.process.stdin.flush()
        elif self.config.get("transport") == "sse":
            response = self.client.post(self.sse_endpoint, json=payload, headers=self.headers)
            response.raise_for_status()
            if "id" not in payload and responses is not None:
                responses.put({"notificationAccepted": True})
        else:
            threading.Thread(target=self._http, args=(payload, responses or queue.Queue()), daemon=True).start()

    def notify(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if self.process:
            self.send(payload)
        else:
            responses = queue.Queue()
            self.send(payload, responses)
            try:
                result = responses.get(timeout=min(5, self.timeout))
            except queue.Empty:
                raise OSError(tr('legacy.4cf3b8682862'))
            if result.get('transportError'): raise OSError(tr('legacy.82c3b1a4e695'))

    def request(self, method, params=None):
        self.serial += 1
        request_id = self.serial
        messages = self.messages if self.process or self.config.get("transport") == "sse" else queue.Queue()
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}, messages)
        deadline = time.monotonic() + self.timeout
        while True:
            if self.closed or self.cancelled() or time.monotonic() >= deadline:
                try:
                    self.notify("notifications/cancelled", {"requestId": request_id, "reason": "cancelled or timed out"})
                finally:
                    self.close()
                raise OSError(tr('legacy.be14f46f4f53'))
            try:
                message = messages.get(timeout=.05)
            except queue.Empty:
                continue
            if message.get("transportClosed") or message.get("transportError"):
                raise OSError(tr('legacy.8a3104d19976'))
            if "method" in message:
                if "id" in message:
                    reply = {"jsonrpc": "2.0", "id": message["id"]}
                    if message["method"] == "ping": reply["result"] = {}
                    else: reply["error"] = {"code": -32601, "message": "Unsupported client capability"}
                    self.send(reply)
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise OSError(tr('legacy.8d2569bcebf5') + str(message["error"].get("code", "unknown")))
            return message.get("result", {})

    def initialize(self):
        if self.config.get("transport") == "sse":
            self.sse_ready = threading.Event()
            self.sse_endpoint, self.sse_error = None, None
            threading.Thread(target=self._read_sse, daemon=True).start()
            if not self.sse_ready.wait(self.timeout) or self.sse_error or not self.sse_endpoint:
                raise OSError("SSE connection failed: " + (self.sse_error or "no endpoint"))
        result = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "ai_upper", "version": "1"}})
        version = result.get("protocolVersion")
        if version not in ("2025-06-18", "2025-03-26", "2024-11-05"):
            raise ValueError(tr('legacy.53bf4abaee00'))
        self.headers["MCP-Protocol-Version"] = version
        self.notify("notifications/initialized")

    def close(self):
        if self.closed: return
        self.closed = True
        if self.process:
            try: self.process.stdin.close()
            except OSError: pass
            try: self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try: self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait()
            self.process.stdout.close()
        if self.client:
            self.client.close()


class McpTools:
    def __init__(self, service, runtime):
        self.service, self.runtime = service, runtime
        self.connections, self.tools = {}, {}
        _active.add(self)

    def stop(self, name):
        connection = self.connections.pop(name, None)
        if connection: connection.close()
        self.tools = {k: v for k, v in self.tools.items() if v[0] != name}

    def close(self):
        for name in list(self.connections): self.stop(name)

    def specs(self):
        servers = {row['id']: row for row in self.service.servers() if row['enabled']}
        for name in list(self.connections):
            if name not in servers: self.stop(name)
        for name, config in servers.items():
            if name in self.connections: continue
            connection = McpConnection(config, self.service.vault.get_secret(self.service.key_id('mcp', name)) or '', lambda: bool(self.runtime.cancel_check and self.runtime.cancel_check()))
            self.connections[name] = connection
            try:
                connection.initialize()
                cursor, seen = None, set()
                while True:
                    result = connection.request('tools/list', {'cursor': cursor} if cursor else {})
                    for item in result.get('tools', []):
                        original = item['name']
                        suffix = hashlib.sha256((name + ':' + original).encode()).hexdigest()[:16]
                        public = 'mcp__' + name[:24].replace('.', '_').replace('-', '_') + '__' + suffix
                        spec = ToolSpec(public, item.get('description', original), item.get('inputSchema', {'type': 'object'}))
                        self.tools[public] = (name, original, spec)
                    cursor = result.get('nextCursor')
                    if not cursor: break
                    if cursor in seen: raise ValueError(tr('legacy.8e0969d8814e'))
                    seen.add(cursor)
            except Exception:
                self.stop(name)
                raise
        return [row[2] for row in self.tools.values()]

    def execute(self, name, arguments):
        entry = self.tools.get(name)
        if not entry: return ToolResult('MCP server was disabled or tool is unavailable', True)
        server, original, _ = entry
        connection = self.connections.get(server)
        if not connection: return ToolResult('MCP server stopped', True)
        try:
            result = connection.request('tools/call', {'name': original, 'arguments': arguments})
            content = '\n'.join(part.get('text', json.dumps(part, ensure_ascii=False)) for part in result.get('content', []))
            return ToolResult(content[:30000], bool(result.get('isError')))
        except (OSError, ValueError) as exc:
            return ToolResult(str(exc), True)
