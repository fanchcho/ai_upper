# F84/F06及像素对照

F84重试：AI_UPPER_HOME=/tmp/ai-upper-ime-abi QT_QPA_PLATFORM=offscreen QT_IM_MODULE=fcitx QT_DEBUG_PLUGINS=1 QT_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt6/plugins，使用当前.venv/PySide6实际构建QApplication/QLineEdit。系统fcitx插件被发现但加载失败，ime-abi.log原文：libQt6WaylandClient.so.6 undefined symbol _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API。这是插件加载诊断，不是实际键盘输入成功；没有preedit成功证据。依赖pin未改；合成事件未用于升级结论。真实环境未验证。

F06保留上一轮Linux实窗flags证据，宿主非macOS，macOS成功态未验证；不改不适用。

本轮重新运行 scripts/parity/final_port/identical_os.py，再运行 compare_identical.py。真实私有D-Bus/Secret Service与Electron safeStorage均成功。Qt保存后的config/mcp/skills/personas复制为同fixture，两端1280x820、滚动142，暗亮Saved态；原始日志pixel-attempt.log与fixture/geometry已归档。并排图compare-identical-*.png。字段标签delta均0.0，但像素相等比例非100%，未归零。对照范围是MCP详情，不外推为正文、机器人或手机整个应用像素闭环。未改token/坐标补偿。
