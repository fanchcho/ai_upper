# Qt 6.11.2 SDK 与 fcitx 插件：构建、加载已闭环

## 实际产物

- SDK：`/tmp/ai-upper-qt611-sdk/install`，Qtbase **6.11.2**，Core/Gui/DBus/Widgets、工具、公开/私有开发头与导出 CMake targets 均已构建安装。
- 插件：`/tmp/ai-upper-qt611-sdk/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so`，fcitx5-qt **5.1.17** 源码，Qt 主/次版本元数据 **396032 = 6.11.0**；实际构建 SDK 的补丁版本为 **6.11.2**。
- `Qt6Config.cmake`、`Qt6GuiPrivateConfig.cmake`、`QtGui/6.11.2/QtGui/qpa/qplatforminputcontext.h` 的实体路径见 sdk-targets.log。fcitx-configure.log 明确找到了 `Qt6`、`Qt6GuiPrivate`；fcitx-link-command.log 明确链接 SDK 6.11.2 库。
- SDK 编译/安装、fcitx 配置/编译/安装的 `.exit` 均为 **0**。new-plugin-loader.log 中 `load True`，运行库映射全部为默认 venv 的 Qt 6.11.2；未用 SDK Qt 库替换应用运行时。

## 来源与复现

Qt 官方源包：`https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz`。fcitx 使用上一轮取得的官方 `fcitx/fcitx5-qt` master 归档 `.tmp/next-boundary/fcitx.tar.gz`（内容版本 5.1.17）。inputs.sha256 固定本轮归档内容，source-integrity.json 对比 22,857 个 Qt 文件、180 个 fcitx 文件，均无修改。构建未修改这些供应商源码。

```sh
bash scripts/parity/build_qt611_fcitx.sh
```

脚本使用 `/tmp/ai-upper-qt611-sdk`，依赖上一轮隔离解包的 ECM/XKB 开发文件 `.tmp/next-boundary/sdk/usr`，未安装到系统。首次配置因无 Ninja 失败（configure.log），改用 Make；随后 OpenGL 检测失败（configure-make.log），用官方 `INPUT_opengl=no` 选项关闭开发 SDK 的 OpenGL，最终配置成功（configure-final.log）。完整配置见 sdk-config.summary；这份 SDK 是用于编译插件的 Qtbase 开发 SDK，不是含 QtQuick 在内的所有 Qt 附加模块，也不是默认应用运行时的替代品。

插件 `BUILD_ONLY_PLUGIN=ON`，关闭 `ENABLE_X11` 的可选 X11 focus-group 设置和 `ENABLE_QT6_WAYLAND_WORKAROUND` 的私有 Wayland 兼容分支；真实输入仍走 Qt xcb 窗口 + fcitx D-Bus input context。当前验证范围为 X11，不宣称 Wayland 通过。Qtbase 自身 XCB/OpenGL 关闭不影响应用，因为应用继续用 venv 的原 xcb/QtQuick 库。

## 库搜索路径、影响面与回退

插件去掉 SDK RPATH（`CMAKE_SKIP_RPATH=ON`），运行时必须使用 venv Qt 库。独立加载探针仅导入 QtGui、未设库路径时，系统 QtWidgets 被选中，报 `_ZTI21QMetaTypeModuleHelper, version Qt_6_PRIVATE_API`，见 new-plugin-loader-without-library-path.log；这次失败原文保留。明确使用以下环境后 new-plugin-loader.log 中加载为 True：

```sh
export LD_LIBRARY_PATH="$PWD/.venv/lib/python3.13/site-packages/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_PLUGIN_PATH=/tmp/ai-upper-qt611-sdk/plugins
export QT_IM_MODULE=fcitx
AI_UPPER_HOME=/tmp/ai-upper-qt611-run PYTHONPATH=app/src .venv/bin/python -c 'import qml_shell; qml_shell.run(False)'
```

此命令需要真实显示会话与 fcitx5 守护进程。审计的独立 Xvfb/D-Bus 启动脚本为 `scripts/parity/qt611_input_run.sh`，记录真实键盘输入，不能代替未测试的物理桌面或 Wayland 环境。

new-plugin-dynamic.log 无 SDK RPATH、无 QtWaylandClient NEEDED 项；new-plugin-ldd.log 使用明确的 venv LD_LIBRARY_PATH，指向 venv Qt Core/Gui/Widgets/DBus。plugin.sha256 为新插件哈希。Qt 的私有 API 版本绑定警告保留于 fcitx-configure.log，未来 Qt 升级需重新构建验证。

没有修改依赖 pin、venv、系统目录或应用实现。激活只作用于命令环境；回退为退出该进程、取消本次添加的三个环境变量即可。`/tmp` SDK/插件不是永久安装，清理后需按脚本重建。原系统插件与其 ABI 错误未被删除或掩盖。
