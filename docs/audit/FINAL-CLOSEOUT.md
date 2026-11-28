# 最终收尾：实现与验证边界

工程实体位置：`/home/agent/shared_workspace/pc/ai_upper`。`/home/agent/shared_workspace/ai_upper` 与 `/home/agent/shared_workspace/py_upper` 两个入口均解析到该实体，前者保留宿主workspaceRoot可用性。迁移用同盘mv，迁前后HEAD、状态、4669个跟踪文件和.git 80604192字节一致，fsck退出0。详细清单见 [迁移报告](pc-migration/MIGRATION.md)。

## 三档交付

|档位|内容|证据索引|
|---|---|---|
|已实现并验证|用户此前验收的81项；手机上传、下载、交互卡、任务管理与安装票据本机协议；成员/任务/回滚补齐|既有feature-parity-gap.md、phone协议专题及各轮收尾；本轮不重新审计或重跑已验收交互|
|已实现并验证|默认Qt6.11真实fcitx输入、生产ChatHost本地fixture回合与独立读盘；嵌套Weston Wayland输入|qt611/input.md、remaining-boundaries/wayland.md；均限定本地环境|
|已实现并验证|工程迁移、新旧入口最小测试、同盘完整性与引用分类|pc-migration/，新入口3 passed/6.55秒，旧入口3 passed/5.85秒|
|已实现未验证|物理设备、外部渠道、macOS及物理Wayland宿主成功态|下方阻塞表；不能用本机fixture代替|
|未实现及阻塞|两处历史崩溃的根因修复、稳定最小复现|remaining-boundaries/crash.md、order-bisection/；没有充分根因证据，不改生命周期猜测修复|

这是对已验收范围与剩余边界的收尾，不把旧89行计数重新解释成全平台成功。组合项的后续实现以各专题证据为准。

## 像素验收二选一结论：落在本轮约定验收口径内

接受渲染引擎亚像素差的前提下，现有“未归零”属于可接受残差，不作为结构/间距/字体/配色未移植处理。依据：extensions-shell-final.md、extensions-runtime-parity.md提供页面布局核对；extensions-rounding.md历次同数据/相位、颜色解析和模糊后端实验定位到引擎栅格与量化。正文renderType开关没有消除差异；Qt box blur参数离散化与原版Skia sigma处理不同；暗亮相位矩阵尾部约1灰阶且随形状/相位变化，不支持统一坐标补偿。

证据索引：extensions-rounding.md、next-boundary/pixel.md及sources/、raster-backend/、remaining-boundaries/phase-matrix.json。这个验收判断不是宣称每个像素相同或已经证明全部残差唯一原因；物理显示缩放组合仍无全面覆盖。本轮不改token、不加坐标补偿。

## 设备、宿主与凭据阻塞

|项目|阻塞原因|所需资源|当前证据|
|---|---|---|---|
|F06 macOS红绿灯|当前Linux宿主|真实macOS桌面|既有Linux分支检查，macOS成功态未验证|
|真手机扫码/第二台设备LAN|无对应设备|手机及同网第二台设备|既有本机LAN/relay协议读盘，不是真机|
|公网relay/移动网络|无公网部署与移动测试环境|可访问relay及移动网络|本机relay fixture协议闭环|
|外部推送/机器人真人授权|无有效渠道凭据/授权|飞书、Telegram或Web Push真实授权设备|已有配置/拒绝日志与本地链路；送达未验证|
|iOS/Android系统安装|无移动系统宿主|真机浏览器及系统安装流程|安装票据有效期/一次性消费已验证|
|真实外部模型|无有效端点凭据|可调用模型端点与授权|ChatHost只验证本地OpenAI兼容fixture|
|物理Wayland/原生text-input协议|仅嵌套Weston资源|物理桌面及对应协议宿主|嵌套Wayland+fcitx D-Bus通过，不等同text-input-v3验证|
|远端推送|原SSH私钥不存在、HTTPS无写凭据|恢复仓库SSH身份或HTTPS写认证|origin SSH失败；HTTPS只读回读e8fdc2c成功|

## 提交与测试

迁址提交515b587保存在本地；origin推送失败原文见pc-migration/push-paths.log，未伪报远端SHA更新。远端HTTPS只读为e8fdc2cad57b073e46e5d16f99d6645fdbce8173。后续本地提交由git log查询；认证恢复后直接git push origin develop，无需改写历史。

迁后首轮全量1486 passed/9 skipped/0 failed，563.18秒；当时新增文档尚未入索引。随后顺序切分发现索引内新文档裸旧别名触发已有断言，已修正文档表述（不是修改断言），首次失败保留bot-second.log。最终索引后的全量与切分数字见order-bisection/RESULTS.md。

## 未完成

远端推送未完成；两处历史段错误根因未归因、未修复；无稳定失败oracle时不能从通过的分组推导“无顺序依赖”。设备表全部外部/物理成功态仍未验证。像素未归零但按本轮用户约定口径验收，不再改像素补偿。deva只读未改、运行home均/tmp、真实用户配置未写。

最终全量（交付文件入索引后）：1486 passed / 9 skipped / 0 failed，557.96秒。工作树待本收尾提交后核验；origin推送仍因认证缺失未完成。
