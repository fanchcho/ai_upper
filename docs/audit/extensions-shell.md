# 设置导航归位（第1项）

基线070eb0ae8d360b82017e1ba95eab5e09962580d6，本地远端一致，status空。

原版只读依据：SettingsPane.tsx:48–51只有General/Models/Extensions/About，:82挂载ModelSettings；features/settings/ModelSettings.tsx:224新增provider，:439/:487/:518自定义provider详情；SettingsPane.tsx:497–665 MCP详情；redesign/ChatFirstShell.tsx:771挂载PersonaEditor，ProfileView.tsx:206角色编辑。

归位：删设置导航Custom model/MCP/Personas三项。Models保留已有自定义provider新增/详情，以及插件专用模型网络子页入口；Extensions保留扫描注册MCP详情，并新增MCP管理子页入口以保全独立插件注册和approval。Personas原始文本编辑入口移到会话启动页，独立编辑页返回chat。所有旧直达settings-*路由、服务和文件格式保留。插件专用网络配置/approval和原始角色文本编辑不完全等价于原版表单，明确保留附加功能，不声称页面内所有控件1:1。

真实点击发现旧modelsCustomNetwork直接赋值root.pane打断绑定，返回后导航失效；改走现有paneRequested信号。插件子页补Back。

scripts/parity/extensions_shell_evidence.py：暗亮真实QTest点击4个导航、Models→网络→保存→返回、Extensions→MCP→保存→返回、chat→Personas→保存。读回模型fixture-model、服务器fixture、角色fixture-persona正文Persistent persona fixture。每种主题输出navigation/custom-saved/mcp-saved/persona-saved.png及disk-files.json，日志dark.log/light.log。截图/日志目录out/extensions-shell。6个既有插件/模型页面测试通过；全量结果后续审计记录。

命令：AI_UPPER_HOME=/tmp/ai-upper-shell-dark2 LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python scripts/parity/extensions_shell_evidence.py dark（浅色独立/tmp/ai-upper-shell-light2，参数light）。
