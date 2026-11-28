# 交付文件下载

原版依据：`deva/apps/desktop/src/main/services/remote/web/adapter.ts:203-204`；`remote/web/files.ts:210-260` 的 sid/tool/index 下载、文本/Office 预览和二进制分块；`shared/remote-web.ts:299-313,332-336` 的 file/file_chunk、192 KiB、30 MiB 上限。

复用现有 `deliverables.delivered_path` 与 `office_text`。浏览器只从已记录边车渲染交付按钮，经认证且受会话范围约束的 file 请求读取。没有开放路径参数。普通文本预览截断 400000 字符，Office 转文字；其它文件 192 KiB 分块组装 Blob，可保存到本机磁盘。

真实交互命令：
```
AI_UPPER_HOME=/tmp/ai-upper-download-run QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py download
```
四组浏览器键鼠（LAN/relay × 暗亮）发消息 → 真实 ChatHost 请求本机模型 fixture → 返回 present_files 工具调用 → 真实工具登记交付边车 → 手机点击下载文本与 256000 字节文件（跨块）→ 浏览器 download 实际写盘，逐字节比较源文件 → 重开 ChatSessionStore 读出 delivered 边车。结果 `download/phone-readback.json`，截图 `download/phone-browser-{dark,light}-{lan,relay}.png`，原始日志 `download/run.log`。单测覆盖未登记工具、布尔序号、文件移除拒绝：2 passed（含既有 scope 测试）。

边界：本机 LAN 与 relay/model fixture，非公网/真机；Office 路径复用现有解析器，本轮端到端样本为 txt 和 bin。无外部送达成功声明。
