# 独立 QtQml 导入修复

基线 ee1fa97。未修改已验收盘点或既有测试。

原始复现：`AI_UPPER_HOME=/tmp/ai-upper-import-before TMPDIR=$PWD/.tmp/remaining .venv/bin/python -m pytest app/tests/test_mvvm.py::test_every_mvvm_module_imports -q`，1 failed；humation.py 模块级加载 QtQml 导致失败，原始输出 import-before.log。

修复：仅将 QtQml 导入移入 Humation.__init__，模块枚举不加载渲染运行库，真正构造对象仍使用原生 QJSEngine，无空替身和异常吞掉。

同一独立命令在全新进程执行：1 passed，import-after.log。另以 QT_QPA_PLATFORM=offscreen、AI_UPPER_HOME=/tmp/ai-upper-humation-after 运行 test_humation_runtime.py 与 test_mvvm.py：10 passed，import-runtime.log。真实头像渲染路径验证通过。
