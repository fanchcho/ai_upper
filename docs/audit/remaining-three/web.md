# Web 安全配对与浏览器订阅入口

原版依据（deva 只读）：`apps/desktop/src/main/services/remote/web/devices.ts:89-113` 配对票据两分钟；`web/secure.ts:43-112` X25519/HKDF 和首次密文证明；`shared/remote-crypto.ts` 的协议实现；`web/adapter.ts:213-216` push/visible 命令，:520-542 保存订阅并跳过前台设备。原版完整手机端还含中继、局域网及安装票据，本轮只实现题述本机浏览器配对/订阅入口，不将其算作完整手机端。

实现：仅监听 loopback 的 HTTP/WebSocket；内存短期票据、密文证明后消费、设备密钥保存、加密顺序帧与重放拒绝；刷新以设备密钥重连；设备前台状态上报和发送前抑制；移除用户同时断开连接/删密钥；浏览器 Service Worker + PushManager.subscribe 入口。未认证的 resume 请求不能伪装前台设备。UI 避免配对/错误文字与列表重叠。

真实验证分两层：

- scripts/parity/web_pair_ui.py：暗亮真实 QML 点击生成票据、真实 QtWebSocket 加密握手及证明、配置重新读盘、前台收件人数为零、重放关闭连接。这里订阅用明确标记的 push.invalid 协议样本验证序列化落盘，**不是外部 PushService 订阅成功证据**，未发任何外部请求。
- scripts/parity/web_browser_host.py + web_browser_check.cjs：真实 Electron 浏览器连接生产本地服务；实际页面 JS 完成安全配对，配置重新读出一个设备；浏览器隐藏/显示经页面 visibilitychange 上报，被真实服务观察为后台/前台；刷新同一页面使用设备密钥恢复且不重复建人。真实鼠标点击订阅按钮，宿主 PushManager 原文返回下述失败；真实 QML 鼠标点击移除设备，浏览器连接关闭，重开配置/密钥库确认用户及设备密钥删除。没有替换 WebSocket、PushManager 或宿主控制器回调。

```
未验证：AbortError: Registration failed - push service not available
```

当前浏览器宿主没有可用 PushService；验证程序也未给予通知权限，未制造许可成功。外部订阅成功及送达 **未验证**。暗亮真实渲染在 assets/browser-*.png；交互结果 browser.json，原始日志 browser.log。字体由本机已存在 Noto CJK 注入截图运行环境，仅解决缺字；截图非合成。

client.ts 使用原版 MIT remote-crypto.ts；编译产物 client.js 纳入仓库，LICENSE.deva 与 LICENSE.noble 保留。构建使用原版已安装 esbuild 与 Noble 包（只读依赖），未改依赖 pin：

```
NODE_PATH=/home/agent/shared_workspace/deva/node_modules /home/agent/shared_workspace/deva/node_modules/.bin/esbuild app/src/web_pair/client.ts --bundle --format=iife --minify --outfile=app/src/web_pair/client.js
```

并发说明：外部执行在 528be75 提前提交了本执行尚在验证的 Web 文件及它添加的两个测试；保留该提交，本报告不把那个提交视作本执行验收。本执行随后修正兼容层、刷新恢复、撤销和状态显示，并独立完成上述交互。外部测试未修改。
