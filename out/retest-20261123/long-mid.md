# long-mid：会话、行索引和悬停状态三项不一致

结论：仍存在，未修复；整页差异 **142444 → 142444 px**，不能全归为 Markdown 渲染错误。

1. deva 脚本先 `click 180 400` 再滚轮，点击选中了第 6 个会话；参考图正文明确是“这是第 6 条会话的回复正文”。QML 运行时仍是 **active=parity-000 → parity-000**，绘制完整表格/列表会话。两端正文根本不是同一数据状态。
2. QML 的 `sessionList.contentY=1386 → 1386`，截图第一个完整标题为“会话 026”，deva 是“会话 027”。QML 源码旁的“index 26 对应会话 027”注释与夹具编号不符。剩余的滚动问题既有行身份偏一，也需要同步同一会话顺序；不能仅看相同 y 坐标称一致。
3. `forceHoverRow=11 → 11` 在长列表中已滚出屏幕。QML 精确悬停色行数 **0 → 0**，deva **54** 行 y668–721。“会话 038”行在参考图被悬停；QML 硬绑第 11 行导致此带缺失。

因此需要后续把 QML 页面驱动与 deva 的点击/滚动/鼠标动作链统一，再重新建立可比较截图。当前报告不改参考图、不把状态不一致算成正文引擎回归。辅助 long-bottom 已重拍：差异 **124452 → 124452 px**。

证据：`logs/runtime-long-mid.json`、`qml/long-mid.png`、`out/latest-parity/deva/long-mid-deva.png`、`scripts/parity/deva_page_shot.sh` 的 long-mid 分支、`Main.qml::applyListScroll`。

基线 `c660bf887aea5eb4e3e9c68f8c6833c95294bbb7`。本轮为归因复核，未改产品代码或测试；“前 → 后”指基线截图重新读数 → 当前代码重拍复验，并非声称有修复收益。九页新截图与原已跟踪 QML 图 MD5 一致，见 `logs/compare-normalized.log`。deva 使用仓库内已跟踪参考图，本轮未重新启动工作区外的 deva。

共同证据：`measure.py`、`logs/measure-current.json`、`qml/`；全量验收 `1349 passed, 5 skipped, rc=0`。
