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

边界：这是移植版真实OS成功，不是Electron safeStorage成功。本轮没有重启原版Electron接入该bus，因此原版成功态同状态像素对照仍未验证。上轮extensions_secret_double.py仍保留为无OS环境回归，与本轮真实证据目录分开。

全量pytest：1429 passed, 9 skipped in 365.26s (0:06:05)，0 failed，out/extensions-shell/pytest.log。此项仅新增验证脚本和报告，不修改产品依赖或密钥实现。
