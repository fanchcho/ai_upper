/**
 * 从 deva 的 lucide-react（只读）抽出图标路径，生成 QML 可直接用的 IconData.qml。
 *
 * 为什么抄路径而不是引入图标字体：QML 侧没有 lucide 字体文件，而 lucide 的图标就是
 * 24×24 viewBox 的 stroke 路径。用 Shape + PathSvg 逐条画，坐标与原版 SVG 完全一致
 * （同一份 `d`），线宽/端点也能逐项配上 `stroke-width:2 / round`。
 *
 * 用法: node scripts/parity/gen_icons.mjs <deva 根目录> <输出 qml 文件>
 */
import fs from 'node:fs'
import path from 'node:path'

const devaRoot = process.argv[2]
const outFile = process.argv[3]
if (!devaRoot || !outFile) {
  console.error('用法: gen_icons.mjs <deva 根目录> <输出 qml 文件>')
  process.exit(2)
}

const ICONS_DIR = path.join(devaRoot, 'node_modules/lucide-react/dist/esm/icons')

// QML 里用到哪些图标：与 deva ChatFirstShell 的图标栏/输入区/设置页一一对应。
const WANTED = [
  'message-circle', 'users', 'alarm-clock', 'bot', 'cog', 'brain', 'puzzle',
  'search', 'plus', 'paperclip', 'folder', 'chevron-down', 'arrow-up',
  'copy', 'x', 'settings-2', 'blocks', 'info', 'sparkles', 'square-pen', 'check',
  'panel-left', 'panel-right', 'trash-2', 'pencil', 'archive',
  // 会话右键菜单的「Select」项（Rail.tsx 用 lucide ListChecks）。
  'list-checks',
  // 交付卡「打开」按钮：原版 DeliverablesCard 用的就是 lucide 的 external-link。
  'external-link',
  // 侧栏搜索：原版 Rail 的筛选按钮是 list-filter，清空按钮是 x（上面已有）。
  'list-filter', 'folder-minus',
  // 输入区思考等级 chip：原版 EffortPicker 用的是 lightbulb（不是 sparkles）。
  'lightbulb',
  // 设置页：面板行的右侧箭头与模型行上的告警三角。
  'chevron-right', 'chevron-left', 'alert-triangle',
  // 服务商详情页的「高级设置」入口（自定义请求头）与关于页的「检查更新」。
  'wrench', 'refresh-cw'
]

const ELEMENT_RE = /\[\s*"(path|circle|rect|line|polyline|polygon)"\s*,\s*\{([^}]*)\}/g

function parseAttrs(src) {
  const out = {}
  const re = /(\w+)\s*:\s*"([^"]*)"/g
  let m
  while ((m = re.exec(src))) out[m[1]] = m[2]
  return out
}

function toSvgData(tag, a) {
  const n = (k, d = 0) => Number(a[k] !== undefined ? a[k] : d)
  switch (tag) {
    case 'path':
      return a.d || ''
    case 'circle': {
      const cx = n('cx'), cy = n('cy'), r = n('r')
      return `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z`
    }
    case 'rect': {
      const x = n('x'), y = n('y'), w = n('width'), h = n('height')
      const rx = a.rx !== undefined ? Number(a.rx) : (a.ry !== undefined ? Number(a.ry) : 0)
      if (!rx) return `M${x} ${y}H${x + w}V${y + h}H${x}Z`
      return (
        `M${x + rx} ${y}H${x + w - rx}A${rx} ${rx} 0 0 1 ${x + w} ${y + rx}` +
        `V${y + h - rx}A${rx} ${rx} 0 0 1 ${x + w - rx} ${y + h}` +
        `H${x + rx}A${rx} ${rx} 0 0 1 ${x} ${y + h - rx}` +
        `V${y + rx}A${rx} ${rx} 0 0 1 ${x + rx} ${y}Z`
      )
    }
    case 'line':
      return `M${n('x1')} ${n('y1')}L${n('x2')} ${n('y2')}`
    case 'polyline':
    case 'polygon': {
      const pts = (a.points || '').trim().split(/\s+/).map((p) => p.split(','))
      const d = pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px} ${py}`).join('')
      return tag === 'polygon' ? d + 'Z' : d
    }
    default:
      return ''
  }
}

const entries = []
for (const name of WANTED) {
  const file = path.join(ICONS_DIR, name + '.js')
  if (!fs.existsSync(file)) continue
  let src = fs.readFileSync(file, 'utf8')
  // lucide 有若干「改名保留旧名」的文件，内容只是一行 re-export（如 alert-triangle.js
  // 就是 `export { default } from './triangle-alert.js'`）。这类文件里没有任何 path 元素，
  // 直接解析会得到空图标，所以要顺着 re-export 指到真正的实现文件。
  const reexport = /export\s*\{\s*default\s*\}\s*from\s*'\.\/([\w-]+)\.js'/.exec(src)
  if (reexport) {
    src = fs.readFileSync(path.join(ICONS_DIR, reexport[1] + '.js'), 'utf8')
  }
  const paths = []
  let m
  ELEMENT_RE.lastIndex = 0
  while ((m = ELEMENT_RE.exec(src))) {
    const d = toSvgData(m[1], parseAttrs(m[2]))
    if (d) paths.push(d)
  }
  const camel = name.replace(/-([a-z0-9])/g, (_, c) => c.toUpperCase())
  entries.push({ name: camel, svg: name, paths })
}

// QML 字符串里不能直接写反斜杠/引号；路径本身只有数字与命令字母，安全，但统一转义一次。
const qmlEscape = (s) => s.replace(/\\/g, '\\\\').replace(/"/g, '\\"')

const lines = []
lines.push('// 由 scripts/parity/gen_icons.mjs 从 deva 的 lucide-react（只读）生成，勿手改。')
lines.push('// 上游: node_modules/lucide-react/dist/esm/icons/<name>.js，viewBox 24x24，')
lines.push('// 默认 stroke-width=2、stroke-linecap=round、stroke-linejoin=round（lucide 规格）。')
lines.push('pragma Singleton')
lines.push('import QtQuick')
lines.push('')
lines.push('QtObject {')
for (const e of entries) {
  const data = e.paths.map(qmlEscape).join('|')
  lines.push(`    // ${e.svg}`)
  lines.push(`    readonly property string ${e.name}: "${data}"`)
}
lines.push('')
lines.push('    function get(key) {')
for (const e of entries) lines.push(`        if (key === "${e.name}") return ${e.name}`)
lines.push('        return ""')
lines.push('    }')
lines.push('}')
lines.push('')

fs.writeFileSync(outFile, lines.join('\n'))
console.log('icons ->', outFile, 'count=' + entries.length,
  'names=' + entries.map((e) => e.name).join(','))
