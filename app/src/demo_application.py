"""演示用的第二个装配处：复用 AiUpperApplication 的全部装配，只多注册一个示例页。

这正是仓库文档描述的扩展方式——新增 View/ViewModel 后只改装配处；这里用一个
子类承载，是为了不干扰参考实现 application.py 与它的测试。
"""
from __future__ import annotations

from application import AiUpperApplication
from mvvm.view_models.demo_vm import DemoViewModel
from mvvm.views.demo_window import DemoWindow


class DemoApplication(AiUpperApplication):
    def initialize_viewmodels(self) -> None:
        super().initialize_viewmodels()
        self.mvvm_app.register_viewmodel("demo", DemoViewModel())

    def initialize_views(self) -> None:
        super().initialize_views()
        self.mvvm_app.register_view("demo", DemoWindow(self.mvvm_app.get_viewmodel("demo")))
