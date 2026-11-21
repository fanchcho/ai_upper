/**
 * 通过 CDP 从原版 Deva 的真实渲染进程里取 DOM 几何与计算样式（只读）。
 *
 * 为什么不用 CSS 推断：原版是 Chromium 排版，字号有 `calc(13.5px * var(--cs))`、
 * grid/flex 混排与 `max-width` 居中，光读 CSS 推出来的坐标会差几像素，而逐页对比
 * 要的是「QML 画在哪、原版画在哪」的实测值。这里直接问渲染进程。
 *
 * 用法: node scripts/parity/deva_dom.mjs <页面名> <输出 json>
 *   - 自己起 Xvfb + electron（与 deva_page_shot.sh 同参数、同点击脚本），
 *     electron 带 --remote-debugging-port；
 *   - 连上页面 target，按页面名执行与 deva_page_shot.sh 相同的交互（真实点击）；
 *   - 把指定的选择器集合的 getBoundingClientRect / 关键 computed style 落成 JSON。
 *
 * deva 工程只读：本脚本只启动它、往它自己的窗口里发鼠标事件，不写它的文件。
 */
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync, spawn } from 'node:child_process'

const PAGE = process.argv[2]
const OUT = process.argv[3]
const DEVA_ROOT = '/home/agent/shared_workspace/deva'
const HOME_DIR = process.env.DEVA_HOME || `/tmp/cdp-home-${PAGE}`
const CONFIG = process.env.DEVA_CONFIG || '/tmp/fx-page-home/config.json'
const FIXTURE = process.env.DEVA_SEED || '/tmp/fx-pages/data/chats'
const PORT = Number(process.env.CDP_PORT || 9333)
const W = 1280
const H = 820

if (!PAGE || !OUT) {
  console.error('用法: node deva_dom.mjs <页面名> <输出 json>')
  process.exit(2)
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function sh(cmd, args, opts = {}) {
  return execFileSync(cmd, args, { encoding: 'utf8', env: { ...process.env, DISPLAY: ':97' }, ...opts })
}

function cleanup() {
  try { sh('pkill', ['-f', 'apps/desktop/out/main/index.js']) } catch {}
  try { sh('pkill', ['-f', 'Xvfb :97']) } catch {}
  for (const f of ['/tmp/.X97-lock', '/tmp/.X11-unix/X97']) {
    try { fs.unlinkSync(f) } catch {}
  }
}

async function getJson(url) {
  const res = await fetch(url)
  return res.json()
}

async function cdp(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = cdp.next++
    const timer = setTimeout(() => reject(new Error(`${method} timeout`)), 15000)
    cdp.pending.set(id, (msg) => {
      clearTimeout(timer)
      if (msg.error) reject(new Error(`${method}: ${msg.error.message}`))
      else resolve(msg.result)
    })
    ws.send(JSON.stringify({ id, method, params }))
  })
}
cdp.next = 1
cdp.pending = new Map()

async function evaluate(ws, expression) {
  const res = await cdp(ws, 'Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
  })
  if (res.exceptionDetails) {
    throw new Error('evaluate: ' + JSON.stringify(res.exceptionDetails))
  }
  return res.result.value
}

function mouse(ws, type, x, y, button = 'left') {
  return cdp(ws, 'Input.dispatchMouseEvent', {
    type, x, y, button, clickCount: 1, buttons: type === 'mousePressed' ? 1 : 0,
  })
}

async function click(ws, x, y, wait = 800) {
  await mouse(ws, 'mouseMoved', x, y)
  await mouse(ws, 'mousePressed', x, y)
  await mouse(ws, 'mouseReleased', x, y)
  await sleep(wait)
}

async function typeText(ws, text) {
  for (const ch of text) {
    await cdp(ws, 'Input.insertText', { text: ch })
    await sleep(40)
  }
  await sleep(900)
}

async function scroll(ws, x, y, delta) {
  await cdp(ws, 'Input.dispatchMouseEvent', {
    type: 'mouseWheel', x, y, deltaX: 0, deltaY: delta,
  })
  await sleep(500)
}

