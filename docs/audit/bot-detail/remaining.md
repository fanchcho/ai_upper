# 明确未完成项

F62：已完成独立详情、角色/会话多选并真实保存/删除验证；原版扫码创建飞书应用、完整二维码邀请/创建全集未完成。原版BotsPane.tsx scanStart/scanCancel与remote onboarding不是现有手填凭据入口的同义替代。

F64：完整PhonePane、QR、LAN/relay双通道、设备状态及跨设备会话往返未完成。本轮没有新增手机双通道代码，不能把Web本机配对当交付，也不能以无公网/手机设备掩盖本地实现欠项。

F84：本轮显式加载系统Qt6 fcitx插件失败（Qt PRIVATE_API符号缺失）。未取得真实preedit/commit；只是ABI诊断，未改依赖pin、未冒充输入成功。

F06：沿用既有Linux非macOS分支实窗证据，macOS成功态未验证，不标不适用。

回归稳定性：五次独立test_bot_roundtrip.py，每次独立进程启用faulthandler，均1 passed；不能由未复现推出修复。首次全量段错误仍未归因、仍属风险。

像素：本轮重新获取原版和Qt同fixture/同滚动142/同1280x820/同Saved的暗亮MCP详情，safeStorage成功，字段delta0；像素94.123%/94.729%，未归零。不是正文全应用像素验收，未增加坐标补偿。

全量原始命令：AI_UPPER_HOME=/tmp/ai-upper-bot-detail-full PYTHONFAULTHANDLER=1 QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python -X faulthandler -m pytest app/tests -q --basetemp=$PWD/.tmp/bot-detail/full

结果1480 passed / 9 skipped / 0 failed，556.10秒，full.log。运行期间仅修正BotDetail的暗色文字并完成专门真实交互重验，没有改测试断言或Qt预载。
