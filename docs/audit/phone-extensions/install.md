# 主屏幕安装票据

原版依据：`deva/apps/desktop/src/main/services/remote/web/adapter.ts:207-211` 请求；`remote/web/devices.ts:78-144` install 类型、一小时 TTL、一次消费、三次失败作废且不随普通二维码刷新失效；`mobile/link.ts:447-452` 请求与响应；`mobile/onboard.tsx:217-231` 把票据写入 URL；`mobile/App.tsx:141-158` 优先恢复已有设备，仅无凭证时消费 install；`mobile/index.html:36-37` manifest 不写 start_url。

实现：仅已认证手机可请求 install，票据仅驻内存，独立 kind，LAN/relay 保活覆盖一小时有效期；普通二维码取消/刷新不销毁安装票据。浏览器真实按钮展示安装说明，URL #i 保存票据，启动后清除；独立存储换新设备，已有凭证刷新恢复原设备。manifest 不指定 start_url，LAN 服务实际返回 manifest。无外部密钥写进页面。

验证命令：
```
AI_UPPER_HOME=/tmp/ai-upper-install-run QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu .venv/bin/python scripts/parity/phone_extended_evidence.py install
```
四组 LAN/relay × 暗亮真实点击「添加到主屏幕」→ 隔离 BrowserWindow 存储打开安装 URL → 握手得到独立设备 → 真实键鼠发 INSTALL_WRITE → ChatHost 本机 HTTP fixture 回复 → 第三个隔离存储重放被真实拒绝 `配对票据已过期或已使用` → 原浏览器刷新正常恢复 → 重开 config.json 和 ChatSessionStore 读回两个设备与消息。`install/install-{theme}-{via}.json` 原文与读盘链路；`install/phone-browser-install-{theme}-{via}.png` 暗亮真实 UI；`install/run.log` 原始结果。TTL/取消不影响 install 的新增测试与既有配对测试：2 passed in 1.43s。

未验证：真实 iOS/Android 添加到主屏幕、系统安装提示/图标与真机独立存储。隔离本机浏览器只验证协议语义，不能当真机安装成功；relay/model 仍为 127.0.0.1 fixture，不是公网服务。

远端复核：该项提交 `b53779c3ac184531b773597c773d3037d44100b7` 已包含在 `origin/develop` 的 `6c62ff9891c2b8dd0b5036fbf2608677a1331c68` 祖先链中，未重写。
