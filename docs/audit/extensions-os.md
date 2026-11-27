# 第2项：真实OS凭据验证

系统初始没有dbus-daemon/dbus-run-session，apt-get download返回Unable to locate package。不是最终阻塞：使用Debian trixie arm64 Packages.xz索引下载dbus-daemon/dbus-bin/dbus-session-bus-common/gnome-keyring/libsecret及所需库，只解包到.tmp/secret-service/root，不安装系统包、不改产品依赖pin。首次ldd发现libapparmor.so.1、libgpg-error.so.0缺失，补齐后启动成功。

复现命令（仓库根，网络需可访问deb.debian.org；本轮使用gnome-keyring48.0-1、dbus1.16.2-2；下载脚本按当前trixie索引解析，不是产品依赖）：
```
AI_UPPER_HOME=/tmp/ai-upper-os-session .venv/bin/python scripts/parity/fetch_secret_service.py
AI_UPPER_HOME=/tmp/ai-upper-os-session .venv/bin/python scripts/parity/extensions_os_session.py
```
脚本启动私有unix socket D-Bus，独立XDG_DATA_HOME/runtime/config；gnome-keyring-daemon --unlock --components=secrets使用公开fixture口令解锁隔离测试钥匙串。PYTHON_KEYRING_BACKEND=keyring.backends.SecretService.Keyring。真实set/get/delete探针通过，再暗亮QTest输入→600ms自动保存→真实vault→GNOME Secret Service，重进详情Configured可见。没有使用字典替身、没有替换keyring API。UI测试fixture原本强制file后端，因此在测试构建后选择真实keyring实例，不改产品存储实现。

原始输出out/extensions-os/session.log：
```
KEYRING 0 GNOME_KEYRING_CONTROL=.../.tmp/secret-service/runtime/keyring
BACKEND keyring.backends.SecretService.Keyring (priority: 5)
REAL_OS_ROUNDTRIP_OK
REAL OS BACKEND keyring.backends.SecretService.Keyring (priority: 5)
REAL OS: real QTest input -> timer -> bridge -> vault -> GNOME Secret Service; Saved visible
REAL OS: reopened detail Configured visible; real OS credential readback
```
暗亮各一组输出。截图dark/light-secret-real-os-saved.png、dark/light-secret-real-os-configured.png。首次浅色因隔离钥匙串共享测试键，已呈Configured导致找不到未配置placeholder；session-first.log保留，修正每主题先清理该fixture键再测，最终通过。测试session结束关闭总线。

边界：这是移植版真实OS成功，不是Electron safeStorage成功。本轮没有重启原版Electron接入该bus，因此原版成功态同状态像素对照仍未验证（此项已由下方 2026-11-27 续做闭环）。上轮extensions_secret_double.py仍保留为无OS环境回归，与本轮真实证据目录分开。

全量pytest：1429 passed, 9 skipped in 365.26s (0:06:05)，0 failed，out/extensions-shell/pytest.log。此项仅新增验证脚本和报告，不修改产品依赖或密钥实现。

## 2026-11-27 续做：原版 Electron safeStorage 接入同一私有 D-Bus（C9）

上一轮边界「没有重启原版 Electron 接入该 bus」本轮已闭环。新增 `scripts/parity/electron_safe_storage_session.py`：脚本自己起同一套真实 `dbus-daemon` + `gnome-keyring-daemon --unlock --components=secrets`，再以 `DBUS_SESSION_BUS_ADDRESS` / `XDG_RUNTIME_DIR` / `XDG_DATA_HOME` / `XDG_CONFIG_HOME` / `XDG_CURRENT_DESKTOP=GNOME` 启动**原版 Electron**（`deva/apps/desktop/out/main/index.js`，Electron 33.4.11，源码只读），用 CDP 真实点击 Settings → Extensions → Probe，在密码框逐字符输入并等 600ms 自动保存。没有 mock safeStorage、没有替换 keyring、没有改 deva。

复现命令（仓库根）：
```
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu \
  .venv/bin/python scripts/parity/electron_safe_storage_session.py
LD_LIBRARY_PATH=$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
  .venv/bin/python scripts/parity/c9_compare.py
```

原始输出（`out/electron-safe-storage/session.log` 同份）：
```
KEYRING 0 GNOME_KEYRING_CONTROL=.../.tmp/secret-service/runtime/keyring
SECRETS_AVAILABLE true
TYPE_SECRET typed
BODY_HAS_SAVED True
STATUS_TEXT ["Saved"]
SECRETS_JSON True 75
KEYRING_ITEMS [{"label":"Chrome Safe Storage Control","attrs":{"xdg:schema":"_chrome_dummy_schema_for_unlocking"}},
 {"label":"Chromium Safe Storage","attrs":{"application":"Electron","xdg:schema":"chrome_libsecret_os_crypt_password_v2"}},
 {"label":"Password for 'mcp:echo:TOKEN' on 'deva'","attrs":{"application":"Python keyring library","xdg:schema":"org.freedesktop.Secret.Generic"}}]
```
说明：`Chromium Safe Storage` 的 `application=Electron` 是 Electron/Chromium 的 libsecret 主密钥条目，证明 safeStorage 真的走私有 GNOME Secret Service；`secrets.json` 75 字节是 base64 密文而非明文。`Password for 'mcp:echo:TOKEN'` 是上一轮移植版真实 OS 测试留下的同总线条目，本轮未复用它作为 Electron 证据。

截图与同尺寸对照：
- 原版成功态：`out/electron-safe-storage/deva-secret-saved.png`（1280×820，`Saved` 可见）；
- 移植版同状态：`out/extensions-os/light-secret-real-os-saved.png`（1280×820，`Saved` 可见）；
- 1:1 并排：`out/electron-safe-storage/compare-secret-saved.png`（两图各裁设置弹窗 720×567，左原版右 Qt，1456×595，无缩放）；
- `compare-secret-saved.json`：pixel_equal_percent=70.821、mean_abs_rgb_sum=20.537、max_channel_diff=667。差异包含两端既有的设置弹窗版式/字段间距差，不是 safeStorage 功能差异；两端“Saved”状态与真实钥匙环写入均已分别验证。

结论：C9 **闭环**——原版 Electron safeStorage 真实成功态已取得，并与移植版同状态做了同尺寸对照；不再使用上轮替身数据。
