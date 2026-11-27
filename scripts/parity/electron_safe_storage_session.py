"""C9：把原版 Electron 的 safeStorage 接到私有 D-Bus/GNOME Secret Service 上跑一次真实验证。

不 mock 凭据 API：dbus-daemon 与 gnome-keyring-daemon 都是真实进程，Electron 走
chromium OSCrypt(libsecret)。脚本只做三件事：起隔离总线、起原版应用、用 CDP 驱动 UI
并在真实“已保存”状态截图。
"""
from __future__ import annotations
import json, os, pathlib, shutil, subprocess, sys, time, uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
SS = ROOT / ".tmp/secret-service"
OUT = ROOT / "out/electron-safe-storage"
NODE = "node"
CDP = str(ROOT / "scripts/parity/extensions_reference_cdp.mjs")


def start_bus():
    runtime = SS / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = f"{ROOT/'.tmp/icon-dpi/runtime/usr/bin'}:{ROOT/'.tmp/wm/usr/bin'}:{env.get('PATH','')}"
    env.update(
        LD_LIBRARY_PATH=f"{SS/'root/usr/lib/aarch64-linux-gnu'}:{ROOT/'.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu'}:{ROOT/'.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu'}:{ROOT/'.tmp/wm/usr/lib/aarch64-linux-gnu'}",
        XDG_DATA_HOME=str(runtime / "data"), XDG_RUNTIME_DIR=str(runtime),
        XDG_CONFIG_HOME=str(runtime / "config"), XDG_CURRENT_DESKTOP="GNOME",
    )
    conf = SS / "bus.conf"
    conf.write_text(
        '<busconfig><type>session</type><listen>unix:tmpdir=' + str(runtime) +
        '</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*" eavesdrop="true"/>'
        '<allow eavesdrop="true"/><allow own="*"/></policy></busconfig>')
    bus = subprocess.Popen([str(SS / "root/usr/bin/dbus-daemon"), "--nofork", "--print-address=1",
                            "--config-file=" + str(conf)], stdout=subprocess.PIPE, text=True, env=env)
    addr = bus.stdout.readline().strip()
    assert addr, "dbus-daemon 没有输出地址"
    env["DBUS_SESSION_BUS_ADDRESS"] = addr
    daemon = subprocess.run([str(SS / "root/usr/bin/gnome-keyring-daemon"), "--unlock",
                             "--components=secrets", "--control-directory=" + str(runtime / "keyring")],
                            input="fixture-only-password\n", text=True, env=env, capture_output=True, timeout=20)
    print("KEYRING", daemon.returncode, daemon.stdout.strip(), flush=True)
    for line in daemon.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    time.sleep(1)
    return bus, env, addr