// ── 页面动作（与 deva_page_shot.sh 的坐标一一对应）──────────────────────
async function act(ws, page) {
  switch (page) {
    case 'chat':
      await click(ws, 160, 90, 2000)
      break
    case 'empty':
    case 'first-run':
      break
    case 'search-open':
      await click(ws, 180, 27, 1000)
      break
    case 'search-results':
      await click(ws, 180, 27, 1000)
      await typeText(ws, '00')
      break
    case 'search-none':
      await click(ws, 180, 27, 1000)
      await typeText(ws, 'zzz')
      break
    case 'ctx-menu':
      await mouse(ws, 'mouseMoved', 160, 90)
      await mouse(ws, 'mousePressed', 160, 90, 'right')
      await mouse(ws, 'mouseReleased', 160, 90, 'right')
      await sleep(800)
      break
    case 'delete-confirm':
      await mouse(ws, 'mouseMoved', 160, 90)
      await mouse(ws, 'mousePressed', 160, 90, 'right')
      await mouse(ws, 'mouseReleased', 160, 90, 'right')
      await sleep(800)
      // 菜单实测 5 项（New chat/Rename/Select/Archive/Delete），每项 29px、从 y=96 起。
      // Delete 中心 (234, 227)。原先的 (225, 205) 落在 Archive 上——见
      // out/final-close/logs/22-menu-geometry.json 与 scripts/parity/verify_menu_geometry.mjs。
      await click(ws, 234, 227, 1200)
      break
    case 'model-picker':
      await click(ws, 160, 90, 2000)
      await click(ws, 1067, 775, 1000)
      break
    case 'hover-thread':
      await mouse(ws, 'mouseMoved', 160, 90)
      await sleep(900)
      break
    case 'focus-composer':
      await click(ws, 160, 90, 2000)
      await click(ws, 700, 700, 800)
      break
    case 'long-mid':
      await click(ws, 180, 400, 200)
      for (let i = 0; i < 12; i++) await scroll(ws, 200, 400, 100)
      break
    case 'long-bottom':
      for (let i = 0; i < 60; i++) await scroll(ws, 200, 400, 100)
      break
    case 'settings-general':
      await click(ws, 28, 787, 1500)
      break
    case 'settings-models':
      await click(ws, 28, 787, 1500)
      await click(ws, 360, 244, 1000)
      break
    case 'settings-extensions':
      await click(ws, 28, 787, 1500)
      await click(ws, 360, 277, 1000)
      break
    case 'settings-about':
      await click(ws, 28, 787, 1500)
      await click(ws, 360, 310, 1000)
      break
    case 'dark-chat':
      await click(ws, 160, 90, 2000)
      break
    default:
      throw new Error('unknown page: ' + page)
  }
  // 指针停到中立位置，避免 :hover 混进测量。
  await mouse(ws, 'mouseMoved', 200, 700)
  await sleep(400)
}

