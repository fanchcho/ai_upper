// 设计 token 的单一声明处：数值逐项取自原版 tokens.css（见 docs/audit/qml-shell-audit.md §5.1）。
// 本文件是 QML 单例——界面里任何颜色/尺寸都不写死，只引用这里的名字。
// 深浅两套语义色同源：dark 覆盖项与 tokens.css `:root[data-theme='dark']` 一一对应。
pragma Singleton
import QtQuick

QtObject {
    id: theme

    // 深浅由 Python 按 config.json 的 theme 写进来（system 时按系统配色解析完再写）。
    property bool dark: false

    // ── 语义色（浅色）────────────────────────────────────────────
    readonly property color _bgLight: "#ffffff"
    readonly property color _bgPanelLight: "#f7f7f8"
    readonly property color _bgInsetLight: "#f0f0f2"
    // tokens.css `--bg-elevated`（浅色 43 行 / 深色 111 行）：抬升面（如 Models 页加号按钮底）。
    readonly property color _bgElevatedLight: "#ffffff"
    readonly property color _bgHoverLight: Qt.rgba(0, 0, 0, 0.045)
    readonly property color _bgActiveLight: Qt.rgba(0, 0, 0, 0.08)
    readonly property color _bgSelectedLight: Qt.rgba(91 / 255, 91 / 255, 214 / 255, 0.12)
    readonly property color _fgLight: "#1f1f24"
    readonly property color _fgMutedLight: "#5c5c66"
    readonly property color _fgSubtleLight: "#8a8a94"
    readonly property color _borderLight: "#e6e6ea"
    readonly property color _borderStrongLight: "#d5d5db"
    readonly property color _accentLight: "#5b5bd6"
    readonly property color _bubbleLight: "#edeffb"

    // ── 语义色（深色）────────────────────────────────────────────
    readonly property color _bgDark: "#1e1e20"
    readonly property color _bgPanelDark: "#252528"
    readonly property color _bgInsetDark: "#191919"
    readonly property color _bgElevatedDark: "#2a2a2e"
    readonly property color _bgHoverDark: Qt.rgba(1, 1, 1, 0.06)
    readonly property color _bgActiveDark: Qt.rgba(1, 1, 1, 0.10)
    readonly property color _bgSelectedDark: Qt.rgba(124 / 255, 124 / 255, 240 / 255, 0.20)
    readonly property color _fgDark: "#e4e4e7"
    readonly property color _fgMutedDark: "#a1a1aa"
    readonly property color _fgSubtleDark: "#71717a"
    readonly property color _borderDark: "#2f2f33"
    readonly property color _borderStrongDark: "#3d3d42"
    readonly property color _accentDark: "#7c7cf0"
    readonly property color _bubbleDark: "#303043"

    readonly property color bg: dark ? _bgDark : _bgLight
    readonly property color bgPanel: dark ? _bgPanelDark : _bgPanelLight
    readonly property color bgInset: dark ? _bgInsetDark : _bgInsetLight
    readonly property color bgElevated: dark ? _bgElevatedDark : _bgElevatedLight
    readonly property color bgHover: dark ? _bgHoverDark : _bgHoverLight
    readonly property color bgActive: dark ? _bgActiveDark : _bgActiveLight
    readonly property color bgSelected: dark ? _bgSelectedDark : _bgSelectedLight
    readonly property color fg: dark ? _fgDark : _fgLight
    readonly property color fgMuted: dark ? _fgMutedDark : _fgMutedLight
    readonly property color fgSubtle: dark ? _fgSubtleDark : _fgSubtleLight
    readonly property color border: dark ? _borderDark : _borderLight
    readonly property color borderStrong: dark ? _borderStrongDark : _borderStrongLight
    readonly property color accent: dark ? _accentDark : _accentLight
    readonly property color accentFg: dark ? "#14141a" : "#ffffff"
    readonly property color chatUserBubble: dark ? _bubbleDark : _bubbleLight
    readonly property color danger: dark ? "#ff6b6b" : "#e5484d"
    // 状态色：tokens.css `--success` / `--warning`（浅色 64–65 行，深色 132–133 行）。
    // 设置页服务商启用点用 success，缺密钥警告三角用 warning。
    readonly property color success: dark ? "#51cf66" : "#2f9e44"
    readonly property color warning: dark ? "#fcc419" : "#d9860b"
    // 滚动条：app.css `::-webkit-scrollbar` width 8px；thumb 常态 `--scrollbar`、
    // hover `--fg-subtle`；`border: 2px solid transparent` + `background-clip: content-box`
    // 等价于控制宽 8 + 内缩 2，真正可见的滑块宽 4px；轨道未写规则 → 透明。
    readonly property color scrollbar: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0, 0, 0, 0.18)
    readonly property color scrollbarHover: fgSubtle
    readonly property int scrollbarWidth: 8
    readonly property int scrollbarInset: 2
    readonly property color shadow: Qt.rgba(0, 0, 0, dark ? 0.50 : 0.12)
    readonly property color backdrop: Qt.rgba(0, 0, 0, 0.42)
    // 输入区模型 chip 前的状态点：原版实测 #d97757（浅色/深色同值）。
    readonly property color statusDot: "#d97757"

    // ── 度量（tokens.css + redesign.css）────────────────────────
    readonly property int railWidth: 56
    readonly property int sideWidth: 300
    readonly property int mainWidth: 780
    readonly property int titlebarHeight: 40
    readonly property int controlHeight: 34
    readonly property int radiusSm: 6
    readonly property int radius: 8
    readonly property int radiusLg: 12
    readonly property int radiusFull: 999
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 20
    readonly property int space6: 24

    // ── 字体 ─────────────────────────────────────────────────────
    // 原版 `--font-sans` 首选 -apple-system/Segoe UI/Microsoft YaHei/Roboto/Helvetica/Arial；
    // 这台机器上 Chromium 把 Arial/Segoe UI/Roboto 都回退到 DejaVu Sans（fc-match 实测），
    // CJK 落到 Noto Sans CJK。QML 的 Font 只有一个 family 名，不能给「按字符集分家族」的栈，
    // 故显式选 DejaVu Sans + 由 fontconfig 回退到 Noto Sans CJK。
    //
    // 为什么不选 Nimbus Sans：它没有 500/600 两个字重，Qt 会把 Medium→Italic、DemiBold→
    // Bold Italic（`QFontInfo.styleName()` 实测），设置页整页文字会变斜体；且正文度量比原版
    // 窄 4–21px（"list_dir" 39.28 vs 60.22）。DejaVu Sans 对同一批判定宽度与原版 CSS 相差
    // ≤0.15px（"DeepSeek V4.1 Flash" 127.19 vs 127.33、"Send" 36.72 vs 36.75）。
    readonly property string sansFamily: "DejaVu Sans"
    readonly property string monoFamily: "DejaVu Sans Mono"
    readonly property real bodyPx: 14 * chatScale
    readonly property real chatScale: 1.0
}
