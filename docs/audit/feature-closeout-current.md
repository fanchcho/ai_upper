# 本轮收口证据（整体未完成）

基线45f71d16ec1637411362c8c6dca2c28bceb95292，本轮只处理原任务未完成项。

## 并发写入

入口 status 只有三个未跟踪实验脚本。本轮运行中，docs/audit/feature-parity-gap.md、.json、extensions-os.md、extensions-rounding.md 被非本次工具调用修改。前两文件被覆盖回宣称 HEAD=b25dc1b 的旧盘点，丢掉上一轮45f71d1中的审计结果。原始差异保存 out/parity-close/concurrent-docs.patch，快照 .tmp/parity-close/concurrent。没有将这些未经核验的改动纳入本轮提交，也没有覆盖它们。

因此本报告不提供伪造的全量三态计数；59项判定仍未完成。需要先停止另一写入源，才可安全统一主报告。其余功能补齐也没有全做完，不能把全部未完成归咎于文档冲突。

## 已补齐

- f4df4918cbab7c540000b8d5de369a8831a74d95：会话筛选。原版 Rail.tsx:182-203、389-421。QML Main.qml filterRoles/filterFolders/visibleSessions → SessionFilter.qml；ShellBridge._rows新增focusRoot。真实点击选择角色和完整目录路径，同名目录显示父目录区分，同类OR、跨类AND，清空恢复；暗亮截图 filter-dark/light.png，读回 filter.json，均在out/parity-close。
- 92d9be2d2f208a085b7a51e9da56540542114827：花名册入口。原版 Rail.tsx:134-142、QuickStart与角色发起会话路径；Main.qml railRoster → PersonaRoster.qml，复用quickStartPersonas/startQuickStart。真实点击入口、粘贴角色名搜索、点击开始会话，读回会话JSON的personaId。截图roster-dark/light.png、roster.json。这是功能入口补齐，不宣称原版整页布局或头像编辑、排序、记忆等完整移植。

## 代理路由明确判定

原版 main/http.ts:41-65 有送达前错误限定、系统代理探测、换路由重试和按origin记忆；:94-96选择system、env、direct；:103-107调用resolveProxy。
移植 app/src/mvvm/services/http_client.py:31-62解析环境代理和NO_PROXY；:109-114以proxy参数创建httpx客户端，trust_env=False。
结论：环境代理和直连已实现；**系统代理/PAC探测及安全失败重试、成功路由记忆未移植**。这是明确缺口，不是Electron独有能力的免责结论。
真实网络验证scripts/parity/feature_review/proxy_evidence.py：本地HTTP代理收到绝对URL，NO_PROXY命中后本地源站收到/direct。结果out/parity-close/proxy.json；未拿替身冒充系统代理。QML没有独立代理表单；原版也主要依赖环境变量/自动路由。web服务复用该HTTP客户端的存在不记作QML新增界面。

## 同数据成功态与相位

scripts/parity/closeout/identical_os.py：先让Qt在真实GNOME Secret Service中保存，复制其config.json/mcp.json/skills/personas到原版隔离目录，再启动只读原版Electron。两端密钥输入均FIXTURE，暗亮均Saved，同1280×820，垂直滚动偏移均142。Qt输出EXACT_SCROLL 142，原版输出BOTTOM top=142,max=142。
数据清单identical-fixture.json、日志identical-final.log、并排compare-identical-dark/light.png均在out/parity-close。比较条件已收口，**像素没有归零**：同滚动偏移下字段纵向布局仍有明显差异，不能称其为单像素引擎取整。

正文相位复跑：out/parity-close/phase/phase-measurements.json。暗亮一致：相位0/1差值+1,+1,0,+1,+1,0；相位0.5六段一致。支持当前正文fixture的栅格定位归因，不添加补偿。

菜单阴影复跑发现真实样式问题：原版components/Select.tsx:75 MAX_H=320、:114-122限定可用高度；Qt此前全量展开七角色，导致采样落在菜单本体而非阴影。补320px高度上限、Flickable、滚动条和键盘活动行滚动后，两端相同相位重测。坐标(700,700)暗色0/.5一致、1相位蓝通道差1；亮色0/.5差1灰阶、1相位一致。剩余为相位相关残差，未归零；未修改颜色、字体或阴影token，也未添加坐标补偿。此修复只覆盖320px上限，原版靠近窗口边界时向上展开的完整放置逻辑仍未移植。

## 遗留脚本明确处置

scripts/parity/electron_safe_storage_session.py **保留原位、不提交、不作为本轮验收入口**。它是其他执行的遗留调试稿：修改HOME、缺AI_UPPER_HOME隔离、只做单主题且使用DOM setter。已备份到.tmp/parity-close/concurrent，替代验证入口为本轮closeout/identical_os.py。不删除不明执行仍可能使用的文件。c9_compare.py/phase_sweep.py/shape_sweep.py同样保留，未冒领其结果。

## 未完成要求

- 59项全量三态判定和主Markdown/JSON统一：未完成。
- 定时任务、机器人入口：未完成；不能接一个空页面假装完成。
- 单实例、托盘、回复通知、指令联想、@候选、未读：未完成。
- 系统代理缺口已判明，尚未实现。
- 同fixture同滚动位置比较条件已完成；页面像素一致仍未完成。
- 正文/阴影相位复跑完成；菜单上限真实缺口已修，剩余差异未归零。
