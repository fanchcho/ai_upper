# 系统代理补齐与真实网络验证

原版依据：`deva/apps/desktop/src/main/http.ts:43-73` 仅送达前失败换路由、按 origin 记忆成功线路；`:119-123` 使用系统代理解析（包括 PAC）；`:162-180` NO_PROXY 转换规则。

实现：`app/src/mvvm/services/http_client.py` 处理 CIDR、端口、通配符、逗号/空白分隔及 IPv6；`system_proxy.py` 通过真实 libproxy 的 PAC/WPAD/桌面配置解析，缺少时回落 Qt 平台查询；`transport.py` 仅对 ConnectError/ConnectTimeout/ProxyError 换路由，原始失败保留，读写中断不重发；`provider_setup.py` 在未显式配置代理时接入系统路由。

验证命令：

```sh
AI_UPPER_HOME=/tmp/ai-upper-proxy-final \
LD_LIBRARY_PATH=$PWD/.tmp/final-port/proxy-runtime/root/usr/lib/aarch64-linux-gnu:$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
PX_MODULE_PATH=$PWD/.tmp/final-port/proxy-runtime/root/usr/lib/aarch64-linux-gnu/libproxy/0.4.18/modules \
.venv/bin/python scripts/parity/final_port/proxy_routes.py
```

真实证据：`out/final-port/proxy-routes.log`、`out/final-port/proxy-routes.json`。使用 ThreadingHTTPServer 的真实 socket，libproxy/WebKit 下载并执行 PAC。没有注入替身 resolver。结果 PASS：

- 环境代理收到 absolute URI 和请求正文。
- CIDR NO_PROXY 命中后目标收到 origin-form 路径。
- 第一次连接拒绝 → 系统 PAC 代理成功。
- 恢复直连目标后第二次仍走已记忆的系统路由。
- 停止代理后换回直连，并更新 origin 记忆。
- 请求正文已经送达后断开连接，目标只收到一次，无重发。
- 已取消请求不建立连接。
- 7 个 NO_PROXY 边界覆盖 CIDR、通配符、端口正反例、空白分隔、IPv6。

宿主限制如实保留：原环境未安装 libproxy。第一次真实运行记录 `System PAC resolver unavailable: libproxy not found; using Qt platform resolver`，PAC 返回 None，断言失败。为完成实证，仅把 Debian bookworm ARM64 的 libproxy 0.4.18、WebKit PAC 插件与其 JavaScriptCore/ICU 运行库解包至 `.tmp/final-port/proxy-runtime/`，没有修改依赖 pin 或系统目录。生产机器缺少系统 PAC 库时会记录原始加载错误并使用 Qt 平台能力；不能据此声称所有 Linux 安装都支持 PAC。Windows/macOS 原生系统代理路径尚未在对应宿主验证。

本项只覆盖实际使用 HttpxTransport 的调用路径；它不证明 Chromium 独立网络服务、系统 CA、所有工具自带 HTTP 客户端都已移植。

API 对照：[Qt 平台代理解析](https://doc.qt.io/qt-6/qnetworkproxyfactory.html#systemProxyForQuery)、[libproxy 原生 API](https://github.com/libproxy/libproxy/blob/0.4.18/libproxy/proxy.h)。