def cdp(expr: str, shot: str | None = None):
    cmd = [NODE, CDP, expr] + ([shot] if shot else [])
    run = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    if run.returncode != 0:
        raise RuntimeError(run.stderr[-800:])
    return json.loads(run.stdout)["result"]["result"].get("value")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bus, env, addr = start_bus()
    home = pathlib.Path("/tmp/deva-electron-safe-" + uuid.uuid4().hex[:8])
    home.mkdir(parents=True)
    (home / "config.json").write_text(json.dumps({"locale": "en", "theme": "light", "closeToTray": False}))
    (home / "mcp.json").write_text(json.dumps({"mcpServers": {"probe": {
        "name": "Probe", "description": "safeStorage probe", "transport": "stdio",
        "command": "/bin/cat", "env": {"TOKEN": {"secretRef": "TOKEN"}}}}}))
    (home / "tmp").mkdir()
    env.update(DEVA_HOME=str(home), HOME=str(home), TMPDIR=str(home / "tmp"))
    log = open(OUT / "session.log", "w")
    proc = subprocess.Popen([
        str(ROOT / ".tmp/wm/usr/bin/xvfb-run"), "-a",
        str(ROOT / ".tmp/extensions-complete/browser/node_modules/electron/dist/electron"),
        "--no-sandbox", "--disable-gpu", "--remote-debugging-port=9344",
        "--user-data-dir=/tmp/deva-electron-ud-" + uuid.uuid4().hex[:8],
        "/home/agent/shared_workspace/deva/apps/desktop/out/main/index.js",
    ], env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                if cdp("1+1") == 2:
                    break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(f"Electron 提前退出 rc={proc.returncode}: {(OUT/'session.log').read_text()[-800:]}")
                time.sleep(1)
        else:
            raise RuntimeError("CDP 未就绪")
        print("SECRETS_AVAILABLE", cdp("window.deva.secrets.available()"), flush=True)
        print("INITIAL_BODY", cdp("document.body.innerText.slice(0,300)"), flush=True)
        print("CLICK_SETTINGS", cdp("(function(){var b=[...document.querySelectorAll('button')].find(x=>x.getAttribute('aria-label')==='Settings'); if(!b)return 'no-button'; b.click(); return 'ok'})()"), flush=True)
        time.sleep(1)
        print("SETTINGS_BODY", cdp("document.body.innerText.slice(0,1200)"), flush=True)
        print("SETTINGS_BUTTONS", cdp("JSON.stringify([...document.querySelectorAll('button')].map(x=>({t:(x.textContent||'').trim().slice(0,30),a:x.getAttribute('aria-label')})).slice(0,40))"), flush=True)
        cdp("1", str(OUT / "settings-open.png"))
        print("SHOT settings-open", flush=True)
        print("CLICK_EXT", cdp("(function(){var b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Extensions'); if(!b)return 'no'; b.click(); return 'ok'})()"), flush=True)
        time.sleep(1)
        print("EXT_BODY", cdp("document.body.innerText.slice(0,1500)"), flush=True)
        print("EXT_ROWS", cdp("JSON.stringify([...document.querySelectorAll('button,[role=button]')].map(x=>({t:(x.textContent||'').trim().slice(0,60),c:x.className})).filter(x=>x.t).slice(0,50))"), flush=True)
        cdp("1", str(OUT / "extensions-list.png"))
        print("SHOT extensions-list", flush=True)
        print("CLICK_PROBE", cdp("(function(){var b=[...document.querySelectorAll('button.cf-setrow__open')].find(x=>x.textContent.includes('Probe')); if(!b)return 'no'; b.click(); return 'ok'})()"), flush=True)
        time.sleep(1)
        print("PROBE_BODY", cdp("document.body.innerText.slice(0,2000)"), flush=True)
        print("PROBE_INPUTS", cdp("JSON.stringify([...document.querySelectorAll('input')].map(x=>({ph:x.placeholder,type:x.type,val:x.value})))"), flush=True)
        cdp("1", str(OUT / "mcp-detail.png"))
        print("SHOT mcp-detail", flush=True)
        print("TYPE_SECRET", cdp("(function(){var i=[...document.querySelectorAll('input')].find(x=>x.placeholder&&x.placeholder.indexOf('Enter secret value')===0); if(!i)return 'no-input'; var setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; setter.call(i,'fixture-electron-safe'); i.dispatchEvent(new Event('input',{bubbles:true})); i.focus(); return 'typed'})()"), flush=True)
        time.sleep(1.4)
        body = cdp("document.body.innerText")
        print("BODY_HAS_SAVED", "Saved" in body, flush=True)
        print("STATUS_TEXT", cdp("(function(){var e=[...document.querySelectorAll('.key-status')].map(x=>x.textContent.trim()); return JSON.stringify(e)})()"), flush=True)
        print("SCROLL", cdp("(function(){var els=[...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+40 && e.clientHeight>250); if(!els.length)return 'none'; els[0].scrollTop=els[0].scrollHeight; return els[0].className+' '+els[0].scrollTop+'/'+els[0].scrollHeight})()"), flush=True)
        time.sleep(0.4)
        cdp("1", str(OUT / "deva-secret-saved.png"))
        print("SHOT deva-secret-saved", flush=True)
        # 读回：secrets.json 密文 + 钥匙环条目（只枚举 label/attributes，不读明文）。
        secrets_file = home / "secrets.json"
        print("SECRETS_JSON", secrets_file.exists(), secrets_file.stat().st_size if secrets_file.exists() else -1, flush=True)
        code = r"""
import os, json
import secretstorage
bus = secretstorage.dbus_init()
col = secretstorage.get_default_collection(bus)
items = []
for item in col.get_all_items():
    try:
        items.append({"label": item.get_label(), "attrs": {k: v for k, v in item.get_attributes().items() if k in ("application", "xdg:schema")}})
    except Exception as e:
        items.append({"error": str(e)})
print(json.dumps(items, ensure_ascii=False))
"""
        run = subprocess.run([str(ROOT / ".venv/bin/python"), "-c", code], env=env, capture_output=True, text=True, timeout=30)
        print("KEYRING_ITEMS", run.stdout.strip(), run.stderr[-300:], flush=True)
    finally:
        proc.terminate()
        try: proc.wait(timeout=10)
        except Exception: proc.kill()
        bus.terminate()
        try: bus.wait(timeout=5)
        except Exception: bus.kill()


if __name__ == "__main__":
    main()
