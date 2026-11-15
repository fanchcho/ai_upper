// 设计 token 的单一声明处：数值取自原版 tokens.css（见 docs/audit/qml-shell-audit.md §5.1）。
// 本文件是 QML 单例——界面里任何颜色/尺寸都不写死，只引用这里的名字。
pragma Singleton
import QtQuick

QtObject {
    // ── 浅色调色板 ────────────────────────────────────────────────
    readonly property color bg: "#ffffff"
    readonly property color bgPanel: "#f7f7f8"
    readonly property color bgInset: "#f0f0f2"
    readonly property color bgSelected: "#e9e9fb"
    readonly property color fg: "#1f1f24"
    readonly property color fgMuted: "#5c5c66"
    readonly property color fgSubtle: "#8a8a94"
    readonly property color border: "#e6e6ea"
    readonly property color borderStrong: "#d5d5db"
    readonly property color accent: "#5b5bd6"

    // ── 度量 ──────────────────────────────────────────────────────
    readonly property int sidebarWidth: 264
    readonly property int titlebarHeight: 40
    readonly property int radius: 8
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 20

    // ── 字体 ──────────────────────────────────────────────────────
    // 系统字体栈里没有 -apple-system/Segoe UI，Linux 实测落到 Noto Sans CJK SC；
    // 显式列出 CJK 家族，避免 Qt 把 sans-serif 匹配到 DejaVu（缺中文字形）。
    readonly property string sansFamily: "Noto Sans CJK SC"
    readonly property string monoFamily: "DejaVu Sans Mono"
    readonly property int bodyPx: 14
}
