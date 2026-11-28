# 默认 Qt 6.11.2 与系统 fcitx 插件的 ABI 复核

本轮基线为 5f7bad26a36b661bcd623c4597dfdeb73c1ccf98；不重做已验收内容。应用代码树见 application-baseline.log，运行数据均使用 /tmp 中的独立目录。

## 本轮实测

- `.venv/bin/python` 的 PySide6 与 `QtCore.qVersion()` 均为 **6.11.2**，见 versions.log。
- 系统 `fcitx5-frontend-qt6` 为 **5.1.9-1+b1**；系统 Qt Core/Gui 为 **6.8.2+dfsg-9+deb13u2**，WaylandClient 为 **6.8.2-4**。见 system-packages.log。插件元数据 `version=395264` 即 Qt **6.8.0** 的主/次版本编码；不能从这个值单独推出补丁版本。
- 先导入默认 venv 的 QtGui，再执行 `QPluginLoader(system_plugin).load()`，得到 **False**，原文见 plugin-loader.log：

```
Cannot load library /usr/lib/aarch64-linux-gnu/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so: /lib/aarch64-linux-gnu/libQt6WaylandClient.so.6: undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API
```

实际符号为 `_ZTI20QGenericUnixServices`，不是线索中的 `_QTI20QGenericUnixServices`。system-dynamic.log、system-symbols.log、system-ldd.log 给出 fcitx 的依赖与私有符号。wayland-symbol.log 证实未解析的 RTTI 符号来自系统 WaylandClient；system-gui-symbol.log 证实系统 QtGui 导出该符号。默认 6.11.2 QtGui 的 runtime-symbols.log 中无该符号，runtime-gui-services.log 中是 `QDesktopUnixServices`。plugin-loader.log 的进程映射证明失败测试已加载 venv 的 QtCore/Gui/DBus。

最早一次仅用 ctypes 加载、未先导入 venv QtGui 的探测没有报错，load-error.log 因此为空。这不能作为默认应用 ABI 兼容证据；有效复现是上述 QPluginLoader 加进程映射检查。

## 可复核命令

```sh
AI_UPPER_HOME=/tmp/ai-upper-qt611-abi .venv/bin/python - <<'PY'
from PySide6 import QtGui, QtCore
p = '/usr/lib/aarch64-linux-gnu/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so'
loader = QtCore.QPluginLoader(p)
print(QtCore.qVersion(), loader.metaData())
print(loader.load(), loader.errorString())
PY
readelf -d /usr/lib/aarch64-linux-gnu/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so
nm -D /usr/lib/aarch64-linux-gnu/libQt6WaylandClient.so.6 | rg QGenericUnixServices
nm -D .venv/lib/python3.13/site-packages/PySide6/Qt/lib/libQt6Gui.so.6 | rg 'QGenericUnixServices|QDesktopUnixServices'
```

这是一条 Qt 私有 ABI 跨版本依赖链问题；仅把系统插件目录加入搜索路径不足以解决。隔离构建结果和运行验证另见本目录 build.md 与 input.md。
