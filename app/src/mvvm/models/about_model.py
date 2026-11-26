"""关于窗口的内容：属于 Model 层的数据，不含任何界面代码。"""

from __future__ import annotations
from locale_runtime import tr

from mvvm.models.base_model import BaseModel

DEFAULT_TITLE = tr('legacy.4f2c9a32be62')

# 本应用的分层职责。写在 model 里而不是视图里：这段文字是数据，
# 视图只负责把它显示出来。
LAYERS = (
    ("models/", tr('legacy.966cb0e44ce5')),
    ("view_models/", tr('legacy.2d023774e562')),
    ("views/", tr('legacy.905315dd0159')),
    ("services/", tr('legacy.01a6030677d4')),
)


def default_body() -> str:
    """默认文案：本应用的分层，以及这个窗口是怎么被打开的"""
    layers = "\n".join(f"  {name}  {duty}" for name, duty in ((('models/', tr('legacy.966cb0e44ce5')), ('view_models/', tr('legacy.2d023774e562')), ('views/', tr('legacy.905315dd0159')), ('services/', tr('legacy.01a6030677d4')))))
    return (
        tr('legacy.8d570ae295b7', p1=layers)
    )


class AboutModel(BaseModel):
    """「关于」窗口的数据"""

    def __init__(self, title: str | None = None, body: str | None = None) -> None:
        super().__init__()
        self.title: str = title if title is not None else tr('legacy.4f2c9a32be62')
        self.body: str = default_body() if body is None else body

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'body': self.body,
        }

    def from_dict(self, data: dict) -> None:
        self.title = data.get('title', (tr('legacy.4f2c9a32be62')))
        self.body = data.get('body', default_body())
