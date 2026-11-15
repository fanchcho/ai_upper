/**
 * 预生成头像 SVG（与 Deva 同源：@humation/core + seededPalette）。
 *
 * Deva 的头像不是图片，而是渲染期用 humation 引擎按 seed/spec 现画的 SVG：
 *   - 角色：seed = persona.id，无 spec → seededPalette(seed) 配色 + 圆形底板；
 *   - 用户：固定 spec（apps/desktop/src/main/services/profile.ts 的 DEFAULT_USER_AVATAR）。
 * QML 侧没有 JS 引擎可跑 humation，所以在这里**离线**用 Deva 自己的引擎生成同款 SVG
 * 落成文件，运行时 `Image { source: avatars/<name>.svg }` 直接用。生成脚本只读 deva 的
 * node_modules，不改 deva 工程。
 *
 * 用法（需要 node 与 deva 依赖，仅生成时用，运行时不需要）:
 *   node scripts/parity/gen_avatars.mjs <deva 根目录> <输出目录>
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const devaRoot = process.argv[2]
const outDir = process.argv[3]
if (!devaRoot || !outDir) {
  console.error('用法: gen_avatars.mjs <deva 根目录> <输出目录>')
  process.exit(2)
}

const core = await import(path.join(devaRoot, 'node_modules/@humation/core/dist/index.js'))
const assets = await import(path.join(devaRoot, 'node_modules/@humation/assets-humation-1/dist/index.js'))
const { createAvatar } = core
const { humation1 } = assets

// 与 apps/desktop/src/renderer/src/components/humation.tsx 的色池逐项一致（顺序即取样次序）。
const HAIR_TONES = ['1c1c1c', '3b2a1a', '6b4226', 'a55c2b', 'd8b26a', 'b0b0b0', '7c4dff', 'e6567a']
const SKIN_TONES = ['ffe0bd', 'ffd9c0', 'f8dcb4', 'f1c27d', 'e8c19a', 'dcab7e']
const CLOTHES_TONES = ['ffffff', '2d2d2d', '4f8cff', '46c26a', 'ff8c42', 'ff5d8f', '7c7cf0', 'ffd23f']
const BG_TONES = [
  '8a38f5', '1f3a8a', '0d8ce9', '0987a0', '198e51',
  '3ad9c7', '2ec4a0', '3fb950', '3aa0ff', '5c7cfa', '9b7bf0', 'e05cd0', 'f06292', 'f2665e', 'ff8a3d', 'f5b82e',
  'a8d8ff', 'b5ead7', 'cdb4ff', 'ffb7c5', 'ffdac1', 'fff1a8'
]

function hashSeed(seed) {
  let h = 0x811c9dc5
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

function seededPalette(seed) {
  let s = hashSeed(seed) || 1
  const next = (n) => {
    s ^= s << 13; s >>>= 0
    s ^= s >>> 17
    s ^= s << 5; s >>>= 0
    return s % n
  }
  return {
    colors: {
      hair: HAIR_TONES[next(HAIR_TONES.length)],
      skin: SKIN_TONES[next(SKIN_TONES.length)],
      clothes: CLOTHES_TONES[next(CLOTHES_TONES.length)]
    },
    background: BG_TONES[next(BG_TONES.length)]
  }
}

const hex = (v) => (/^[0-9a-fA-F]{6}$/.test(v.trim()) ? `#${v.trim()}` : v.trim())
const CIRCLE = 'M50 0A50 50 0 1 1 50 100A50 50 0 1 1 50 0Z'

function mapPath(box) {
  const k = box.s / 100
  const tok = CIRCLE.match(/[MLQAZ]|-?\d*\.?\d+(?:e-?\d+)?/g)
  const r2 = (n) => Math.round(n * 100) / 100
  const X = (v) => r2(box.x + v * k)
  const Y = (v) => r2(box.y + v * k)
  let out = ''
  let i = 0
  const n = () => parseFloat(tok[i++])
  while (i < tok.length) {
    const cmd = tok[i++]
    if (cmd === 'M' || cmd === 'L') out += `${cmd}${X(n())} ${Y(n())}`
    else if (cmd === 'Q') out += `Q${X(n())} ${Y(n())} ${X(n())} ${Y(n())}`
    else if (cmd === 'A') {
      const rx = n(), ry = n(), rot = n(), large = n(), sweep = n()
      out += `A${r2(rx * k)} ${r2(ry * k)} ${rot} ${large} ${sweep} ${X(n())} ${Y(n())}`
    } else if (cmd === 'Z') out += 'Z'
  }
  return out
}

/** 与 humation.tsx 的 avatarDataUri 同口径：框内构图、圆形底板、身体+头部按形状裁切。 */
function avatarSvg(seed, spec) {
  const pal = seededPalette(seed)
  const data = createAvatar(humation1, {
    seed,
    selections: spec?.selections,
    colors: { ...pal.colors, ...(spec?.colors ?? {}) },
    background: 'transparent'
  }).toRenderData()
  let body = ''
  let head = ''
  const re = /<g data-hm-layer-slot="([^"]+)"[\s\S]*?<\/g>(?=<g data-hm-layer-slot|$)/g
  let m
  let matched = 0
  while ((m = re.exec(data.content))) {
    matched += m[0].length
    if (m[1] === 'bottom' || m[1] === 'body') body += m[0]
    else head += m[0]
  }
  if (matched !== data.content.length) {
    body = data.content
    head = ''
  }
  const box = { x: data.viewBox.x, y: data.viewBox.y, s: data.viewBox.width }
  const d = mapPath(box)
  const colors = { ...pal.colors, ...(spec?.colors ?? {}) }
  const bg = hex(spec?.background || pal.background)
  // 浏览器里 --hm-* 由外层 style 的 CSS 变量解析；Qt 的 SVG 渲染器不认 var()，
  // 所以把每个引用直接换成解析后的颜色（同一份取值，产物与浏览器绘制等价）。
  const resolveVars = (markup) =>
    markup.replace(/var\(--hm-([a-z]+)(?:,\s*([^)]*))?\)/g, (_all, slot, fallback) => {
      const v = colors[slot]
      return v ? hex(v) : (fallback || 'none').trim()
    })
  body = resolveVars(body)
  head = resolveVars(head)
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box.x} ${box.y} ${box.s} ${box.s}">` +
    `<defs><clipPath id="c"><path d="${d}"/></clipPath></defs>` +
    `<path d="${d}" fill="${bg}"/><g clip-path="url(#c)">${body}${head}</g></svg>`
  )
}

