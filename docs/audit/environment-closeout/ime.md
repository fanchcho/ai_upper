# F84隔离组合复试

当前应用Qt+系统fcitx插件仍报 `undefined symbol: _ZTI20QGenericUnixServices, version Qt_6_PRIVATE_API`（ime-abi.log）。
另用系统 `/usr/bin/python3` 的 PySide6/Qt 6.8.2，与系统插件匹配，Xvfb+私有D-Bus运行fcitx5。XDG_CONFIG_HOME/DATA_HOME/RUNTIME_DIR 指向 .tmp/environment-closeout/ime-*，AI_UPPER_HOME=/tmp/ai-upper-ime-isolated。私有总线使用 .tmp/secret-service/bus.conf，运行 .tmp/environment-closeout/ime.sh；探针已保存 scripts/parity/environment_ime_probe.py。

真实 xdotool Ctrl+Space 后键入 nihao，插件成功 loaded library，结果 `QT 6.8.2 FINAL 'nihao'`；没有任何 inputMethodEvent preedit/commit 记录。ime-system.log与fcitx-daemon.log为原始输出，ime.log保留前次总线缺session.conf报错。未合成QInputMethodEvent，未修改仓库pin。

结论：匹配ABI插件加载已验证；真实中文preedit/commit未取得，F84真实环境未验证。不能把拉丁文本输入或插件加载当中文输入成功。
