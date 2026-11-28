# 手机附件上传（本地验证）

原版只读依据：`deva/apps/desktop/src/main/services/remote/web/adapter.ts:195-202` 注册四帧；`remote/web/files.ts:89-176` 实现设备归属、50 MiB、20 个并发、2 小时回收、顺序块及发送时消费；`shared/remote-web.ts:329-336` 规定帧与块大小。

移植：`app/src/mvvm/services/phone_uploads.py` 实际写入隔离 home 的 uploads，使用现有 AttachmentService 登记，再由 `phone_sessions.handle` 送进真实 ChatHost。浏览器文件输入使用 192 KiB 分块，不接受手机传来的宿主文件路径。

执行：
```
AI_UPPER_HOME=/tmp/ai-upper-upload-tests .venv/bin/python -m pytest app/tests/test_phone_uploads.py app/tests/test_phone_sessions.py -q
# 2 passed in 0.14s
AI_UPPER_HOME=/tmp/ai-upper-upload-run QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_upload_evidence.py
```

`phone-readback.json` 四组 LAN/relay × 暗/亮记录包含独立 /tmp home、实际模型 HTTP 请求、重开 ChatSessionStore 读出的附件正文和回复、设备记录。`phone-browser-{dark,light}-{lan,relay}.png` 为真实渲染。测试真实键鼠发送，文件用 CDP 的 DOM.setFileInputFiles 选取真实磁盘文件。原生 GTK 文件选择器在本宿主报 `No GSettings schemas are installed on the system`，日志 `file-chooser-failure.log`，core 保留在 `.tmp/phone-extensions/file-chooser.core`；不将 CDP 选文件说成原生选择器成功。

验证边界：LAN 是真实本机监听；relay 与模型是 127.0.0.1 fixture，ChatHost、加密协议、HTTP、磁盘与浏览器均真实执行。没有公网 relay、真实手机或外部模型成功态。已通过附件属于其他设备拒绝、乱序删除未完成文件的新增测试。既有断言未改。

远端复核：该项提交 `564d226da261c9496599931b4d780fef7ad93ab6` 已包含在 `origin/develop` 的 `6c62ff9891c2b8dd0b5036fbf2608677a1331c68` 祖先链中，未重写。