// ── 测量表达式 ──────────────────────────────────────────────────────────
const MEASURE = String.raw`
(() => {
  const out = { viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio } }
  const round = (n) => Math.round(n * 100) / 100
  const rect = (el) => {
    const r = el.getBoundingClientRect()
    return { x: round(r.x), y: round(r.y), w: round(r.width), h: round(r.height) }
  }
  const cs = (el) => getComputedStyle(el)
  const styleOf = (el, props) => {
    const s = cs(el)
    const o = {}
    for (const p of props) o[p] = s.getPropertyValue(p)
    return o
  }
  const TEXT_PROPS = ['font-family','font-size','font-weight','line-height','color',
    'background-color','border-radius','padding','border-width','border-color',
    'letter-spacing','text-align','box-shadow','opacity','gap','display']
  const one = (sel, props = TEXT_PROPS) => {
    const el = document.querySelector(sel)
    if (!el) return null
    return { sel, rect: rect(el), style: styleOf(el, props), text: (el.innerText || '').slice(0, 120) }
  }
  const many = (sel, props = TEXT_PROPS) => Array.from(document.querySelectorAll(sel)).map((el) => ({
    rect: rect(el), style: styleOf(el, props), text: (el.innerText || '').slice(0, 200)
  }))
  out.rootTheme = document.documentElement.dataset.theme || '(none)'
  out.rootChatFs = document.documentElement.dataset.chatFs || '(none)'
  out.fontSans = cs(document.documentElement).getPropertyValue('--font-sans')
  // 每条会话行的内部结构（grid 列宽/头像框/标题块），逐层列出 class 与 rect。
  out.threadTree = Array.from(document.querySelectorAll('.cf-thread')).slice(0, 3).map((row) => {
    const walk = (el, depth) => {
      const r = rect(el)
      const own = Array.from(el.childNodes)
        .filter((n) => n.nodeType === 3)
        .map((n) => n.textContent.trim())
        .filter(Boolean)
        .join(' ')
      const node = {
        tag: el.tagName.toLowerCase(),
        cls: typeof el.className === 'string' ? el.className : '',
        rect: r,
        style: styleOf(el, ['display','grid-template-columns','gap','padding','font-size',
          'font-weight','color','background-color','border-radius','width','height',
          'overflow','text-overflow','white-space','line-height','align-items']),
      }
      if (own) node.ownText = own.slice(0, 80)
      const kids = Array.from(el.children)
      if (kids.length) node.children = kids.map((k) => walk(k, depth + 1))
      return node
    }
    return walk(row, 0)
  })
  // 图标栏各按钮的结构与几何
  out.railTree = (() => {
    const railEl = document.querySelector('.cf-iconrail')
    if (!railEl) return null
    return Array.from(railEl.children).map((el) => ({
      tag: el.tagName.toLowerCase(),
      cls: typeof el.className === 'string' ? el.className : '',
      rect: rect(el),
      style: styleOf(el, ['display','padding','gap','position','width','height',
        'background-color','border-radius','color','overflow']),
      kidCount: el.children.length,
      html: el.outerHTML.slice(0, 400),
    }))
  })()
  // 中栏头部（conv head）结构
  out.headTree = (() => {
    const el = document.querySelector('.cf-conv__head')
    if (!el) return null
    return Array.from(el.children).map((k) => ({
      tag: k.tagName.toLowerCase(),
      cls: typeof k.className === 'string' ? k.className : '',
      rect: rect(k),
      text: (k.innerText || '').slice(0, 80),
      html: k.outerHTML.slice(0, 500),
      style: styleOf(k, ['display','gap','padding','font-size','font-weight','color',
        'background-color','border-radius','border-width','align-items']),
    }))
  })()
  // 中栏结构（到 3 层）：空状态 / 引导页的元素名没有先验 class，靠这棵树上取实测 rect。
  out.convTree = (() => {
    const rootEl = document.querySelector('.cf-conv')
    if (!rootEl) return null
    const walk = (el, depth) => {
      const node = {
        tag: el.tagName.toLowerCase(),
        cls: typeof el.className === 'string' ? el.className : '',
        rect: rect(el),
        text: (el.children.length ? '' : (el.textContent || '').trim()).slice(0, 100),
        style: styleOf(el, ['display','padding','gap','font-size','font-weight','color',
          'background-color','border-radius','border-width','border-color','max-width',
          'margin','align-items','justify-content','text-align','line-height','opacity']),
      }
      if (depth < 3 && el.children.length) {
        node.children = Array.from(el.children).slice(0, 12).map((k) => walk(k, depth + 1))
      }
      return node
    }
    return walk(rootEl, 0)
  })()
  // 页面上所有文本节点的 rect（用 Range 量），用于定位「某段文案画在哪」。
  out.textRects = (() => {
    const out2 = []
    const walker = document.createTreeWalker(document.querySelector('.cf-conv') || document.body, NodeFilter.SHOW_TEXT)
    let n
    while ((n = walker.nextNode()) && out2.length < 80) {
      const t = (n.textContent || '').trim()
      if (!t) continue
      const r = document.createRange()
      r.selectNodeContents(n)
      const b = r.getBoundingClientRect()
      if (b.width < 1 || b.height < 1) continue
      const parent = n.parentElement
      out2.push({
        text: t.slice(0, 80),
        rect: { x: round(b.x), y: round(b.y), w: round(b.width), h: round(b.height) },
        parentCls: parent ? String(parent.className).slice(0, 80) : '',
        font: parent ? styleOf(parent, ['font-size','font-weight','color','line-height','text-align']) : null,
      })
    }
    return out2
  })()
  // 浮层内部结构（设置弹窗 / 搜索浮层 / 右键菜单）：无先验 class 时靠这棵树取实测值。
  const treeOf = (sel, maxDepth = 6, maxKids = 16) => {
    const rootEl = document.querySelector(sel)
    if (!rootEl) return null
    const walk = (el, depth) => {
      const node = {
        tag: el.tagName.toLowerCase(),
        cls: typeof el.className === 'string' ? el.className : '',
        rect: rect(el),
        text: (el.children.length ? '' : (el.textContent || '').trim()).slice(0, 80),
        style: styleOf(el, ['display','grid-template-columns','padding','gap','font-size',
          'font-weight','color','background-color','border-radius','border-width',
          'border-color','margin','align-items','justify-content','text-align',
          'line-height','width','height','box-shadow','opacity','flex-direction']),
      }
      if (depth < maxDepth && el.children.length) {
        node.children = Array.from(el.children).slice(0, maxKids).map((k) => walk(k, depth + 1))
      }
      return node
    }
    return walk(rootEl, 0)
  }
  out.modalTree = treeOf('.cf-modal')
  out.searchTree = treeOf('.cf-search-pop, .cf-searchwrap, .cf-search', 4)
  out.ctxTree = treeOf('.cf-ctx')
  // 所有带背景色的可见盒子（浮层里的分组卡片/按钮靠这条清单，避免漏掉无 class 的块）
  out.boxes = Array.from(document.querySelectorAll('.cf-modal *, .cf-search-pop *, .cf-ctx *'))
    .slice(0, 120)
    .map((el) => {
      const r = rect(el)
      const s = cs(el)
      return { tag: el.tagName.toLowerCase(), cls: String(el.className).slice(0, 60), rect: r,
        bg: s.backgroundColor, br: s.borderRadius, bw: s.borderTopWidth, bc: s.borderTopColor,
        fs: s.fontSize, fw: s.fontWeight, col: s.color,
        text: (el.children.length ? '' : (el.textContent || '').trim()).slice(0, 50) }
    })
    .filter((b) => b.rect.w > 0 && b.rect.h > 0)
  // 正文细节：代码块头/表格单元格/列表/引用/行内元素的逐项样式（这些在 CSS 里是嵌套规则，
  // 直接读规则容易漏掉 padding 与 border 的实际取值）。
  const DETAIL_GROUPS = {
    md: ['.md-code', '.md-code__head', '.md-code__head *', '.md-code__body', '.md-code__body *',
      '.md table', '.md table thead', '.md table tr', '.md table th', '.md table td',
      '.md li', '.md ol > li', '.md ul > li', '.md li p', '.md li input[type=checkbox]',
      '.md blockquote', '.md blockquote p', '.md blockquote blockquote',
      '.md a', '.md strong', '.md em', '.md code', '.md img', '.md hr'],
    msg: ['.cf-msg__name', '.cf-msg__time', '.cf-msg__text'],
    modal: ['.cf-modal__head', '.cf-modal__close', '.cf-nav', '.cf-nav__item', '.cf-nav__icon',
      '.cf-pane', '.cf-pane__title', '.cf-set', '.cf-set__row', '.cf-set__label',
      '.cf-seg', '.cf-seg__opt'],
    overlay: ['.cf-ctx', '.cf-ctx__item', '.cf-search-pop', '.cf-search__filter'],
  }
  out.detail = []
  for (const [group, sels] of Object.entries(DETAIL_GROUPS)) {
    const seen = new Set()
    for (const sel of sels) {
      for (const el of Array.from(document.querySelectorAll(sel))) {
        if (seen.has(el)) continue
        seen.add(el)
        out.detail.push({
          group, sel,
          tag: el.tagName.toLowerCase(),
          cls: typeof el.className === 'string' ? el.className : '',
          rect: rect(el),
          text: (el.children.length ? '' : (el.textContent || '').trim()).slice(0, 60),
          style: styleOf(el, ['display','padding','margin','font-size','font-weight','line-height',
            'color','background-color','border-top','border-bottom','border-left','border-right',
            'border-radius','border-collapse','border-spacing','text-align','white-space',
            'overflow-x','overflow-y','letter-spacing','vertical-align','opacity','width','max-width']),
          attrs: el.getAttribute('href') || el.getAttribute('src') || el.getAttribute('title') || undefined,
        })
      }
    }
  }
  // 输入区工具栏的每个按钮
  out.composerTree = Array.from(document.querySelectorAll('.cf-composer *')).slice(0, 60).map((el) => ({
    tag: el.tagName.toLowerCase(),
    cls: typeof el.className === 'string' ? el.className : '',
    rect: rect(el),
    text: (el.innerText || el.getAttribute('placeholder') || '').slice(0, 60),
    style: styleOf(el, ['display','gap','padding','font-size','font-weight','color',
      'background-color','border-radius','border-width','border-color','width','height']),
    html: el.children.length === 0 ? el.outerHTML.slice(0, 300) : undefined,
  }))
  // 消息区：每条消息行的 grid 与子块
  out.msgTree = Array.from(document.querySelectorAll('.cf-msg')).map((el) => ({
    cls: typeof el.className === 'string' ? el.className : '',
    rect: rect(el),
    style: styleOf(el, ['display','grid-template-columns','gap','padding','margin']),
    children: Array.from(el.children).map((k) => ({
      tag: k.tagName.toLowerCase(),
      cls: typeof k.className === 'string' ? k.className : '',
      rect: rect(k),
      text: (k.innerText || '').slice(0, 60),
      style: styleOf(k, ['display','padding','margin','font-size','font-weight',
        'background-color','border-radius','color','white-space']),
    })),
  }))
  // .md 顶层块逐项（含 margin/height），用于对齐正文节奏
  out.mdTop = Array.from(document.querySelectorAll('.md > *')).map((el) => ({
    tag: el.tagName.toLowerCase(),
    cls: typeof el.className === 'string' ? el.className : '',
    rect: rect(el),
    text: (el.innerText || '').slice(0, 60),
    style: styleOf(el, ['margin-top','margin-bottom','padding','font-size','font-weight',
      'color','background-color','border-radius','border-width','border-color','line-height','white-space']),
  }))
  // 图标栏/侧栏底色的实际绘制值
  out.painted = {}
  for (const [k, sel] of Object.entries({
    iconrail: '.cf-iconrail', rail: '.cf-rail', conv: '.cf-conv',
    railTop: '.cf-rail__top', search: '.cf-search', box: '.cf-box',
  })) {
    const el = document.querySelector(sel)
    if (el) out.painted[k] = { bg: cs(el).backgroundColor, borderRight: cs(el).borderRightColor,
      borderRightWidth: cs(el).borderRightWidth, borderBottom: cs(el).borderBottomColor }
  }
  out.named = {}
  const NAMED = {
    shell: '.cf-shell', body: '.cf-body', iconrail: '.cf-iconrail',
    me: '.cf-iconrail__me', navActive: '.cf-navbtn.is-active',
    navAll: '.cf-iconrail .cf-navbtn',
    rail: '.cf-rail', railTop: '.cf-rail__top', search: '.cf-search',
    searchInput: '.cf-search__input', addBtn: '.cf-rail__addbtn',
    list: '.cf-list', thread: '.cf-thread', threadActive: '.cf-thread.is-active',
    threadFace: '.cf-thread__face', threadTitle: '.cf-thread__title, .cf-thread__name',
    conv: '.cf-conv', head: '.cf-conv__head', idbtn: '.cf-idbtn',
    idname: '.cf-idbtn__name', msgs: '.cf-msgs', msgsInner: '.cf-msgs__inner',
    msg: '.cf-msg', msgName: '.cf-msg__name', msgText: '.cf-msg__text',
    md: '.md', mdP: '.md p', mdH2: '.md h2', mdTable: '.md table',
    mdCode: '.md-code', mdCodeBody: '.md-code__body, .md-code pre',
    mdCodeHead: '.md-code__head', mdQuote: '.md blockquote', mdHr: '.md hr',
    mdUl: '.md ul', mdOl: '.md ol', mdTask: '.md li.is-task, .md input[type=checkbox]',
    composer: '.cf-composer', composerInner: '.cf-composer__inner',
    box: '.cf-box', draft: '.cf-draft', send: '.cf-send',
    toolbar: '.cf-composer__bar, .cf-box__bar', modelPickerTrigger: '.cf-effort, .cf-model',
    statusDot: '.cf-composer__dot, .cf-status__dot',
    empty: '.cf-empty', quickstart: '.cf-quickstart, .cf-start',
    ctx: '.cf-ctx', ctxItem: '.cf-ctx__item',
    modalBackdrop: '.cf-modal__backdrop', modal: '.cf-modal',
    modalHead: '.cf-modal__head', modalTitle: '.cf-modal__title',
    modalNav: '.cf-modal__nav', modalNavActive: '.cf-modal__nav .is-active',
    modalBody: '.cf-modal__body', modalPanel: '.cf-modal__panel',
    settingsRow: '.cf-setrow, .cf-settings__row', seg: '.cf-seg, .cf-segmented',
    segItem: '.cf-seg button, .cf-segmented button',
    switch: '.cf-switch', picker: '.cf-picker, .cf-menu',
    about: '.cf-about', aboutIcon: '.cf-about__icon', aboutName: '.cf-about__name',
    aboutVer: '.cf-about__ver', updateBtn: '.cf-update button, .cf-update__btn',
    tag: '.cf-thread__time, .cf-thread__meta', scrollbar: '.cf-list__scroll',
  }
  for (const [k, sel] of Object.entries(NAMED)) out.named[k] = one(sel)
  // 全部会话行（前 20 行）与它们的标题/时间/预览段
  out.threads = many('.cf-thread').slice(0, 20)
  out.threadParts = many('.cf-thread > *').slice(0, 40)
  // 消息区逐条：外框 + 内部文本块
  out.messages = many('.cf-msg')
  out.mdBlocks = many('.md > *').slice(0, 40)
  out.mdAll = many('.md *').length
  // 中列正文滚动信息
  const sc = document.querySelector('.cf-msgs')
  if (sc) out.scroll = { scrollTop: sc.scrollTop, scrollHeight: sc.scrollHeight, clientHeight: sc.clientHeight }
  const list = document.querySelector('.cf-list')
  if (list) out.listScroll = { scrollTop: list.scrollTop, scrollHeight: list.scrollHeight, clientHeight: list.clientHeight }
  // 文本清单（逐页文案对齐用）
  out.texts = {}
  for (const k of ['search','empty','composer','ctx','modal','thread','messages','buttons','labels']) out.texts[k] = null
  const grab = (sel) => Array.from(document.querySelectorAll(sel)).map((e) => (e.innerText || e.value || e.placeholder || '').trim()).filter(Boolean).slice(0, 60)
  out.texts.search = grab('.cf-search input, .cf-search__input')
  out.texts.placeholders = Array.from(document.querySelectorAll('input,textarea,[contenteditable]')).map((e) => e.getAttribute('placeholder') || e.getAttribute('data-placeholder') || '').filter(Boolean).slice(0, 20)
  out.texts.buttons = grab('button')
  out.texts.labels = Array.from(document.querySelectorAll('.cf-rail, .cf-composer, .cf-modal')).map((e) => (e.innerText||'').trim().slice(0,1200))
  out.texts.empty = grab('.cf-empty')
  out.texts.ctx = grab('.cf-ctx__item')
  out.texts.modal = grab('.cf-modal')
  out.texts.thread = grab('.cf-thread')
  out.texts.messages = grab('.cf-msgs')
  // hover/focus 状态标记
  out.active = document.activeElement ? {
    tag: document.activeElement.tagName,
    cls: document.activeElement.className,
  } : null
  out.hovered = (() => {
    const h = document.querySelectorAll(':hover')
    const last = h[h.length - 1]
    return last ? { tag: last.tagName, cls: String(last.className).slice(0, 120) } : null
  })()
  return out
})()
`

