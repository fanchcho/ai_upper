"""Feishu registerApp device authorization, matching the original SDK protocol.

Reference: deva remote/feishu-onboard.ts and @larksuiteoapi/node-sdk registerApp.
Endpoint overrides are restricted to loopback for reproducible protocol tests.
"""
import asyncio
import gzip
import json
import os
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from mvvm.services.channel_push import encode
from mvvm.services.provider_setup import build_transport
from mvvm.services.qr_image import qr_image


def endpoint(domain):
    override = os.environ.get('AI_UPPER_FEISHU_REGISTRATION', '')
    if override:
        parsed = urlsplit(override)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1':
            raise ValueError('registration test endpoint must be http://127.0.0.1')
        return override
    return 'https://accounts.' + ('larksuite.com' if domain == 'lark' else 'feishu.cn') + '/oauth/v1/app/registration'


def scan(cancel, emit):
    async def run():
        transport = build_transport()
        async def request(domain, fields):
            response = await transport.post(endpoint(domain), headers={'Content-Type': 'application/x-www-form-urlencoded'},
                                            body=urlencode(fields).encode())
            text = await response.text()
            try:
                result = json.loads(text)
            except ValueError:
                raise RuntimeError(text)
            return result
        try:
            begin = await request('feishu', {'action': 'begin', 'archetype': 'PersonalAgent',
                                           'auth_method': 'client_secret', 'request_user_info': 'open_id'})
            if cancel.is_set():
                return
            if not begin.get('verification_uri_complete') or not begin.get('device_code'):
                raise RuntimeError(json.dumps(begin, ensure_ascii=False))
            parts = urlsplit(begin['verification_uri_complete'])
            params = dict(parse_qsl(parts.query))
            addons = {'scopes': {'tenant': ['im:message.reactions:write_only']},
                      'events': {'items': {'tenant': ['im.message.receive_v1']}},
                      'callbacks': {'items': ['card.action.trigger']}}
            params.update({'from': 'sdk', 'source': 'node-sdk/deva', 'tp': 'sdk', 'createOnly': 'true',
                           'name': '{user}的 Deva', 'desc': '在飞书里和电脑上的 Deva 对话：查看回复、审批计划、接收定时任务结果。',
                           'addons': encode(gzip.compress(json.dumps(addons, separators=(',', ':')).encode()))})
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), parts.fragment))
            expires = time.time() + begin.get('expires_in', 600)
            emit({'status': 'waiting', 'url': url, 'qr': qr_image(url), 'expiresAt': int(expires * 1000)})
            interval, domain = begin.get('interval', 5), 'feishu'
            while not cancel.is_set() and time.time() < expires:
                result = await request(domain, {'action': 'poll', 'device_code': begin['device_code']})
                if cancel.is_set():
                    return
                if time.time() >= expires:
                    break
                if result.get('user_info', {}).get('tenant_brand') == 'lark' and domain != 'lark':
                    domain = 'lark'
                    continue
                if result.get('client_id') and result.get('client_secret'):
                    emit({'status': 'done', 'result': result, 'domain': domain})
                    return
                code = result.get('error')
                if code == 'slow_down':
                    interval += 5
                elif code not in (None, 'authorization_pending'):
                    emit({'status': {'access_denied': 'denied', 'expired_token': 'expired'}.get(code, 'error'),
                          'error': json.dumps(result, ensure_ascii=False)})
                    return
                # Wait is cancellable and never runs on the GUI thread.
                cancel.wait(min(interval, max(0, expires - time.time())))
            if not cancel.is_set():
                emit({'status': 'expired', 'error': 'expired_token: Polling timed out'})
        finally:
            await transport.aclose()
    try:
        asyncio.run(run())
    except Exception as exc:
        if not cancel.is_set():
            emit({'status': 'error', 'error': str(exc)})
