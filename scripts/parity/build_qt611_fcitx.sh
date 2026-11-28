#!/usr/bin/env bash
set -euo pipefail
# Isolated developer SDK, not an application runtime replacement.
# ECM and XKB development files were unpacked by the previous investigation.
sdk_root=${1:-/tmp/ai-upper-qt611-sdk}
fcitx_source=${2:-$PWD/.tmp/next-boundary/fcitx5-qt-master}
deps=${3:-$PWD/.tmp/next-boundary/sdk/usr}
case "$sdk_root" in /tmp/*) ;; *) echo 'SDK root must be under /tmp' >&2; exit 2;; esac
mkdir -p "$sdk_root"
if [ ! -f "$sdk_root/qtbase.tar.xz" ]; then
    curl --fail --location https://download.qt.io/official_releases/qt/6.11/6.11.2/submodules/qtbase-everywhere-src-6.11.2.tar.xz -o "$sdk_root/qtbase.tar.xz"
fi
if [ ! -d "$sdk_root/qtbase-everywhere-src-6.11.2" ]; then
    tar -xf "$sdk_root/qtbase.tar.xz" -C "$sdk_root"
fi
cmake -S "$sdk_root/qtbase-everywhere-src-6.11.2" -B "$sdk_root/build-make" \
    -G 'Unix Makefiles' -DCMAKE_INSTALL_PREFIX="$sdk_root/install" \
    -DCMAKE_BUILD_TYPE=Release -DQT_BUILD_TESTS=OFF -DQT_BUILD_EXAMPLES=OFF \
    -DINPUT_opengl=no -DFEATURE_opengl=OFF -DFEATURE_xcb=OFF
cmake --build "$sdk_root/build-make" --parallel 4
cmake --install "$sdk_root/build-make"
cmake -S "$fcitx_source" -B "$sdk_root/fcitx-build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$sdk_root/install;$deps" \
    -DBUILD_ONLY_PLUGIN=ON -DENABLE_QT5=OFF -DENABLE_QT6=ON \
    -DENABLE_X11=OFF -DENABLE_QT6_WAYLAND_WORKAROUND=OFF \
    -DXKBCommon_XKBCommon_LIBRARY=/usr/lib/aarch64-linux-gnu/libxkbcommon.so.0 \
    -DXKBCommon_XKBCommon_INCLUDE_DIR="$deps/include" \
    -DCMAKE_INSTALL_QT6PLUGINDIR="$sdk_root/plugins" -DCMAKE_SKIP_RPATH=ON
cmake --build "$sdk_root/fcitx-build" --parallel 4
cmake --install "$sdk_root/fcitx-build"
printf 'Plugin root: %s/plugins\nUse the application venv Qt libraries, not SDK libraries, at runtime.\n' "$sdk_root"