async function main() {
  cleanup()
  fs.rmSync(HOME_DIR, { recursive: true, force: true })
  fs.mkdirSync(HOME_DIR, { recursive: true })
  if (FIXTURE && fs.existsSync(FIXTURE) && PAGE !== 'empty' && PAGE !== 'first-run') {
    fs.mkdirSync(path.join(HOME_DIR, 'data/chats'), { recursive: true })
    sh('cp', ['-a', FIXTURE + '/.', path.join(HOME_DIR, 'data/chats')])
  }
  if (CONFIG && fs.existsSync(CONFIG)) fs.copyFileSync(CONFIG, path.join(HOME_DIR, 'config.json'))
  else fs.writeFileSync(path.join(HOME_DIR, 'config.json'), '{"locale":"en","theme":"light"}\n')

  const xvfb = spawn('Xvfb', [':97', '-screen', '0', '1400x900x24'], {
    stdio: 'ignore', detached: true,
  })
  await sleep(1500)
  const profile = `/tmp/electron-profile-cdp-${PAGE}`
  fs.rmSync(profile, { recursive: true, force: true })
  const electron = spawn(
    path.join(DEVA_ROOT, 'node_modules/electron/dist/electron'),
    ['--no-sandbox', '--disable-gpu', `--remote-debugging-port=${PORT}`,
     `--user-data-dir=${profile}`, path.join(DEVA_ROOT, 'apps/desktop/out/main/index.js')],
    { env: { ...process.env, DISPLAY: ':97', DEVA_HOME: HOME_DIR }, stdio: 'ignore', detached: true },
  )
  try {
    await sleep(7000)
    // 窗口摆到 0,0 并调成 1280x820（与截图脚本同一几何）。
    let wid = ''
    try { wid = sh('xdotool', ['search', '--name', '^Deva$']).split('\n')[0] } catch {}
    if (!wid) {
      try { wid = sh('xdotool', ['search', '--class', 'electron']).split('\n')[0] } catch {}
    }
    if (wid) {
      sh('xdotool', ['windowmove', wid, '0', '0'])
      sh('xdotool', ['windowsize', wid, '1280', '820'])
      try { sh('xdotool', ['windowactivate', wid]) } catch {}
      await sleep(1200)
    } else {
      console.error('未找到窗口')
    }

    // CDP：找到渲染页面 target
    let targets = []
    for (let i = 0; i < 30; i++) {
      try {
        targets = await getJson(`http://127.0.0.1:${PORT}/json`)
        if (targets.some((t) => t.type === 'page')) break
      } catch {}
      await sleep(500)
    }
    const page = targets.find((t) => t.type === 'page' && t.webSocketDebuggerUrl)
    if (!page) throw new Error('没有可连的页面 target: ' + JSON.stringify(targets.map((t) => t.type)))
    const ws = new WebSocket(page.webSocketDebuggerUrl)
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej })
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && cdp.pending.has(msg.id)) {
        const cb = cdp.pending.get(msg.id)
        cdp.pending.delete(msg.id)
        cb(msg)
      }
    }
    await cdp(ws, 'Runtime.enable')
    await cdp(ws, 'Page.enable')
    await sleep(1500)
    await act(ws, PAGE)
    const result = await evaluate(ws, MEASURE)
    fs.mkdirSync(path.dirname(OUT), { recursive: true })
    fs.writeFileSync(OUT, JSON.stringify(result, null, 2))
    console.log('dom', PAGE, '->', OUT, 'threads=' + result.threads.length,
      'messages=' + result.messages.length)
    ws.close()
  } finally {
    try { process.kill(-electron.pid, 'SIGKILL') } catch {}
    try { process.kill(-xvfb.pid, 'SIGKILL') } catch {}
    cleanup()
  }
}

main().catch((err) => {
  console.error('FAILED', err && err.stack || err)
  cleanup()
  process.exit(1)
})
