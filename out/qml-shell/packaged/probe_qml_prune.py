"""在真实 wheel 解包树上跑 prune，并用被裁后的 PySide6 真加载 Main.qml。

为什么单独一个脚本：`prune()` 的结果必须在**真 Qt payload** 上验证，假 wheel
（`test_qt_prune.py` 里那套）只能证明判定逻辑，证明不了 `libqtquickcontrols2plugin.so`
能不能在裁完的库集合里 dlopen。本脚本不是测试，是打包链的一次人工核对。
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from ai_upper import qt_prune                      # noqa: E402
from ai_upper.config import TARGETS                # noqa: E402

WORK = ROOT / "out" / "qml-shell" / "packaged" / "prune-site"
WHEELS = ROOT / "build" / "wheels" / "linux-arm64"

if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir(parents=True)
for wheel in sorted(WHEELS.glob("pyside6_*.whl")) + sorted(WHEELS.glob("shiboken6-*.whl")):
    zipfile.ZipFile(wheel).extractall(WORK)

modules = {"QtCore", "QtGui", "QtWidgets", "QtNetwork", "QtPrintSupport", "QtQml",
           "QtQuick", "QtQuickControls2", "QtQuickLayouts", "QtQuickTemplates2",
           "QtWebEngineCore", "QtWebEngineWidgets", "QtWebChannel"}
counters = qt_prune.prune(WORK, TARGETS["linux-arm64"], modules, source_root=ROOT / "app" / "src")
print("PRUNE", counters)

qml = WORK / "PySide6" / "Qt" / "qml"
kept = sorted(p.relative_to(qml).as_posix() for p in qml.rglob("*") if p.is_file())
print("PRUNE qml files", len(kept))
for name in kept:
    print("  KEPT", name, (qml / name).stat().st_size)

probe = (
    "import sys\n"
    "from PySide6 import QtCore, QtGui, QtQml\n"
    "app = QtGui.QGuiApplication([])\n"
    "engine = QtQml.QQmlApplicationEngine()\n"
    "engine.load(QtCore.QUrl.fromLocalFile(sys.argv[1]))\n"
    "print('ROOTS', len(engine.rootObjects()))\n"
    "sys.exit(0 if engine.rootObjects() else 1)\n"
)
env = {"QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
       "PYTHONPATH": str(WORK), "PATH": "/usr/bin:/bin"}
result = subprocess.run(
    [str(ROOT / "runtimes" / "linux-arm64" / "3.13.5" / "bin" / "python3.13"), "-c", probe,
     str(ROOT / "app" / "src" / "qml" / "Main.qml")],
    capture_output=True, text=True, env=env,
)
print("PROBE rc=", result.returncode)
print(result.stdout.strip())
print(result.stderr.strip())
sys.exit(0 if result.returncode == 0 else 1)
