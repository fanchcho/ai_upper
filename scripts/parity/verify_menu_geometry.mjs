/**
 * 只读探针：实测原版 Deva 会话行右键菜单的**项数与每项几何**。
 *
 * 为什么需要它：deva_page_shot.sh 的 delete-confirm 用固定坐标点菜单项，项数一变
 * （4 项→5 项）就会点到隔壁项。坐标必须来自渲染进程实测，不能按 ~31px 估算。
 *
 * 用法: node verify_menu_geometry.mjs <输出 json>
 * deva 工程只读：只启动它、往窗口里发真实鼠标事件。
 */
import fs from 'node:fs'
import { execFileSync, spawn } from 'node:child_process'

const OUT = process.argv[2]
const DEVA_ROOT = '/home/agent/shared_workspace/deva'
const DISPLAY = ':98'
const HOME_DIR = '/tmp/verify-menu-home'
const PROFILE = '/tmp/verify-menu-profile'
const PORT = 9331
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const sh = (cmd, args, opts = {}) =>
  execFileSync(cmd, args, { encoding: 'utf8', env: { ...process.env, DISPLAY }, ...opts })

function cleanup() {
  try { sh('pkill', ['-f', 'apps/desktop/out/main/index.js']) } catch {}
  try { sh('pkill', ['-f', `Xvfb ${DISPLAY}`]) } catch {}
  for (const f of [`/tmp/.X${DISPLAY.slice(1)}-lock`, `/tmp/.X11-unix/X${DISPLAY.slice(1)}`]) {
    try { fs.unlinkSync(f) } catch {}
  }
}

const cdpState = { next: 1, pending: new Map() }
function cdp(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = cdpState.next++
    const timer = setTimeout(() => reject(new Error(`${method} timeout`)), 20000)
    cdpState.pending.set(id, (msg) => {
      clearTimeout(timer)
      if (msg.error) reject(new Error(`${method}: ${msg.error.message}`))
      else resolve(msg.result)
    })
    ws.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(ws, expression) {
  const res = await cdp(ws, 'Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
  if (res.exceptionDetails) throw new Error('evaluate: ' + JSON.stringify(res.exceptionDetails))
  return res.result.value
}
const mouse = (ws, type, x, y, button = 'left') =>
  cdp(ws, 'Input.dispatchMouseEvent', {
    type, x, y, button, clickCount: 1, buttons: type === 'mousePressed' ? 1 : 0,
  })

cleanup()
fs.rmSync(HOME_DIR, { recursive: true, force: true })
fs.rmSync(PROFILE, { recursive: true, force: true })
fs.mkdirSync(`${HOME_DIR}/data/chats`, { recursive: true })
fs.mkdirSync(PROFILE, { recursive: true })
fs.cpSync('/tmp/fx-pages/data/chats', `${HOME_DIR}/data/chats`, { recursive: true })
fs.writeFileSync(`${HOME_DIR}/config.json`, JSON.stringify({ locale: 'en', theme: 'light' }))

const xvfb = spawn('Xvfb', [DISPLAY, '-screen', '0', '1400x900x24'], { stdio: 'ignore' })
await sleep(2000)
const electron = spawn(
  `${DEVA_ROOT}/node_modules/electron/dist/electron`,
  ['--no-sandbox', '--disable-gpu', `--user-data-dir=${PROFILE}`,
   `--remote-debugging-port=${PORT}`, `${DEVA_ROOT}/apps/desktop/out/main/index.js`],
  { env: { ...process.env, DISPLAY, DEVA_HOME: HOME_DIR },
    stdio: ['ignore', fs.openSync('/tmp/verify-menu-deva.log', 'w'), fs.openSync('/tmp/verify-menu-deva.log', 'a')] },
)

try {
  let target = null
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()
      target = list.find((t) => t.type === 'page')
      if (target) break
    } catch {}
    await sleep(500)
  }
  if (!target) throw new Error('没有拿到 CDP page target，见 /tmp/verify-menu-deva.log')

  const ws = new WebSocket(target.webSocketDebuggerUrl)
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data)
    const fn = cdpState.pending.get(msg.id)
    if (fn) { cdpState.pending.delete(msg.id); fn(msg) }
  }
  await new Promise((resolve, reject) => {
    ws.onopen = resolve
    ws.onerror = reject
  })
  await cdp(ws, 'Runtime.enable')
  await cdp(ws, 'Page.enable')

  // 窗口尺寸与 deva_page_shot.sh 一致：1280x820 客户端区。
  // 页面 target 上没有 Browser 域（getWindowForTarget 是 browser 级 target 的），
  // 用 Emulation 把视口钉到同一尺寸，CDP 输入坐标才是同一套。
  await cdp(ws, 'Emulation.setDeviceMetricsOverride', {
    width: 1280, height: 820, deviceScaleFactor: 1, mobile: false,
  })
  await sleep(1500)

  const viewport = await evaluate(ws, '({w: innerWidth, h: innerHeight, dpr: devicePixelRatio})')

  // 真实右键（CDP 输入事件，和截图脚本同一条路径）。
  await mouse(ws, 'mouseMoved', 160, 90)
  await mouse(ws, 'mousePressed', 160, 90, 'right')
  await mouse(ws, 'mouseReleased', 160, 90, 'right')
  await sleep(1200)

  const menu = await evaluate(ws, `(() => {
    const pick = (sel) => [...document.querySelectorAll(sel)];
    let items = pick('[role="menuitem"]');
    let menuEl = document.querySelector('[role="menu"]');
    if (!items.length && menuEl) items = [...menuEl.querySelectorAll('button, a, [tabindex]')];
    if (!items.length) {
      // 兜底：面板 = 右键点附近包含 ≥3 个等高可点击子的容器
      const all = pick('div, ul').filter((el) => {
        const b = el.getBoundingClientRect();
        return b.width > 80 && b.width < 320 && b.height > 90 && b.height < 400 &&
               Math.abs(b.left - 160) < 40 && [...el.children].length >= 3;
      });
      menuEl = all.sort((a, b) => b.querySelectorAll('*').length - a.querySelectorAll('*').length)[0] || null;
      if (menuEl) items = [...menuEl.children];
    }
    const mb = menuEl ? menuEl.getBoundingClientRect() : null;
    return {
      menuRole: menuEl ? menuEl.getAttribute('role') : null,
      menuRect: mb && {x: Math.round(mb.x), y: Math.round(mb.y), w: Math.round(mb.width), h: Math.round(mb.height)},
      count: items.length,
      items: items.map((el) => {
        const b = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return {
          text: (el.innerText || el.textContent || '').trim().slice(0, 40),
          role: el.getAttribute('role'),
          rect: {x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height)},
          center: {x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2)},
          padTop: cs.paddingTop, color: cs.color, background: cs.backgroundColor,
        };
      }),
    };
  })()`)

  const report = { page: 'delete-confirm', viewport, menu }
  fs.writeFileSync(OUT, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
  ws.close()
} finally {
  electron.kill('SIGTERM')
  xvfb.kill('SIGTERM')
  await sleep(800)
  cleanup()
}
