# 默认 Qt 6.11.2 fcitx 配套：未完成

find /usr/lib /usr/local/lib .venv .tmp -name '*fcitx*plugin*.so' 仅找到系统Qt6插件，清单plugin-inventory.log；venv无Qt6Config.cmake或qplatforminputcontext.h，qt-sdk.log为空。没有现成6.11插件。

从fcitx/fcitx5-qt官方master下载源码到.tmp/next-boundary（未修改仓库pin），逐步隔离解包ECM、XCB/XKB、fcitx utils开发包；配置日志fcitx-configure*.log保存缺依赖原文。BUILD_ONLY_PLUGIN=ON、ENABLE_X11=OFF、Wayland workaround关闭的最小配置仍失败于qt6/CMakeLists.txt:7：Could not find a package configuration file provided by "Qt6"，Qt6Config.cmake不存在。qt6/CMakeLists.txt:9-10还要求GuiPrivate，不能用6.8头文件对6.11库硬拼。

匹配Qt6.11.2源码获取探测见qt-sdk-fetch.log；没有完成完整Qt SDK构建，未产出可加载插件。没有用禁用X11的配置冒充实际输入成功。系统插件旧错误undefined symbol: _ZTI20QGenericUnixServices继续保留于../environment-closeout/ime-abi.log；未升级默认F84。下一步需要完整6.11.2开发SDK及私有头，再构建fcitx平台插件，当前不是已完成。