// 用户头像：Deva profile.ts 的 DEFAULT_USER_AVATAR（个人资料未配置时的固定 spec）。
const USER_SPEC = JSON.parse(
  '{"selections":{"head":"hm1-p-000004","body":"hm1-p-000028","bottom":"hm1-p-000037","item":"hm1-p-000062","glasses":"hm1-p-000058"},"colors":{"stroke":"000000","hair":"B0B0B0","skin":"FFE0BD","clothes":"2D2D2D","bottom":"000000"},"background":"0D8CE9"}'
)

// 角色头像：Deva 的默认角色在源码里带**显式 spec**（不是按 seed 现取配色），
// 逐字段抄自 deva 工程（只读）：
//   general      → apps/desktop/src/main/services/deva-personas.ts:23
//   xiaomajiang  → apps/desktop/src/main/services/xiaomajiang-personas.ts:7
const GENERAL_SPEC = JSON.parse(
  '{"selections":{"head":"hm1-p-000005","body":"hm1-p-000029","bottom":"hm1-p-000036","item":"hm1-p-000061","glasses":"hm1-p-000056"},"colors":{"stroke":"000000","hair":"e6567a","skin":"ffd9c0","clothes":"ffd23f","bottom":"000000"},"background":"8a38f5"}'
)
const XIAOMAJIANG_SPEC = JSON.parse(
  '{"selections":{"head":"hm1-p-000018","body":"hm1-p-000025","bottom":"hm1-p-000038","item":"hm1-p-000042","glasses":"hm1-p-000056"},"colors":{"stroke":"000000","hair":"000000","skin":"F7DFBB","clothes":"F20202","bottom":"000000"},"background":"3AD9C7"}'
)

const JOBS = [
  ['user.svg', 'deva-you', USER_SPEC],
  ['general.svg', 'general', GENERAL_SPEC],
  ['xiaomajiang.svg', 'xiaomajiang', XIAOMAJIANG_SPEC]
]

fs.mkdirSync(outDir, { recursive: true })
for (const [file, seed, spec] of JOBS) {
  const svg = avatarSvg(seed, spec)
  fs.writeFileSync(path.join(outDir, file), svg)
  console.log(file, 'seed=' + seed, 'bytes=' + svg.length)
}
